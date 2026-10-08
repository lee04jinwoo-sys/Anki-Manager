import os
import csv
import re
import requests
from integrations.anki_connect import AnkiConnector
from utils.cli_selector import InteractiveSelector
from utils.ui import UI
from core.completer import run_note_completion
from config import MODEL_VOCAB

# Remote CSV source and local cache path
SCRIPT_URL = "https://raw.githubusercontent.com/declare-lab/MELD/master/data/MELD/train_sent_emo.csv"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CACHE_FILE = os.path.join(CACHE_DIR, "friends_script.csv")

def ensure_script_downloaded():
    """Ensures the Friends transcript dataset is cached locally"""
    if os.path.exists(CACHE_FILE):
        return True
        
    os.makedirs(CACHE_DIR, exist_ok=True)
    UI.info("📡 Friends 전체 대본 데이터셋 최초 다운로드 중 (약 1.8MB)...")
    
    try:
        headers = {"User-Agent": "AnkiManagerCLI/1.0"}
        response = requests.get(SCRIPT_URL, headers=headers, timeout=20)
        response.raise_for_status()
        
        with open(CACHE_FILE, "wb") as f:
            f.write(response.content)
            
        UI.success("✅ 대본 다운로드 및 캐싱 완료!")
        return True
    except Exception as e:
        UI.error(f"대본 다운로드 실패: {e}")
        return False

