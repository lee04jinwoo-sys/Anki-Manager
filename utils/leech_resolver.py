import concurrent.futures
from integrations.anki_connect import AnkiConnector
from utils.ui import UI
from utils.cli_selector import InteractiveSelector
from core.completer import NoteCompleter
from config import MODEL_VOCAB, MODEL_SENTENCE, DECK_SENTENCE

class LeechResolver:
    @staticmethod
    def get_missed_today():
        # Search for cards rated 1 (Again) today
        query = f'note:"{MODEL_VOCAB}" rated:1:1'
        card_ids = AnkiConnector.invoke("findCards", query=query)
        if not card_ids:
            return []
        
        cards_info = AnkiConnector.invoke("cardsInfo", cards=card_ids)
        seen_notes = set()
        candidates = []
        
        for c in cards_info:
            nid = c['note']
            if nid in seen_notes: continue
            
            word = c['fields']['단어']['value']
            lapses = c.get('lapses', 0)
            reps = c.get('reps', 0)
            
            candidates.append({
                "id": nid,
                "word": word,
                "lapses": lapses,
                "reps": reps
            })
            seen_notes.add(nid)
            
        return candidates

    @staticmethod
    def get_top_lapses(limit=30):
        query = f'note:"{MODEL_VOCAB}"'
        card_ids = AnkiConnector.invoke("findCards", query=query)
        if not card_ids:
            return []
        
        cards_info = AnkiConnector.invoke("cardsInfo", cards=card_ids)
        
        note_stats = {} # nid -> {word, lapses, reps}
        for c in cards_info:
            nid = c['note']
            lapses = c.get('lapses', 0)
            reps = c.get('reps', 0)
            word = c['fields']['단어']['value']
            
            if nid not in note_stats or lapses > note_stats[nid]['lapses']:
                note_stats[nid] = {
                    "word": word,
                    "lapses": lapses,
                    "reps": reps
                }
        
        # Sort by lapses, then reps
        sorted_notes = sorted(
            note_stats.items(), 
            key=lambda x: (x[1]['lapses'], x[1]['reps']), 
            reverse=True
        )
        
        return [
            {
                "id": nid, 
                "word": info['word'], 
                "lapses": info['lapses'], 
                "reps": info['reps']
            } 
            for nid, info in sorted_notes[:limit]
        ]

    @staticmethod
    def resolve():
        UI.clear()
        UI.header("Leech Resolver")
        
        options = [
            ("1", "1. Vocabulary Missed Today"),
            ("2", "2. Top Historical Leech Vocabulary"),
            ("b", "b. Back")
        ]
        
        choice_text = InteractiveSelector.select_one([opt[1] for opt in options], title="Select Mode")
        if not choice_text or "Back" in choice_text:
            return

        mode = next(opt[0] for opt in options if opt[1] == choice_text)
        
        candidates = []
        with UI.wait("Searching for leeches"):
            if mode == "1":
                candidates = LeechResolver.get_missed_today()
            else:
                candidates = LeechResolver.get_top_lapses()

        if not candidates:
            UI.error("No leech candidates found in 'English Vocabulary'.")
            UI.ask("Press Enter to continue")
            return

        # Selection - Show both Lapses and Total Reps for context
        display_items = [
            f"{c['word']} [dim](Lapses: {c['lapses']}, Reps: {c['reps']})[/]" 
            for c in candidates
        ]
        selector = InteractiveSelector(display_items, title="Select words to reinforce", multi_select=True)
        selected_indices = selector.run_indices()
        
        if not selected_indices:
            return

        selected_words = [candidates[i]['word'] for i in selected_indices]
        
        UI.info(f"Generating reinforcement sentences for {len(selected_words)} words...")
        
        completer = NoteCompleter()
        
        results = []
        with UI.progress() as progress:
            task = progress.add_task("[cyan]AI Generating...", total=len(selected_words))
            
            def process_word(word):
                prompt = (
                    f"단어 '{word}'의 의미를 가장 잘 보여주는 실용적인 영어 예문 하나를 만드세요.\n"
                    f"반드시 다음 JSON 형식을 따르세요: {{ \"문장\": \"...\", \"해설\": \"...\" }}"
                )
                res = completer._generate(prompt)
                progress.update(task, advance=1)
                return res

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(process_word, w) for w in selected_words]
                for future in concurrent.futures.as_completed(futures):
                    res = future.result()
                    if res:
                        results.append(res)

        # Add to Anki
        added_count = 0
        card_ids_to_schedule = []
        
        for res in results:
            if not res.get("문장"): continue
            try:
                # Add note to Anki
                nid = AnkiConnector.add_note(DECK_SENTENCE, MODEL_SENTENCE, {
                    "문장": res["문장"],
                    "해설": res["해설"]
                }, tags=["leech_reinforcement"])
                
                # Get card IDs for this note to reschedule
                cids = AnkiConnector.invoke("findCards", query=f"nid:{nid}")
                card_ids_to_schedule.extend(cids)
                added_count += 1
            except Exception as e:
                if "duplicate" in str(e).lower():
                    # If duplicate, we might still want to reschedule it? 
                    # But the user asked to "set up" which implies adding/updating.
                    # For simplicity, if it's already there, we just skip.
                    pass
                else:
                    UI.error(f"Error adding note: {e}")

        if card_ids_to_schedule:
            # Set due to tomorrow (1 day from now)
            try:
                AnkiConnector.invoke("setSpecificDueDate", cards=card_ids_to_schedule, days=1)
                UI.success(f"Added {added_count} sentences. Scheduled for review tomorrow.")
            except Exception as e:
                UI.warn(f"Sentences added but failed to reschedule: {e}")
        else:
            UI.info("No new sentences were added (possibly all duplicates).")
            
        UI.ask("Press Enter to continue")
