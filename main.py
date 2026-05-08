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
from utils.leech_resolver import LeechResolver
from utils.ui import UI
from utils.cli_selector import InteractiveSelector
from utils.design_manager import export_design, import_design

def run_workflow_interactive(source=None, input_data=None):
    if not source:
        UI.clear()
        UI.header()
        UI.subheader("Source Selection")
        
        options = [
            ("youtube", "YouTube URL"),
            ("situation", "Situation (Description)"),
            ("obsidian", "Obsidian Inbox")
        ]
        source_choice = InteractiveSelector.select_one(
            [opt[1] for opt in options], 
            title="Select Data Source"
        )
        
        if not source_choice:
            return
            
        source = next(opt[0] for opt in options if opt[1] == source_choice)

    if not input_data and source not in ["obsidian"]:
        input_data = UI.ask(f"Enter input for [{source}]").strip()
        if not input_data:
            return

    run_workflow(source, input_data)

def run_workflow(source, input_data):
    UI.clear()
    UI.header()
    UI.info(f"Starting Anki Automation Workflow (Source: {source})")
    
    steps_map = {
        "youtube":   {"fetch":10,"select_s":30,"select_v":20,"enrich":20,"audio":15,"organize":5},
        "obsidian":  {"fetch":20,"enrich":60,"audio":15,"organize":5},
        "situation": {"gen":40,"enrich":40,"audio":15,"organize":5},
    }
    
    ws_config = steps_map.get(source)
    if not ws_config: return

    total_points = sum(ws_config.values())

    with UI.progress() as progress:
        pbar = progress.add_task("[cyan]Overall Progress...", total=total_points)
        
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
            rpbar.set_description("Fetching YouTube Transcript...")
            import re
            v_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", input_data)
            if not v_id_match:
                UI.error("Could not find a valid YouTube ID.")
                return
            
            sentences = YouTubeFetcher.fetch_transcript(v_id_match.group(1), pbar=rpbar)
            if not sentences: return
            rpbar.update(ws_config["fetch"])

            rpbar.set_description("Selecting Sentences and Vocabulary...")
            from config import MODEL_VOCAB
            existing_vocab = AnkiConnector.get_existing_vocab_words(MODEL_VOCAB)
            
            data = {"source": input_data, "content": " ".join(sentences)}
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                fs = ex.submit(run_sentence_selection, data, pbar=rpbar, step_points=ws_config["select_s"])
                fv = ex.submit(run_vocabulary_selection, data, existing_vocab, pbar=rpbar, step_points=ws_config["select_v"])
                selected_sentences, selected_vocab = fs.result(), fv.result()

        elif source == "obsidian":
            rpbar.set_description("Fetching Obsidian Inbox Data...")
            obsidian_mgr = ObsidianManager()
            data = obsidian_mgr.fetch_inbox_content()
            if not data or (not data["vocab"] and not data["sentences"]):
                UI.info("No Obsidian data found to fetch.")
                return
            selected_sentences = {"sentences": data["sentences"]}
            selected_vocab = {"vocab": data["vocab"]}
            rpbar.update(ws_config["fetch"])

        elif source == "situation":
            rpbar.set_description("Generating Situation-based Content...")
            gen = generate_situation_content(input_data, pbar=rpbar, step_points=ws_config["gen"])
            if not gen: return
            selected_sentences = {"sentences": gen.get('sentences', [])}
            selected_vocab = {"vocab": gen.get('vocab', [])}

        def cli_inspector(enriched):
            UI.subheader("Final Data Inspection")
            if enriched.get("sentences"):
                UI.step(f"Sentences - {len(enriched['sentences'])} items")
                enriched["sentences"] = inspect_items(enriched["sentences"], lambda x: f"Sentence: {x.get('문장')}")
            if enriched.get("vocab"):
                UI.step(f"Vocabulary - {len(enriched['vocab'])} items")
                enriched["vocab"] = inspect_items(enriched["vocab"], lambda x: f"Word: {x.get('단어')}")
            return enriched

        rpbar.set_description("Adding and Enriching Notes...")
        if not run_note_completion(selected_sentences, selected_vocab, pbar=rpbar, 
                                   step_points=ws_config["enrich"], inspector_func=cli_inspector):
            UI.error("Error occurred during note addition.")
            return

        if source == "obsidian" and obsidian_mgr:
            rpbar.set_description("Clearing Obsidian Inbox...")
            obsidian_mgr.clear_processed_content()
            UI.success("Obsidian data cleared.")

        rpbar.set_description("Adding Audio...")
        AnkiTTSFiller.run_audio_addition(pbar=rpbar, step_points=ws_config["audio"])

        rpbar.set_description("Organizing Cards...")
        run_organizer(pbar=rpbar, step_points=ws_config["organize"])

    UI.print("All tasks completed successfully!", style="bold green")

def menu_add_notes():
    run_workflow_interactive()