def load_episodes_from_csv():
    """Loads all lines from cached CSV and returns a structured map of season -> episode -> list of utterances"""
    if not ensure_script_downloaded():
        return None
        
    script_data = {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # MELD columns: Utterance, Speaker, Emotion, Sentiment, Season, Episode, ...
                try:
                    season = int(row.get("Season", 0))
                    episode = int(row.get("Episode", 0))
                except ValueError:
                    continue
                    
                utterance = row.get("Utterance", "").strip()
                speaker = row.get("Speaker", "").strip()
                
                if not utterance or season == 0 or episode == 0:
                    continue
                    
                if season not in script_data:
                    script_data[season] = {}
                if episode not in script_data[season]:
                    script_data[season][episode] = []
                    
                script_data[season][episode].append({
                    "speaker": speaker,
                    "text": utterance
                })
        return script_data
    except Exception as e:
        UI.error(f"대본 데이터 로드 중 오류: {e}")
        return None

def run_tv_show_importer_flow():
    """Interactive flow to select an episode from Friends and import vocabularies"""
    UI.clear()
    UI.header("🎬 Friends 미드 대본 영어 어휘 가져오기")
    
    # 1. Load data
    with UI.wait("Friends 대본 데이터셋 로드 중..."):
        script_data = load_episodes_from_csv()
        
    if not script_data:
        UI.error("대본 데이터를 불러올 수 없습니다.")
        UI.ask("계속하려면 Enter를 누르세요", default="")
        return
        
    # 2. Select Season
    seasons = sorted(list(script_data.keys()))
    season_options = [f"시즌 {s}" for s in seasons]
    
    selected_season_text = InteractiveSelector.select_one(
        season_options,
        title="가져올 시즌(Season)을 선택하세요"
    )
    if not selected_season_text:
        return
        
    season = seasons[season_options.index(selected_season_text)]
    
    # 3. Select Episode
    episodes = sorted(list(script_data[season].keys()))
    episode_options = [f"에피소드 {e}" for e in episodes]
    
    selected_episode_text = InteractiveSelector.select_one(
        episode_options,
        title=f"Friends 시즌 {season}의 에피소드를 선택하세요"
    )
    if not selected_episode_text:
        return
        
    episode = episodes[episode_options.index(selected_episode_text)]
    
    utterances = script_data[season][episode]
    UI.success(f"🎬 시즌 {season} 에피소드 {episode} 로드 완료! (총 {len(utterances)}개 대사)")
    
    # 4. Get Existing Vocabulary from Anki to avoid duplicates
    with UI.wait("내 안키 단어장 로드 및 중복 필터링 중..."):
        try:
            existing_vocab = AnkiConnector.get_existing_vocab_words(MODEL_VOCAB)
            existing_set = {w.lower().strip() for w in existing_vocab}
        except Exception as e:
            UI.error(f"Anki 연결 실패: {e}")
            UI.ask("계속하려면 Enter를 누르세요", default="")
            return
            
    # Extract unique words from utterances
    # Simple regex to split words
    word_pattern = re.compile(r"\b[a-zA-Z]{3,15}\b")  # words of length 3-15
    candidate_words = {}
    
    for idx, ut in enumerate(utterances):
        text = ut["text"]
        words = word_pattern.findall(text)
        for w in words:
            w_lower = w.lower()
            if w_lower not in existing_set:
                # Keep track of the sentence context as example sentence
                if w_lower not in candidate_words:
                    candidate_words[w_lower] = {
                        "word": w_lower,
                        "example": f"\"{text}\" (Speaker: {ut['speaker']})"
                    }
                    
    new_words = list(candidate_words.values())
    
    UI.print(f"  - 기존 내 안키 단어: {len(existing_vocab)}개")
    UI.print(f"  - 대사 속 신규 단어: {len(new_words)}개 검출", style="bold green")
    
    if not new_words:
        UI.info("새로 가져올 수 있는 미등록 단어가 없습니다.")
        UI.ask("계속하려면 Enter를 누르세요", default="")
        return
        
    # 5. Ask how many to import
    count_str = UI.ask(f"❓ 이 중 몇 개의 단어를 가져오시겠습니까? (기본값: 15, 최대: {len(new_words)})").strip()
    try:
        import_count = int(count_str) if count_str else 15
    except:
        import_count = 15
        
    import_count = max(1, min(import_count, len(new_words)))
    
    # Take first N words
    sampled_words = new_words[:import_count]
    
    # 6. Final inspect and confirm
    display_sampled = [f"{w['word']} (컨텍스트: {w['example'][:40]}...)" for w in sampled_words]
    
    selector = InteractiveSelector(
        display_sampled,
        title="최종 단어 선택 (가져올 단어를 체크하세요)",
        help_text="SPACE: 토글 | A: 전체선택 | N: 선택해제 | C: 확정 | Q: 취소"
    )
    selected_indices = selector.run_indices()
    
    if not selected_indices:
        UI.info("작업이 취소되었습니다.")
        UI.ask("계속하려면 Enter를 누르세요", default="")
        return
        
    final_vocab_list = [sampled_words[idx] for idx in selected_indices]
    
    # Format structure for NoteCompleter: 'word' -> '단어', 'example' -> '예문'
    completer_vocab_list = []
    for item in final_vocab_list:
        completer_vocab_list.append({
            "단어": item["word"],
            "뜻": ""  # AI note completion will automatically generate accurate meaning
        })
        
    # 7. Enrich via Gemini & Insert
    UI.info(f"선택된 {len(completer_vocab_list)}개 단어 보강 및 안키 추가 작업 시작...")
    
    sentences_data = {"sentences": []}
    vocab_data = {"vocab": completer_vocab_list}
    
    # Override default prompts temporarily? No, standard completion prompt works great.
    success, added_s, added_v = run_note_completion(sentences_data, vocab_data)
    
    if success:
        UI.success(f"🎉 총 {len(added_v)}개의 카드가 성공적으로 보강 및 추가되었습니다!")
        
        # 8. Post-processing automated steps (Audio, Organize, Cluster)
        UI.info("🔊 누락된 오디오(TTS) 생성 및 추가 중...")
        try:
            from integrations.audio import AnkiTTSFiller
            AnkiTTSFiller.run_audio_addition()
        except Exception as e:
            UI.error(f"오디오 추가 오류: {e}")
            
        UI.info("📁 카드를 알맞은 덱으로 자동 정리 중...")
        try:
            from utils.organizer import run_organizer
            run_organizer()
        except Exception as e:
            UI.error(f"덱 정리 오류: {e}")
            
        UI.info("🔗 AI 유의어 맵 업데이트 및 클러스터링 중...")
        try:
            from utils.cluster import run_clustering
            run_clustering()
        except Exception as e:
            UI.error(f"유의어 업데이트 오류: {e}")
            
        UI.success("✨ 모든 후속 자동화 정리가 완료되었습니다!")
    else:
        UI.error("보강 작업 중 오류가 발생했습니다.")
        
    UI.ask("계속하려면 Enter를 누르세요", default="")
