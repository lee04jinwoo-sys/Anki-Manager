import sys
import os
import re

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.anki_connect import AnkiConnector
from core.completer import run_note_completion
from utils.tv_show_importer import ensure_script_downloaded, load_episodes_from_csv
from config import MODEL_VOCAB

def main():
    print("🧪 [TEST] Friends 미드 대본 영어 어휘 가져오기 자동 E2E 테스트 시작...")
    
    # 1. Download Script (if not cached)
    print("1. Friends 대본 데이터셋 캐시 및 다운로드 체크...")
    if not ensure_script_downloaded():
        print("❌ 대본 다운로드 및 캐시 생성 실패")
        return
        
    # 2. Parse CSV
    print("2. 로컬 캐시에서 대본 파싱 및 로드...")
    script_data = load_episodes_from_csv()
    if not script_data:
        print("❌ 대본 데이터 로드 실패")
        return
        
    print(f"   - 시즌 목록: {list(script_data.keys())}")
    
    # Target Season 1, Episode 1 for testing
    season = 1
    episode = 1
    
    if season not in script_data or episode not in script_data[season]:
        print(f"❌ 시즌 {season} 에피소드 {episode} 대본이 존재하지 않습니다.")
        return
        
    utterances = script_data[season][episode]
    print(f"   - Friends 시즌 {season} 에피소드 {episode} 로드 성공 (대사 수: {len(utterances)}개)")
    
    # 3. Local Anki Set Difference (Duplicate Filter)
    print("3. 내 안키 단어장 로드 및 로컬 중복 필터링...")
    try:
        existing_vocab = AnkiConnector.get_existing_vocab_words(MODEL_VOCAB)
        existing_set = {w.lower().strip() for w in existing_vocab}
        print(f"   - 기존 안키 내 단어 수: {len(existing_vocab)}개")
    except Exception as e:
        print(f"❌ Anki 연결 실패: {e}")
        return
        
    word_pattern = re.compile(r"\b[a-zA-Z]{4,15}\b")  # words of length 4-15 (more practical words)
    candidate_words = {}
    
    for ut in utterances:
        text = ut["text"]
        words = word_pattern.findall(text)
        for w in words:
            w_lower = w.lower()
            if w_lower not in existing_set:
                if w_lower not in candidate_words:
                    candidate_words[w_lower] = {
                        "word": w_lower,
                        "example": f"\"{text}\" (Speaker: {ut['speaker']})"
                    }
                    
    new_words = list(candidate_words.values())
    print(f"   - 중복 필터링 완료: 신규 미등록 단어 {len(new_words)}개 검출")
    if not new_words:
        print("⚠️ 가져올 새로운 단어가 없습니다.")
        return
        
    # 4. Extract sample words (3 words)
    test_count = 3
    sampled_words = new_words[:test_count]
    print(f"4. 테스트용 상위 {test_count}개 단어 발췌...")
    print(f"   - 발췌 목록: {[w['word'] for w in sampled_words]}")
    
    completer_vocab_list = []
    for item in sampled_words:
        completer_vocab_list.append({
            "단어": item["word"],
            "뜻": ""  # Run completer
        })
        
    # 5. Enrich & Insert into Anki (NoteCompleter Integration)
    print("5. NoteCompleter 연동을 통한 뜻/예문 보강 및 안키 저장...")
    sentences_data = {"sentences": []}
    vocab_data = {"vocab": completer_vocab_list}
    
    success, added_s, added_v = run_note_completion(sentences_data, vocab_data)
    
    # 6. Post-processing Automated Steps (E2E Integration)
    if success:
        print(f"🎉 [TEST SUCCESS] 성공적으로 {len(added_v)}개의 카드가 보강 및 안키에 저장되었습니다!")
        print(f"   - 추가된 단어: {added_v}")
        
        print("6. 후속 자동화 정리 실행...")
        try:
            from integrations.audio import AnkiTTSFiller
            from utils.organizer import run_organizer
            from utils.cluster import run_clustering
            
            print("   - 오디오(TTS) 생성 및 추가...")
            AnkiTTSFiller.run_audio_addition()
            print("   - 덱 자동 정렬 및 정리...")
            run_organizer()
            print("   - AI 유의어 맵 업데이트...")
            run_clustering()
            print("✨ [TEST SUCCESS] 프렌즈 대본 수집 E2E 자동 테스트 완료!")
        except Exception as e:
            print(f"❌ 후속 자동화 처리 중 에러 발생: {e}")
    else:
        print("❌ 보강 및 안키 저장 중 실패")

if __name__ == "__main__":
    main()
