import requests
import json
import html
import re
import csv

# ================= [설정 영역] =================
ANKI_URL = "http://localhost:8765"
TARGET_NOTE_TYPE = "English Vocabulary"
# ===============================================

def invoke(action, **params):
    """AnkiConnect API 호출 함수"""
    try:
        response = requests.post(ANKI_URL, json={"action": action, "version": 6, "params": params}).json()
        if 'error' in response and response['error']:
            print(f"❌ AnkiConnect 에러: {response['error']}")
            return None
        return response.get('result')
    except Exception as e:
        print(f"❌ Anki 연결 오류: {e}")
        return None

def write_to_csv(cards):
    if not cards:
        return

    filename = "leech_cards.csv"
    # 필드명 순서 확보를 위해 첫 번째 카드의 필드 키를 사용
    fieldnames = list(cards[0].get('fields', {}).keys())
    
    header = ['Card ID', 'Deck', 'Lapses', 'Reps', 'Leech Ratio'] + fieldnames

    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for card in cards:
            lapses = card.get('lapses', 0)
            reps = card.get('reps', 0)
            leech_ratio = (lapses / reps) if reps > 0 else 0
            
            row = [
                card.get('cardId'),
                card.get('deckName'),
                lapses,
                reps,
                f"{leech_ratio:.2%}"
            ]
            
            card_fields = card.get('fields', {})
            for fieldname in fieldnames:
                # 필드 값에서 HTML 태그 제거
                raw_value = card_fields.get(fieldname, {}).get('value', '')
                clean_value = html.unescape(re.sub('<[^<]+?>', '', raw_value)).strip()
                row.append(clean_value)
            
            writer.writerow(row)
            
    print(f"\n✅ 상위 {len(cards)}개 카드를 '{filename}' 파일로 저장했습니다.")


def main():
    # 1. 특정 덱(하위 포함)에서 망각 횟수 8회 이상인 카드 검색
    # Anki 쿼리 문법: deck:"이름*" (와일드카드를 사용하여 하위 덱 모두 포함)
    query = f'note:"{TARGET_NOTE_TYPE}"'
    print(f"🔍 검색 쿼리 실행 중: [{query}]")
    
    card_ids = invoke("findCards", query=query)
    
    if card_ids is None:
        return
    if not card_ids:
        print(f"✅ '{TARGET_NOTE_TYPE}' 노트 타입의 카드를 찾을 수 없습니다.")
        return

    print(f"🚨 총 {len(card_ids)}개의 카드가 발견되었습니다. 데이터를 불러옵니다...\n")

    # 2. 검색된 카드의 상세 정보 조회
    cards_info = invoke("cardsInfo", cards=card_ids)
    
    if not cards_info:
        print("❌ 카드 상세 정보를 불러오지 못했습니다.")
        return

    # (망각 + 복습) 횟수가 8 이상인 카드만 필터링
    filtered_cards = [
        card for card in cards_info 
        if (card.get('lapses', 0) + card.get('reps', 0)) >= 8
    ]

    if not filtered_cards:
        print("✅ (망각+복습)이 8회 이상인 카드가 없습니다.")
        return


    # 망각 비율(lapses/reps) 계산 및 내림차순 정렬
    def get_leech_ratio(card):
        lapses = card.get('lapses', 0)
        reps = card.get('reps', 0)
        if reps == 0:
            return 0
        return lapses / reps

    filtered_cards.sort(key=get_leech_ratio, reverse=True)
    
    # 상위 10개 카드만 선택
    top_10_cards = filtered_cards[:10]

    # 3. 데이터 파싱 및 출력
    print("-" * 80)
    print(f"🏆 망각 비율 상위 {len(top_10_cards)}개 카드 🏆")
    print("-" * 80)

    for idx, card in enumerate(top_10_cards, 1):
        card_id = card.get('cardId')
        lapses = card.get('lapses', 0)
        reps = card.get('reps', 0)
        deck_name = card.get('deckName', 'Unknown')
        leech_ratio = get_leech_ratio(card)
        
        # 필드 데이터 추출
        fields = card.get('fields', {})
        if fields:
            # 일반적으로 첫 번째 필드가 앞면(단어/문장) 역할
            first_field_name = list(fields.keys())[0]
            raw_text = fields[first_field_name].get('value', '')
            # HTML 태그 제거 및 특수문자 디코딩
            clean_text = html.unescape(re.sub('<[^<]+?>', '', raw_text)).strip()
            # 텍스트가 너무 길면 자르기 (콘솔 출력용)
            display_text = clean_text[:60] + "..." if len(clean_text) > 60 else clean_text
        else:
            first_field_name = "N/A"
            display_text = "내용 없음"

        print(f"[{idx:02d}] 비율: {leech_ratio:.2%} (망각: {lapses} / 복습: {reps})")
        print(f"    덱: {deck_name}")
        print(f"    내용({first_field_name}): {display_text}")
        print("-" * 80)

    # CSV 파일로 저장
    write_to_csv(top_10_cards)

if __name__ == "__main__":
    main()