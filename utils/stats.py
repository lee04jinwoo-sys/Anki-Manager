import time
from integrations.anki_connect import AnkiConnector

def get_deck_stats(pbar=None, fast_mode=False):
    parent = "1. Language::1.1. English"
    target_prefix = parent + "::"
    
    try:
        all_decks = AnkiConnector.get_deck_names()
        target_decks = [n for n in all_decks if n == parent or n.startswith(target_prefix)]
        
        if not target_decks:
            return None

        stats = []
        now_ms = time.time() * 1000
        
        # Used for retention calculation
        ms_1d = now_ms - (1 * 24 * 60 * 60 * 1000)
        ms_7d = now_ms - (7 * 24 * 60 * 60 * 1000)
        ms_30d = now_ms - (30 * 24 * 60 * 60 * 1000)

        for name in target_decks:
            # Display name formatting
            display_name = name.replace(target_prefix, "")
            if name == parent:
                display_name = "[Root]"

            # 1. New cards (Total unseen)
            new_cards = len(AnkiConnector.invoke('findCards', query=f'"deck:{name}" is:new'))
            # 2. Total cards
            total_cards = len(AnkiConnector.invoke('findCards', query=f'"deck:{name}"'))
            # 3. Reviews today
            reviews_today = len(AnkiConnector.invoke('findCards', query=f'"deck:{name}" rated:1'))
            # 4. Due cards
            due_cards = len(AnkiConnector.invoke('findCards', query=f'"deck:{name}" is:due'))
            # 5. Learning cards
            learn_cards = len(AnkiConnector.invoke('findCards', query=f'"deck:{name}" is:learn'))
            
            # 6. Daily new limit & Exhaust days
            new_per_day = 0
            exhaust_days = "∞"
            try:
                config = AnkiConnector.get_deck_config(name)
                new_per_day = config.get('new', {}).get('perDay', 0)
                if new_per_day > 0:
                    exhaust_days = f"{new_cards / new_per_day:.1f}"
                elif new_cards == 0:
                    exhaust_days = "0"
            except:
                pass

            deck_stat = {
                "name": display_name,
                "new": new_cards,
                "total": total_cards,
                "reviews_today": reviews_today,
                "due": due_cards,
                "learn": learn_cards,
                "new_per_day": new_per_day,
                "exhaust_days": exhaust_days
            }

            if fast_mode:
                deck_stat["ret_7d"] = "-"
                stats.append(deck_stat)
                continue

            # Retention calculation helper
            def calculate_retention(days, threshold_ms):
                cards = AnkiConnector.invoke('findCards', query=f'"deck:{name}" rated:{days}')
                if not cards:
                    return "N/A"
                
                reviews = AnkiConnector.invoke('getReviewsOfCards', cards=cards)
                total, passed = 0, 0
                for cid, rev_list in reviews.items():
                    for r in rev_list:
                        if r['id'] >= threshold_ms:
                            total += 1
                            if r['ease'] > 1: passed += 1
                
                return f"{(passed/total)*100:.1f}%" if total > 0 else "N/A"

            deck_stat.update({
                "ret_1d": calculate_retention(1, ms_1d),
                "ret_7d": calculate_retention(7, ms_7d),
                "ret_30d": calculate_retention(30, ms_30d)
            })
            stats.append(deck_stat)
        return stats
    except Exception as e:
        print(f"❌ Failed to fetch stats: {e}")
        return None
