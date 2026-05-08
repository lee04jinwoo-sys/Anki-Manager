import argparse
import sys
import os
import concurrent.futures
from tqdm import tqdm
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# Project Modules
from core.generator import generate_situation_content
from core.selector import run_sentence_selection, run_vocabulary_selection
from core.completer import run_note_completion, run_universal_field_completion
from collectors.youtube import YouTubeFetcher
from collectors.obsidian import ObsidianManager
from integrations.audio import AnkiTTSFiller
from integrations.anki_connect import AnkiConnector
from utils.inspector import inspect_items
from utils.stats import get_deck_stats
from utils.cleaner import clean_duplicates, find_leeches
from utils.organizer import run_organizer
from utils.cluster import run_clustering
from utils.leech_resolver import LeechResolver
from utils.ui import UI
from utils.cli_selector import InteractiveSelector
from utils.design_manager import export_design, import_design
from utils.settings_editor import menu_settings

def run_workflow_interactive(source=None, input_data=None):
    if not source:
        UI.clear()
        UI.subheader("데이터 소스 선택")
        
        options = [
            ("youtube", "1. YouTube URL"),
            ("situation", "2. Situation (상황 설명)"),
            ("obsidian", "3. Obsidian Inbox")
        ]
        source_choice = InteractiveSelector.select_one(
            [opt[1] for opt in options], 
            title="데이터 소스를 선택하세요"
        )
        
        if not source_choice:
            return
            
        source = next(opt[0] for opt in options if opt[1] == source_choice)

    if not input_data and source not in ["obsidian"]:
        input_data = UI.ask(f"[{source}]에 대한 입력을 입력하세요").strip()
        if not input_data:
            return

    run_workflow(source, input_data)

def run_workflow(source, input_data):
    UI.clear()
    UI.info(f"Anki 자동화 워크플로우 시작 (소스: {source})")
    
    steps_map = {
        "youtube":   {"fetch":10,"select_s":25,"select_v":15,"enrich":20,"audio":15,"organize":5,"cluster":10},
        "obsidian":  {"fetch":10,"enrich":60,"audio":15,"organize":5,"cluster":10},
        "situation": {"gen":30,"enrich":40,"audio":15,"organize":5,"cluster":10},
    }
    
    ws_config = steps_map.get(source)
    if not ws_config: return

    total_points = sum(ws_config.values())

    with UI.progress() as progress:
        pbar = progress.add_task("[cyan]전체 진행률...", total=total_points)
        
        # Wrapper for compatibility with tqdm-like usage
        class RichPbar:
            def update(self, n): progress.update(pbar, advance=n)
            def write(self, msg): UI.step(msg)
            def set_description(self, msg): progress.update(pbar, description=f"[cyan]{msg}")
            def clear(self): pass
            def refresh(self): pass


        rpbar = RichPbar()
        selected_sentences = None
        selected_vocab = None
        obsidian_mgr = None

        if source == "youtube":
            rpbar.set_description("YouTube 자막 가져오는 중...")
            import re
            v_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", input_data)
            if not v_id_match:
                UI.error("유효한 YouTube ID를 찾을 수 없습니다.")
                return
            
            sentences = YouTubeFetcher.fetch_transcript(v_id_match.group(1), pbar=rpbar)
            if not sentences: return
            rpbar.update(ws_config["fetch"])

            rpbar.set_description("문장 및 단어 선별 중...")
            from config import MODEL_VOCAB
            existing_vocab = AnkiConnector.get_existing_vocab_words(MODEL_VOCAB)
            
            data = {"source": input_data, "content": " ".join(sentences)}
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                fs = ex.submit(run_sentence_selection, data, pbar=rpbar, step_points=ws_config["select_s"])
                fv = ex.submit(run_vocabulary_selection, data, existing_vocab, pbar=rpbar, step_points=ws_config["select_v"])
                selected_sentences, selected_vocab = fs.result(), fv.result()

        elif source == "obsidian":
            rpbar.set_description("Obsidian Inbox 데이터 가져오는 중...")
            obsidian_mgr = ObsidianManager()
            data = obsidian_mgr.fetch_inbox_content()
            if not data or (not data["vocab"] and not data["sentences"]):
                UI.info("가져올 Obsidian 데이터가 없습니다.")
                return
            selected_sentences = {"sentences": data["sentences"]}
            selected_vocab = {"vocab": data["vocab"]}
            rpbar.update(ws_config["fetch"])

        elif source == "situation":
            rpbar.set_description("상황 기반 컨텐츠 생성 중...")
            gen = generate_situation_content(input_data, pbar=rpbar, step_points=ws_config["gen"])
            if not gen: return
            selected_sentences = {"sentences": gen.get('sentences', [])}
            selected_vocab = {"vocab": gen.get('vocab', [])}

        def cli_inspector(enriched):
            UI.subheader("최종 데이터 검수")
            if enriched.get("sentences"):
                UI.step(f"문장 - {len(enriched['sentences'])}개")
                enriched["sentences"] = inspect_items(enriched["sentences"], lambda x: f"문장: {x.get('문장')}")
            if enriched.get("vocab"):
                UI.step(f"단어 - {len(enriched['vocab'])}개")
                enriched["vocab"] = inspect_items(enriched["vocab"], lambda x: f"단어: {x.get('단어')}")
            return enriched

        rpbar.set_description("노트 추가 및 내용 보강 중...")
        if not run_note_completion(selected_sentences, selected_vocab, pbar=rpbar, 
                                   step_points=ws_config["enrich"], inspector_func=cli_inspector):
            UI.error("노트 추가 중 오류가 발생했습니다.")
            return

        if source == "obsidian" and obsidian_mgr:
            rpbar.set_description("Obsidian Inbox 비우는 중...")
            obsidian_mgr.clear_processed_content()
            UI.success("Obsidian 데이터가 정리되었습니다.")

        rpbar.set_description("오디오 추가 중...")
        AnkiTTSFiller.run_audio_addition(pbar=rpbar, step_points=ws_config["audio"])

        rpbar.set_description("카드 정리 중...")
        run_organizer(pbar=rpbar, step_points=ws_config["organize"])

        rpbar.set_description("AI 유의어 맵 업데이트 중...")
        run_clustering(pbar=rpbar, step_points=ws_config["cluster"])

    UI.print("모든 작업이 성공적으로 완료되었습니다!", style="bold green")

