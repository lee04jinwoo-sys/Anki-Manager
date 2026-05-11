import concurrent.futures
from integrations.anki_connect import AnkiConnector
from utils.ui import UI
from utils.cli_selector import InteractiveSelector
from core.completer import NoteCompleter
from integrations.audio import AnkiTTSFiller
from utils.organizer import run_organizer
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
        UI.header("Leech 단어 강화")
        
        options = [
            ("1", "1. 오늘 틀린 단어"),
            ("2", "2. 역대 최다 오답 단어"),
            ("b", "b. 뒤로 가기")
        ]
        
        choice_text = InteractiveSelector.select_one([opt[1] for opt in options], title="모드를 선택하세요")
        if not choice_text or "뒤로 가기" in choice_text:
            return

        mode = next(opt[0] for opt in options if opt[1] == choice_text)
        
        candidates = []
        with UI.wait("리치 단어 검색 중..."):
            if mode == "1":
                candidates = LeechResolver.get_missed_today()
            else:
                candidates = LeechResolver.get_top_lapses()

        if not candidates:
            UI.error("검색된 리치 단어가 없습니다.")
            UI.ask("계속하려면 Enter를 누르세요")
            return

        # Selection - Show both Lapses and Total Reps for context
        display_items = [
            f"{c['word']} [dim](Lapses: {c['lapses']}, Reps: {c['reps']})[/]" 
            for c in candidates
        ]
        selector = InteractiveSelector(display_items, title="강화할 단어를 선택하세요", multi_select=True)
        selected_indices = selector.run_indices()
        
        if not selected_indices:
            return

        selected_words = [candidates[i]['word'] for i in selected_indices]
        selected_note_ids = [candidates[i]['id'] for i in selected_indices]
        
        UI.info(f"예문 생성 중... ({len(selected_words)} 단어)...")
        
        completer = NoteCompleter()
        
        results = []
        with UI.progress() as progress:
            task = progress.add_task(f"[cyan]해결 중...", total=len(selected_words))
            
            def process_word(word):
                prompt = (
                    f"단어 '{word}'의 의미를 가장 잘 보여주는 실용적인 영어 예문 하나를 만드세요.\n"
                    f"중요: 단어가 'play with A'처럼 A, B, V 플레이스홀더를 포함한다면, 문장에서는 이를 실제 상황에 맞는 단어로 반드시 대체하세요.\n"
                    f"반드시 다음 JSON 형식을 따르세요: {{ \"문장\": \"...\", \"해설\": \"...\" }}\n"
                    f"'해설' 필드에는 군더더기 없이 자연스러운 한국어 번역만 작성하세요."
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
        
        for res in results:
            if not res.get("문장"): continue
            try:
                # Add note to Anki
                AnkiConnector.add_note(DECK_SENTENCE, MODEL_SENTENCE, {
                    "문장": res["문장"],
                    "해설": res["해설"]
                }, tags=["leech_reinforcement"])
                
                added_count += 1
            except Exception as e:
                if "duplicate" in str(e).lower():
                    pass
                else:
                    UI.error(f"Error: {e}")

        if added_count > 0:
            UI.success(f"{added_count}개의 새로운 문장 카드가 추가되었습니다.")
            
            # Add audio and organize cards
            with UI.wait("오디오 추가 및 카드 정리 중..."):
                AnkiTTSFiller.run_audio_addition()
                run_organizer()
        else:
            UI.info("추가된 새로운 문장이 없습니다.")

        # If Top Leech mode, reset the original cards
        if mode == "2" and selected_note_ids:
            try:
                # Find all cards associated with these notes
                all_card_ids = []
                for nid in selected_note_ids:
                    cids = AnkiConnector.invoke("findCards", query=f"nid:{nid}")
                    all_card_ids.extend(cids)
                
                if all_card_ids:
                    AnkiConnector.invoke("forgetCards", cards=all_card_ids)
                    UI.info(f"🔄 {len(all_card_ids)}개의 기존 리치 카드를 초기화했습니다.")
            except Exception as e:
                UI.error(f"카드 초기화 실패: {e}")
            
        UI.ask("계속하려면 Enter를 누르세요")
