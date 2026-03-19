import requests
import json
import time
import re
import html  # [추가됨] 특수문자 처리를 위한 라이브러리
import os

# ================= [1. 설정 영역] =================
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

ANKI_URL = "http://localhost:8765"
MODEL_VOCAB = "English Vocabulary"

FIELD_WORD = "단어"
FIELD_DESC = "설명"
# ===============================================

def invoke(action, **params):
    try:
        response = requests.post(ANKI_URL, json={"action": action, "version": 6, "params": params}).json()
        if 'error' in response and response['error']:
            print(f"   ❌ AnkiConnect 에러: {response['error']}")
            return None
        return response['result']
    except Exception as e:
        print(f"   ❌ Anki 연결 오류: {e}")
        return None

def get_nuance_from_gemini(words):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GOOGLE_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    # [System Instruction] - 모델의 기본 동작 정의
    system_instruction = (
        "너는 최고의 언어학 전문가이자 영어 교육자야. 다음 영단어들의 의미, 뉘앙스, "
        "유의어와의 미묘한 차이, 콜로케이션을 한국어로 상세히 설명해."
        "\n\n[제약 조건]\n"
        "1. 반드시 순수한 JSON 객체만 반환하라.\n"
        "2. HTML 태그(<b>, <br> 등)는 절대 사용하지 마라.\n"
        "3. 각 단어에 대한 설명은 한국어 공백 포함 300자 내외로 매우 상세하게 작성하라.\n"
        "4. 마크다운 기호(```json)나 서론, 결론은 생략하고 순수 JSON 데이터만 출력하라."
    )

    # [User Prompt] - 구체적인 작업 지시
    prompt_text = (
        f"대상 단어: {json.dumps(words)}"
        
    )

    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.4 # 창의성과 정확성의 균형 (분량 확보를 위해 약간 올림)
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        result_json = response.json()
        
        # 텍스트 추출 및 JSON 파싱
        raw_text = result_json['candidates'][0]['content']['parts'][0]['text']
        return json.loads(raw_text)

    except Exception as e:
        print(f"\n❌ [API 에러]: {str(e)}")
        return None

def update_anki_nuance():
    # 1. 대상 카드 찾기
    query = f'note:"{MODEL_VOCAB}"'
    print(f"🔍 '{MODEL_VOCAB}' 유형의 모든 카드를 스캔 중...")
    
    note_ids = invoke("findNotes", query=query)
    if not note_ids:
        print("❌ 카드를 찾지 못했습니다.")
        return

    notes_info = invoke("notesInfo", notes=note_ids)
    
    # 2. 업데이트할 목록 만들기
    to_update = []
    skipped_count = 0
    
    for note in notes_info:
        fields = note.get('fields', {})
        
        if FIELD_WORD in fields and FIELD_DESC in fields:
            # 이미 설명이 있으면 건너뜀
            existing_desc = fields[FIELD_DESC]['value'].strip()
            if existing_desc:
                skipped_count += 1
                continue
            
            raw_word = fields[FIELD_WORD]['value']
            
            # [수정된 부분] HTML 엔티티 디코딩 (&#x27; -> ')
            clean_word = html.unescape(re.sub('<[^<]+?>', '', raw_word)).strip()
            
            if clean_word:
                to_update.append({"id": note['noteId'], "word": clean_word})

    total_to_update = len(to_update)
    print(f"📊 총 {len(note_ids)}개 중 {skipped_count}개는 이미 내용이 있어 건너뜁니다.")
    print(f"🚀 업데이트 예정 카드: {total_to_update}개\n")

    if total_to_update == 0:
        print("✅ 모든 카드에 이미 설명이 채워져 있습니다!")
        return

    # 3. 배치 처리
    batch_size = 10
    for i in range(0, total_to_update, batch_size):
        batch = to_update[i:i+batch_size]
        words_only = [item['word'] for item in batch]
        
        print(f"🔄 [{i+1}/{total_to_update}] 처리 중: {words_only[0]} ... (총 {len(batch)}개)")
        
        nuances = get_nuance_from_gemini(words_only)
        
        if nuances:
            for item in batch:
                original_word = item['word']
                # 매칭 로직 (대소문자 및 인코딩 문제 해결됨)
                content = (nuances.get(original_word) or 
                           nuances.get(original_word.lower()) or 
                           nuances.get(original_word.capitalize()) or
                           nuances.get(original_word.title()))
                
                if content:
                    print(f"   👀 [생성] {original_word}: {content[:40]}...") 

                    res = invoke("updateNoteFields", note={
                        "id": item['id'],
                        "fields": {FIELD_DESC: content}
                    })
                    if res is None:
                        print(f"   ✨ 저장 완료")
                else:
                    print(f"   ⚠️ 매칭 실패: '{original_word}'")
        else:
            print(f"   ❌ 이 배치는 API 응답 오류로 건너뜁니다.")
        
        time.sleep(1.0)

    print(f"\n✨ 모든 작업이 완료되었습니다!")

if __name__ == "__main__":
    update_anki_nuance()