import nltk
from utils.pos_automator import get_simple_pos, setup_nltk

def test_idioms():
    setup_nltk()
    test_cases = [
        "kick the bucket",
        "piece of cake",
        "break a leg",
        "take off",
        "under the weather",
        "bus stop",
        "social media",
        "in front of",
        "by the way"
    ]
    
    print(f"{'표현':<20} | {'판별 결과'}")
    print("-" * 35)
    for case in test_cases:
        res = get_simple_pos(case)
        print(f"{case:<20} | {res}")

if __name__ == "__main__":
    test_idioms()
