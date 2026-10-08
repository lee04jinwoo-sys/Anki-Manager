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
from core.knowledge_extractor import run_knowledge_workflow
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
from utils.pos_automator import run_pos_automation
from utils.ui import UI
from utils.cli_selector import InteractiveSelector
from utils.design_manager import export_design, import_design, sync_design_from_code
from utils.settings_editor import menu_settings
from utils.vocab_importer import run_vocab_importer_flow
from utils.tv_show_importer import run_tv_show_importer_flow

def run_workflow_interactive(source=None, input_data=None):
    if not source:
        UI.clear()
        UI.subheader("데이터 소스 선택")
        
        options = [
            ("youtube", "1. YouTube URL (영어 문장/단어)"),
            ("situation", "2. Situation (상황 설명 - 영어)"),
            ("obsidian", "3. Obsidian Inbox"),
            ("github", "4. GitHub Vocabulary (깃허브 실시간 어휘집)"),
            ("modern_family", "5. Modern Family Script (모던 패밀리 자막)"),
            ("knowledge", "6. 🏛️ Knowledge Q&A (교양/지식 - 유튜브, 웹 URL, 텍스트)")
        ]
        source_choice = InteractiveSelector.select_one(
            [opt[1] for opt in options], 
            title="데이터 소스를 선택하세요"
        )
        
        if not source_choice:
            return
            
        source = next(opt[0] for opt in options if opt[1] == source_choice)

    if source == "knowledge":
        from utils.topic_manager import TopicManager
        import subprocess

        while True:
            UI.clear()
            UI.subheader("🏛️ Knowledge Q&A (일반 지식 / 교양 카드 생성)")

            # 클립보드 내용 확인
            cb_content = ""
            try:
                cb_content = subprocess.check_output(['pbpaste'], text=True).strip()
            except Exception:
                pass

            cb_preview = (cb_content[:50] + "...") if len(cb_content) > 50 else cb_content
            has_clipboard = bool(cb_content and ("http" in cb_content or len(cb_content) > 30))

            sub_options = []
            if has_clipboard:
                sub_options.append(("clipboard", f"📋 클립보드 내용으로 즉시 생성 ({cb_preview})"))
            sub_options.append(("input", "⌨️ URL 또는 텍스트 직접 입력"))
            sub_options.append(("topics", "⚙️ 대주제/소주제 및 저장 덱 관리"))
            sub_options.append(("back", "b. 이전 메뉴로 돌아가기"))

            sub_choice_text = InteractiveSelector.select_one(
                [opt[1] for opt in sub_options],
                title="Knowledge 작업을 선택하세요"
            )

            if not sub_choice_text or "이전 메뉴" in sub_choice_text:
                return

            sub_choice = next(opt[0] for opt in sub_options if opt[1] == sub_choice_text)

            if sub_choice == "topics":
                TopicManager.menu_manage_topics()
                continue

            url_or_text = ""
            if sub_choice == "clipboard":
                url_or_text = cb_content
                UI.info(f"클립보드 로드 완료 ({len(url_or_text)}자)")
            elif sub_choice == "input":
                url_or_text = UI.ask("유튜브 URL, 웹 기사 URL, 또는 텍스트를 입력하세요").strip()

            if not url_or_text:
                continue

            count_str = UI.ask("생성할 목표 카드 수를 입력하세요 (기본: 10)", default="10").strip()
            try:
                target_count = int(count_str)
            except ValueError:
                target_count = 10

            run_knowledge_workflow(url_or_text, target_count=target_count)
            UI.ask("\n계속하려면 Enter를 누르세요", default="")
            break
        return

    if source == "github":
        # GitHub Importer is a self-contained interactive flow
        run_vocab_importer_flow()
        return

    if source == "modern_family":
        # Launch Modern Family directly
        run_vocab_importer_flow(preset_mode=True, preset_key="modern_family")
        return

    if not input_data and source not in ["obsidian"]:
        input_data = UI.ask(f"[{source}]에 대한 입력을 입력하세요").strip()
        if not input_data:
            return

    run_workflow(source, input_data)

