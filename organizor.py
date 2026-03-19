import json
import requests
from config import ORGANIZER_RULES, ANKI_URL

def _print(pbar, *args, **kwargs):
    if pbar:
        pbar.write(" ".join(map(str, args)), **kwargs)
    else:
        print(*args, **kwargs)

def invoke(action, **params):
    """AnkiConnect 로컬 서버에 API 요청을 보내는 함수"""
    try:
        response = requests.post(ANKI_URL, json={"action": action, "version": 6, "params": params}).json()
        if 'error' in response and response['error']:
            raise Exception(response['error'])
        return response['result']
    except Exception as e:
        raise e

def run_organizer(pbar=None, step_points=0):
    rules = ORGANIZER_RULES
    total_moved_count = 0
    step_amount = step_points / len(rules) if (step_points > 0 and len(rules) > 0) else 0

    for rule in rules:
        original_query = rule["query"]
        target_deck = rule["target_deck"]
        
        exclude_query = f'-deck:"{target_deck}"'
        full_query = f"{original_query} {exclude_query}"
        
        _print(pbar, f"규칙 확인 중: {original_query}")
        _print(pbar, f" -> 목적지 덱: {target_deck}")
        
        try:
            card_ids = invoke('findCards', query=full_query)
            
            if not card_ids:
                _print(pbar, f" -> 이동할 카드가 없습니다 (모든 카드가 제 위치에 있습니다).\n")
                if pbar and step_amount > 0: pbar.update(step_amount)
                continue
            
            invoke('changeDeck', cards=card_ids, deck=target_deck)
            moved_count = len(card_ids)
            total_moved_count += moved_count
            _print(pbar, f" -> 성공: {moved_count}개의 카드를 '{target_deck}'(으)로 이동했습니다.\n")

        except Exception as e:
            _print(pbar, f" -> 실패: 카드 이동 중 오류가 발생했습니다. 에러: {e}\n")
            if pbar and step_amount > 0: pbar.update(step_amount)
            return False
            
        if pbar and step_amount > 0: pbar.update(step_amount)
            
    if total_moved_count > 0:
        _print(pbar, f"총 {total_moved_count}개의 카드를 올바른 위치로 이동했습니다.")
    else:
        _print(pbar, "모든 카드가 이미 올바른 덱에 배치되어 있습니다.")
    return True

if __name__ == '__main__':
    print("Anki 카드 자동 분류 스크립트를 시작합니다...\n")
    run_organizer()
    print("작업이 완료되었습니다.")
