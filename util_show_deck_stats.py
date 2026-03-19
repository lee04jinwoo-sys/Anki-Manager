import json
import urllib.request
import time

def _print(pbar, *args, **kwargs):
    if pbar:
        # Assuming pbar is a tqdm-like object with a 'write' method.
        pbar.write(" ".join(map(str, args)), **kwargs)
    else:
        print(*args, **kwargs)

def invoke(action, **params):
    requestJson = json.dumps({'action': action, 'params': params, 'version': 6}).encode('utf-8')
    try:
        response = json.load(urllib.request.urlopen(urllib.request.Request('http://localhost:8765', requestJson)))
    except Exception as e:
        return {"error": "Anki에 연결할 수 없습니다."}
    if response['error'] is not None:
        raise Exception(response['error'])
    return response['result']

def main(pbar=None):
    parent_prefix = "1. Language::1.1. English"
    target_prefix = parent_prefix + "::"
    
    try:
        all_deck_names = invoke('deckNames')
        target_decks = [name for name in all_deck_names if name.startswith(target_prefix)]

        if not target_decks:
            _print(pbar, f"'{target_prefix}' 하위 덱을 찾을 수 없습니다.")
            return

        _print(pbar, f"[{parent_prefix}] 학습 효율 분석")
        _print(pbar, f"{'덱 이름':<20} | {'새 카드':<7} | {'고갈 시점':<8} | {'Ret (1d)':<10} | {'Ret (7d)':<10} | {'Ret (30d)'}")
        _print(pbar, "-" * 90)

        for name in target_decks:
            # 1. 새 카드 및 고갈 계산
            new_cards = len(invoke('findCards', query=f'"deck:{name}" is:new'))
            try:
                config = invoke('getDeckConfig', deck=name)
                daily_limit = config['new']['perDay']
            except:
                daily_limit = 0
            
            days_left = f"{new_cards/daily_limit:.1f}일" if daily_limit > 0 else "N/A"

            # 2. Retention 계산 (1일, 7일, 30일)
            cards_reviewed_30d = invoke('findCards', query=f'"deck:{name}" rated:30')
            
            total_1d, pass_1d = 0, 0
            total_7d, pass_7d = 0, 0
            total_30d, pass_30d = 0, 0
            
            now_ms = time.time() * 1000
            ms_1d = now_ms - (1 * 24 * 60 * 60 * 1000)
            ms_7d = now_ms - (7 * 24 * 60 * 60 * 1000)
            ms_30d = now_ms - (30 * 24 * 60 * 60 * 1000)

            if cards_reviewed_30d:
                reviews_dict = invoke('getReviewsOfCards', cards=cards_reviewed_30d)
                
                for card_id, reviews in reviews_dict.items():
                    for review in reviews:
                        rid = review['id']
                        ease = review['ease']
                        is_pass = 1 if ease > 1 else 0
                        
                        if rid >= ms_1d:
                            total_1d += 1
                            pass_1d += is_pass
                        if rid >= ms_7d:
                            total_7d += 1
                            pass_7d += is_pass
                        if rid >= ms_30d:
                            total_30d += 1
                            pass_30d += is_pass

            def fmt_ret(passed, total):
                if total == 0: return "N/A"
                return f"{(passed/total)*100:.1f}%"

            ret_1d = fmt_ret(pass_1d, total_1d)
            ret_7d = fmt_ret(pass_7d, total_7d)
            ret_30d = fmt_ret(pass_30d, total_30d)

            display_name = name.replace(target_prefix, "")
            if len(display_name) > 20:
                display_name = display_name[:17] + "..."
                
            _print(pbar, f"{display_name:<20} | {new_cards:<7} | {days_left:<8} | {ret_1d:<10} | {ret_7d:<10} | {ret_30d}")

    except Exception as e:
        _print(pbar, f"오류 발생: {e}")

if __name__ == '__main__':
    main()