def run_workflow(source, input_data, progress_cb=None, is_web=False):
    if not is_web:
        UI.clear()
        UI.info(f"Anki 자동화 워크플로우 시작 (소스: {source})")
    
    steps_map = {
        "youtube":   {"fetch":10,"select_s":25,"select_v":15,"enrich":20,"audio":15,"organize":5,"cluster":10},
        "obsidian":  {"fetch":10,"enrich":60,"audio":15,"organize":5,"cluster":10},
        "situation": {"gen":30,"enrich":40,"audio":15,"organize":5,"cluster":10},
        "knowledge": {"fetch":30,"extract":50,"save":20},
    }
    
    ws_config = steps_map.get(source)
    if not ws_config:
        if progress_cb: progress_cb(f"알 수 없는 소스: {source}", 0, "error")
        return

    total_points = sum(ws_config.values())
    current_progress = 0

    def log_step(msg, advance=0, level="info"):
        nonlocal current_progress
        current_progress += advance
        pct = min(100, int((current_progress / total_points) * 100)) if total_points > 0 else 0
        if not is_web:
            if level == "error": UI.error(msg)
            elif level == "warn": UI.warn(msg)
            elif level == "success": UI.success(msg)
            else: UI.step(msg)
        if progress_cb:
            progress_cb(msg, pct, level)

    log_step(f"워크플로우 시작 (소스: {source})", 0, "info")

    class WebOrRichPbar:
        def update(self, n):
            log_step("진행 중...", advance=n, level="info")
        def write(self, msg):
            log_step(msg, 0, "info")
        def set_description(self, msg):
            log_step(msg, 0, "info")
        def clear(self): pass
        def refresh(self): pass

    rpbar = WebOrRichPbar()
    selected_sentences = None
    selected_vocab = None
    obsidian_mgr = None

    if source == "youtube":
        log_step("YouTube 자막 가져오는 중...", 0, "info")
        import re
        v_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", input_data)
        if not v_id_match:
            log_step("유효한 YouTube ID를 찾을 수 없습니다.", 0, "error")
            return
        
        res = YouTubeFetcher.fetch_transcript(v_id_match.group(1), pbar=rpbar)
        if not res:
            log_step("YouTube 자막을 가져오지 못했습니다.", 0, "error")
            return
        sentences = res["sentences"]
        segments = res["segments"]
        video_id = v_id_match.group(1)
        log_step(f"YouTube 자막 로드 완료 ({len(sentences)} 문장)", ws_config["fetch"], "success")

        log_step("문장 및 단어 선별 중...", 0, "info")
        from config import MODEL_VOCAB
        existing_vocab = AnkiConnector.get_existing_vocab_words(MODEL_VOCAB)
        
        data = {"source": input_data, "content": " ".join(sentences)}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            fs = ex.submit(run_sentence_selection, data, pbar=rpbar, step_points=ws_config["select_s"])
            fv = ex.submit(run_vocabulary_selection, data, existing_vocab, pbar=rpbar, step_points=ws_config["select_v"])
            selected_sentences, selected_vocab = fs.result(), fv.result()
            
        if selected_sentences:
            selected_sentences["segments"] = segments
            selected_sentences["video_id"] = video_id
        if selected_vocab:
            selected_vocab["segments"] = segments
            selected_vocab["video_id"] = video_id

    elif source == "obsidian":
        log_step("Obsidian Inbox 데이터 읽는 중...", 0, "info")
        obsidian_mgr = ObsidianManager()
        data = obsidian_mgr.fetch_inbox_content()
        if not data or (not data["vocab"] and not data["sentences"]):
            log_step("가져올 Obsidian 데이터가 없습니다 (Inbox 파일이 비어있음).", 0, "warn")
            return
        selected_sentences = {"sentences": data["sentences"]}
        selected_vocab = {"vocab": data["vocab"]}
        log_step(f"Obsidian 데이터 로드 완료 (단어 {len(data['vocab'])}개, 문장 {len(data['sentences'])}개)", ws_config["fetch"], "success")

    elif source == "situation":
        log_step("상황 기반 컨텐츠 AI 생성 중...", 0, "info")
        gen = generate_situation_content(input_data, pbar=rpbar, step_points=ws_config["gen"])
        if not gen:
            log_step("상황 컨텐츠 생성 실패", 0, "error")
            return
        selected_sentences = {"sentences": gen.get('sentences', [])}
        selected_vocab = {"vocab": gen.get('vocab', [])}
        log_step("상황 컨텐츠 생성 완료", ws_config["gen"], "success")

    elif source == "knowledge":
        log_step("Knowledge 콘텐츠 로드 및 Q&A 추출 중...", 0, "info")
        from core.knowledge_extractor import run_knowledge_workflow
        success = run_knowledge_workflow(input_data, target_count=10, is_web=is_web, pbar=rpbar)
        if success:
            log_step("Knowledge Q&A 생성 및 Anki 저장 완료!", ws_config["save"], "success")
        else:
            log_step("Knowledge Q&A 생성 실패", 0, "error")
        return

    def cli_inspector(raw_data):
        if is_web:
            return raw_data # 웹 모드에서는 터미널 대기 없이 전체 처리
        UI.subheader("학습 데이터 선별 (원하는 항목만 체크)")
        if raw_data.get("sentences"):
            UI.step(f"선별된 문장 후보 - {len(raw_data['sentences'])}개")
            raw_data["sentences"] = inspect_items(
                raw_data["sentences"], 
                lambda x: f"문장: {x if isinstance(x, str) else x.get('문장', '')}"
            )
        if raw_data.get("vocab"):
            UI.step(f"선별된 단어 후보 - {len(raw_data['vocab'])}개")
            raw_data["vocab"] = inspect_items(
                raw_data["vocab"], 
                lambda x: f"단어: {x}" if isinstance(x, str) else f"단어: {x.get('단어', '')} ({x.get('뜻', '')})"
            )
        return raw_data

    log_step("노트 추가 및 AI 내용 보강(뜻, 예문, 품사) 진행 중...", 0, "info")
    inspector = None if is_web else cli_inspector
    if not run_note_completion(selected_sentences, selected_vocab, pbar=rpbar, 
                               step_points=ws_config["enrich"], inspector_func=inspector):
        log_step("노트 추가 중 오류가 발생했습니다.", 0, "error")
        return

    if source == "obsidian" and obsidian_mgr:
        log_step("Obsidian Inbox 정리 중...", 0, "info")
        obsidian_mgr.clear_processed_content()
        log_step("Obsidian Inbox 정리 완료", 0, "success")

    log_step("TTS 오디오 생성 및 추가 중...", 0, "info")
    AnkiTTSFiller.run_audio_addition(pbar=rpbar, step_points=ws_config["audio"])

    log_step("카드 규칙별 덱 자동 정리 중...", 0, "info")
    run_organizer(pbar=rpbar, step_points=ws_config["organize"])

    log_step("AI 유의어 맵 클러스터링 업데이트 중...", 0, "info")
    run_clustering(pbar=rpbar, step_points=ws_config["cluster"])

    log_step("모든 작업이 성공적으로 완료되었습니다!", 0, "success")