def menu_organize():
    while True:
        UI.clear()
        UI.header()
        UI.subheader("Organize Notes")
        
        options = [
            ("1", "1. Fill Missing Audio"),
            ("2", "2. Auto-Fill Empty Fields (All Models)"),
            ("3", "3. Auto-Organize Cards (Deck Migration)"),
            ("4", "4. Remove Duplicate Cards"),
            ("b", "b. Back to Main Menu")
        ]
        
        choice_text = InteractiveSelector.select_one(
            [opt[1] for opt in options],
            title="Organize Notes"
        )
        
        if not choice_text or "Back to Main Menu" in choice_text:
            break
            
        choice = next(opt[0] for opt in options if opt[1] == choice_text)
        
        if choice == '1':
            UI.subheader("Fill Missing Audio")
            AnkiTTSFiller.run_audio_addition()
            UI.ask("Press Enter to continue", default="")
        elif choice == '2':
            UI.subheader("Auto-Fill Empty Fields")
            run_universal_field_completion()
            UI.ask("Press Enter to continue", default="")
        elif choice == '3':
            UI.subheader("Auto-Organize Cards")
            run_organizer()
            UI.ask("Press Enter to continue", default="")
        elif choice == '4':
            UI.subheader("Remove Duplicate Cards")
            clean_duplicates()
            UI.success("Duplicates removed.")
            UI.ask("Press Enter to continue", default="")

def menu_design():
    while True:
        UI.clear()
        UI.header()
        UI.subheader("Design Management")
        
        options = [
            ("export", "1. Export Design to JSON (Anki -> JSON)"),
            ("import", "2. Import Design from JSON (JSON -> Anki)"),
            ("b", "b. Back to Main Menu")
        ]
        
        choice_text = InteractiveSelector.select_one(
            [opt[1] for opt in options],
            title="Design Management"
        )
        
        if not choice_text or "Back to Main Menu" in choice_text:
            break
            
        choice = next(opt[0] for opt in options if opt[1] == choice_text)
        
        if choice == 'export':
            export_design()
            UI.ask("Press Enter to continue", default="")
        elif choice == 'import':
            import_design()
            UI.ask("Press Enter to continue", default="")

def menu_statistics():
    UI.clear()
    UI.header()
    UI.subheader("Deck Statistics Analysis")
    with UI.wait("Loading detailed statistics"):
        stats = get_deck_stats(fast_mode=False) # Full mode for the statistics menu
    if stats:
        columns = ["Deck Name", "New", "7d Retention"]
        rows = [[s['name'], str(s['new']), s['ret_7d']] for s in stats]
        UI.table("Detailed Deck Statistics", columns, rows)
    else:
        UI.error("Could not load statistics.")
    UI.ask("Press Enter to continue", default="")

def build_dashboard_panel():
    # FAST MODE: Only total and new cards
    stats = get_deck_stats(fast_mode=True)
    if not stats:
        return Panel(Text("Anki Offline", style="bold red", justify="center"), title="[bold white]Dashboard[/]", border_style="red")
    
    table = Table(box=None, header_style="bold magenta", expand=True)
    table.add_column("Deck", style="bold white")
    table.add_column("Total", justify="right", style="grey70")
    table.add_column("New", justify="right", style="cyan")
    table.add_column("Limit", justify="right", style="yellow")
    table.add_column("Today", justify="right", style="green")
    table.add_column("Rem.", justify="right", style="bold yellow")
    
    for s in stats:
        if s['name'] in ["[Root]", "listening"]: continue
        table.add_row(
            s['name'], 
            str(s['total']),
            str(s['new']), 
            f"{s.get('new_per_day', 0)}/d",
            str(s.get('reviews_today', 0)), 
            f"{s.get('exhaust_days', '∞')}d"
        )
        
    return Panel(
        Group(
            table,
            Text.from_markup("\n[italic grey50]Refreshed: " + os.popen("date +%H:%M:%S").read().strip() + "[/]")
        ),
        title="[bold white]Live Stats[/]", 
        border_style="bright_blue", 
        expand=True
    )

def build_system_info_panel():
    from config import SENTENCE_SELECTOR_MODEL, ANKI_URL, CURRENT_TARGET, OBSIDIAN_VAULT_PATH
    
    grid = Table.grid(expand=True)
    grid.add_column(ratio=2) # AI
    grid.add_column(ratio=2) # Anki
    grid.add_column(ratio=3) # Vault
    grid.add_column(ratio=3) # Keys
    
    ai = f"[cyan]AI:[/] {SENTENCE_SELECTOR_MODEL.split('-')[1]}" # Compact name
    anki = f"[green]Anki:[/] {CURRENT_TARGET}"
    vault = f"[magenta]Vault:[/] {OBSIDIAN_VAULT_PATH[-15:]}"
    keys = "[yellow]Shortcuts:[/] Q:Quit | Enter:Select"

    grid.add_row(ai, anki, vault, keys)
    
    return Panel(
        grid,
        title="[bold white]System Info[/]",
        border_style="bright_blue",
        padding=(0, 1)
    )

def interactive_menu():
    while True:
        UI.clear()
        UI.header()

        dashboard = build_dashboard_panel()
        sys_info = build_system_info_panel()

        options = [
            ("1", "Add Notes (YouTube, Situation, Obsidian)"),
            ("2", "Organize Notes (Audio, Fields, Migration)"),
            ("3", "Reinforce Leech Vocabulary (Today/Top)"),
            ("4", "Manage Card Design (Import/Export)"),
            ("5", "Analyze Deck Statistics"),
            ("q", "Quit")
        ]

        choice_text = InteractiveSelector.select_one(
            [opt[1] for opt in options], 
            title="Anki Manager CLI Main Menu",
            side_panel=dashboard,
            bottom_panel=sys_info
        )

        if not choice_text or choice_text == "Quit":

            UI.info("Exiting program.")
            break

        choice = next(opt[0] for opt in options if opt[1] == choice_text)

        if choice == '1':
            run_workflow_interactive()
        elif choice == '2':
            menu_organize()
        elif choice == '3':
            LeechResolver.resolve()
        elif choice == '4':
            menu_design()
        elif choice == '5':
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
