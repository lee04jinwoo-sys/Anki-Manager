import sys
import os

# 프로젝트 루트를 path에 추가하여 모듈 임포트 가능하게 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.cli_selector import InteractiveSelector
from rich.console import Console

def test_interactive_selector():
    console = Console()
    console.print("[bold magenta]Interactive Selector Test[/bold magenta]")
    console.print("테스트 데이터로 선택기 실행 중... (Enter: 선택, x: 제외, c: 완료, q: 취소)\n")
    
    test_items = [
        "This is a sample sentence for testing.",
        "How about this one? It looks like a good candidate.",
        "I'll get right on it as soon as possible.",
        "That makes a lot of sense in this context.",
        "Meticulous planning is key to success.",
        "She was over the moon when she heard the news.",
        "Keep me in the loop regarding this project.",
        "It's not my cup of tea, to be honest.",
        "Let's call it a day after this test.",
        "Break a leg on your presentation!"
    ]
    
    selector = InteractiveSelector(test_items, title="🧪 Test Selector (5 words min filter applied)")
    results = selector.run()
    
    if results is None:
        console.print("\n[bold red]테스트 취소됨 (User pressed 'q')[/bold red]")
    else:
        console.print(f"\n[bold green]선택된 문장 ({len(results)}개):[/bold green]")
        for i, item in enumerate(results, 1):
            console.print(f"{i}. {item}")

if __name__ == "__main__":
    try:
        test_interactive_selector()
    except KeyboardInterrupt:
        print("\nTest interrupted.")
    except Exception as e:
        print(f"\nAn error occurred during testing: {e}")