def menu_add_notes():
    run_workflow_interactive()

def menu_organize_notes():
    while True:
        UI.clear()
        UI.subheader("노트 정리")

        
        options = [
            ("1", "1. 누락된 오디오 채우기"),
            ("2", "2. 빈 필드 자동 완성 (모든 모델)"),
            ("3", "3. 유의어 자동 클러스터링 (AI)"),
            ("4", "4. 카드 자동 정리 (덱 이동)"),
            ("5", "5. 중복 카드 제거"),
            ("b", "b. 메인 메뉴로 돌아가기")
        ]
        
        choice_text = InteractiveSelector.select_one(
            [opt[1] for opt in options],
            title="노트 정리"
        )
        
        if not choice_text or "메인 메뉴로 돌아가기" in choice_text:
            break
            
        choice = next(opt[0] for opt in options if opt[1] == choice_text)
        
        if choice == '1':
            UI.subheader("누락된 오디오 채우기")
            AnkiTTSFiller.run_audio_addition()
            UI.ask("계속하려면 Enter를 누르세요", default="")
        elif choice == '2':
            UI.subheader("빈 필드 자동 완성")
            run_universal_field_completion()
            UI.ask("계속하려면 Enter를 누르세요", default="")
        elif choice == '3':
            UI.subheader("유의어 자동 클러스터링")
            run_clustering()
            UI.ask("계속하려면 Enter를 누르세요", default="")
        elif choice == '4':
            UI.subheader("카드 자동 정리")
            run_organizer()
            UI.ask("계속하려면 Enter를 누르세요", default="")
        elif choice == '5':
            UI.subheader("중복 카드 제거")
            clean_duplicates()
            UI.success("중복 카드가 제거되었습니다.")
            UI.ask("계속하려면 Enter를 누르세요", default="")

def menu_design():
    while True:
        UI.clear()
        UI.subheader("디자인 관리")
        
        options = [
            ("export", "1. 디자인을 JSON으로 내보내기 (Anki -> JSON)"),
            ("import", "2. JSON에서 디자인 가져오기 (JSON -> Anki)"),
            ("b", "b. 메인 메뉴로 돌아가기")
        ]
        
        choice_text = InteractiveSelector.select_one(
            [opt[1] for opt in options],
            title="디자인 관리"
        )
        
        if not choice_text or "메인 메뉴로 돌아가기" in choice_text:
            break
            
        choice = next(opt[0] for opt in options if opt[1] == choice_text)
        
        if choice == 'export':
            export_design()
            UI.ask("계속하려면 Enter를 누르세요", default="")
        elif choice == 'import':
            import_design()
            UI.ask("계속하려면 Enter를 누르세요", default="")

def menu_statistics():
    UI.clear()
    UI.subheader("덱 통계 분석")
    with UI.wait("상세 통계 불러오는 중"):
        stats = get_deck_stats(fast_mode=False) # Full mode for the statistics menu
    if stats:
        columns = ["덱 이름", "새 카드", "7일 유지율"]
        rows = [[s['name'], str(s['new']), s['ret_7d']] for s in stats]
        UI.table("상세 덱 통계", columns, rows)
    else:
        UI.error("통계를 불러올 수 없습니다.")
    UI.ask("계속하려면 Enter를 누르세요", default="")