def menu_add_notes():
    run_workflow_interactive()

def menu_organize_notes():
    while True:
        UI.clear()
        UI.subheader("노트 정리")

        
        options = [
            ("1", "1. 누락된 오디오 채우기"),
            ("2", "2. 빈 필드 자동 완성 (모든 모델)"),
            ("3", "3. 누락된 품사 채우기 (NLTK)"),
            ("4", "4. 유의어 자동 클러스터링 (AI - 전체 재배치)"),
            ("5", "5. 카드 자동 정리 (덱 이동)"),
            ("6", "6. 중복 카드 제거"),
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
            UI.subheader("누락된 품사 채우기 (NLTK)")
            run_pos_automation()
            UI.ask("계속하려면 Enter를 누르세요", default="")
        elif choice == '4':
            UI.subheader("유의어 자동 클러스터링 (전체 재배치)")
            run_clustering(full_recluster=True)
            UI.ask("계속하려면 Enter를 누르세요", default="")
        elif choice == '5':
            UI.subheader("카드 자동 정리")
            run_organizer()
            UI.ask("계속하려면 Enter를 누르세요", default="")
        elif choice == '6':
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
            ("sync", "3. Python 설정에서 디자인 강제 적용 (config.py -> Anki)"),
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
        elif choice == 'sync':
            sync_design_from_code()
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
            ("1", "1. 노트 추가 (YouTube, 상황, Obsidian, GitHub, Friends)"),
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
        run_parser.add_argument("--source", choices=["youtube", "situation", "obsidian", "github", "friends"], default="youtube")
        run_parser.add_argument("--input")

        subparsers.add_parser("stats")
        subparsers.add_parser("audio")
        subparsers.add_parser("organize")

        args = parser.parse_args()

        if args.command == "run":
            if args.source == "github":
                run_vocab_importer_flow(preset_mode=True)
            elif args.source == "friends":
                run_tv_show_importer_flow()
            else:
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
