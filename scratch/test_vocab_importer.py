import sys
import os
import re
import json
import requests
import random

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.anki_connect import AnkiConnector
from core.completer import run_note_completion
from utils.vocab_importer import download_file_content, parse_vocab_file
from config import MODEL_VOCAB

def main():
    print("🧪 [TEST] GitHub Vocabulary Importer 자동 E2E 테스트 시작...")
    
    # 1. Download & Clean Parse
    url = "https://raw.githubusercontent.com/vatsalsaglani/gre-vocab/master/words_meanings.json"
    print(f"1. 깃허브 프리셋 파일 다운로드 및 파싱 시도 (URL: {url})...")
    file_bytes = download_file_content(url)
    if not file_bytes:
        print("❌ 파일 다운로드 실패")
        return
        
    parsed_words = parse_vocab_file(file_bytes, "words_meanings.json")
    print(f"   - 파싱 성공: 총 {len(parsed_words)}개 단어 로드됨")
    
    if not parsed_words:
        print("❌ 단어 파싱 결과 없음")
        return
        
    # 2. Local Anki Set Difference (Duplicate Filter)
    print("2. 내 안키 단어장 로드 및 로컬 중복 필터링...")
    try:
        existing_vocab = AnkiConnector.get_existing_vocab_words(MODEL_VOCAB)
        existing_set = {w.lower().strip() for w in existing_vocab}
        print(f"   - 기존 안키 내 단어 수: {len(existing_vocab)}개")
    except Exception as e:
        print(f"❌ Anki 연결 실패: {e}")
        return
        
    new_words = []
    for item in parsed_words:
        word = item.get("word", "").strip()
        clean_word = re.sub('<[^<]+?>', '', word).strip()
        if clean_word and clean_word.lower() not in existing_set:
            item["word"] = clean_word
            new_words.append(item)
            
    print(f"   - 중복 필터링 완료: 신규 미등록 단어 {len(new_words)}개")
    if not new_words:
        print("⚠️ 가져올 새로운 단어가 없습니다.")
        return

    # 3. Direct Selection (select 3 sample words for fast test verification)
    test_count = 3
    print(f"3. 중복 제거된 신규 단어에서 상위 {test_count}개 직접 추출...")
    sampled_words = new_words[:test_count]
    print(f"   - 추출 완료: {sampled_words}")
    
    # 4. Enrich & Insert into Anki (E2E Integration)
    print("4. NoteCompleter 연동을 통한 뜻/예문 보강 및 안키 저장...")
    completer_vocab_list = []
    for item in sampled_words:
        completer_vocab_list.append({
            "단어": item["word"],
            "뜻": item["meaning"]
        })
        
    sentences_data = {"sentences": []}
    vocab_data = {"vocab": completer_vocab_list}
    
    # Insert with note completions
    success, added_s, added_v = run_note_completion(sentences_data, vocab_data)
    
    if success:
        print(f"🎉 [TEST SUCCESS] 성공적으로 {len(added_v)}개의 카드가 보강 및 안키에 저장되었습니다!")
        print(f"   - 추가된 단어: {added_v}")
        
        print("5. [TEST] 후속 자동화 정리 실행...")
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
            print("✨ [TEST SUCCESS] 모든 후속 자동화 테스트 완료!")
        except Exception as e:
            print(f"❌ 후속 자동화 처리 중 에러 발생: {e}")
    else:
        print("❌ 보강 및 안키 저장 중 실패")

if __name__ == "__main__":
    main()