def build_dashboard_panel():
    stats = get_deck_stats(fast_mode=True)
    if not stats:
        return Panel(Text("Anki 오프라인", style="bold red", justify="center"), title="[bold white]대시보드[/]", border_style="red")
    
    table = Table(box=None, header_style="bold magenta", expand=True)
    table.add_column("덱", style="bold white")
    table.add_column("전체", justify="right", style="grey70")
    table.add_column("새 카드", justify="right", style="cyan")
    table.add_column("복습", justify="right", style="red")
    table.add_column("오늘", justify="right", style="green")
    table.add_column("남은 일수", justify="right", style="bold yellow")
    
    for s in stats:
        if s['name'] in ["[Root]", "listening"]: continue
        table.add_row(
            s['name'], 
            str(s['total']),
            str(s['new']), 
            str(s.get('due', 0)),
            str(s.get('reviews_today', 0)), 
            f"{s.get('exhaust_days', '∞')}일"
        )
        
    return Panel(
        table,
        title=f"[bold white]학습 현황[/]", 
        border_style="bright_cyan", 
        expand=True
    )

def build_system_info_panel():
    from config import SENTENCE_SELECTOR_MODEL, CURRENT_TARGET, OBSIDIAN_VAULT_PATH
    
    grid = Table.grid(expand=True)
    grid.add_column(ratio=2) # AI
    grid.add_column(ratio=2) # Anki
    grid.add_column(ratio=6) # Shortcuts
    
    ai = f"[cyan]AI 모델:[/] {SENTENCE_SELECTOR_MODEL.split('-')[1] if '-' in SENTENCE_SELECTOR_MODEL else SENTENCE_SELECTOR_MODEL}"
    anki = f"[green]Anki 대상:[/] {CURRENT_TARGET}"
    shortcuts = f"[yellow]↑↓:이동 | Enter:선택 | Q/ㅂ:종료[/]"

    grid.add_row(ai, anki, shortcuts)
    
    return Panel(
        grid,
        title=f"[bold white]시스템 정보[/]",
        border_style="bright_cyan",
        padding=(0, 1)
    )

def interactive_menu():
    while True:
        UI.clear()

        header = UI.make_header("Anki Manager CLI")
        dashboard = build_dashboard_panel()
        sys_info = build_system_info_panel()

        options = [
            ("1", "1. 노트 추가 (YouTube, 상황, Obsidian)"),
            ("2", "2. 노트 정리 (오디오, 필드, 이동)"),
            ("3", "3. Leech 단어 강화 (오늘/최다)"),
            ("4", "4. 카드 디자인 관리 (내보내기/가져오기)"),
            ("5", "5. 설정 변경 (경로, 대상, 모델, 언어)"),
            ("6", "6. 덱 통계 분석"),
            ("q", "q. 종료")
        ]

        choice_text = InteractiveSelector.select_one(
            [opt[1] for opt in options], 
            title="Anki Manager CLI 메인 메뉴",
            side_panel=dashboard,
            bottom_panel=sys_info,
            header_panel=header
        )

        if not choice_text or choice_text.startswith('q'):
            UI.info("프로그램을 종료합니다.")
            break

        # Finding choice based on text
        choice = None
        for opt in options:
            if opt[1] == choice_text:
                choice = opt[0]
                break
        
        if not choice: break

        if choice == '1':
            run_workflow_interactive()
        elif choice == '2':
            menu_organize_notes()
        elif choice == '3':
            LeechResolver.resolve()
        elif choice == '4':
            menu_design()
        elif choice == '5':
            menu_settings()
        elif choice == '6':
            menu_statistics()

        elif choice == 'q':
            UI.info("Exiting program.")
            break

def main():
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Anki Manager CLI")
        subparsers = parser.add_subparsers(dest="command")

        run_parser = subparsers.add_parser("run")
        run_parser.add_argument("--source", choices=["youtube", "situation", "obsidian"], default="youtube")
        run_parser.add_argument("--input")

        subparsers.add_parser("stats")
        subparsers.add_parser("audio")
        subparsers.add_parser("organize")

        args = parser.parse_args()

        if args.command == "run":
            run_workflow(args.source, args.input or input("입력: "))
        elif args.command == "stats":
            print(get_deck_stats())
        elif args.command == "audio":
            AnkiTTSFiller.run_audio_addition()
        elif args.command == "organize":
            run_organizer()
        else:
            parser.print_help()
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
