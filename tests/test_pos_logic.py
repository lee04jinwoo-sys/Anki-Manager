import nltk
from integrations.anki_connect import AnkiConnector
from config import MODEL_VOCAB
from utils.pos_automator import get_simple_pos, setup_nltk
from rich.console import Console
from rich.table import Table

def test_pos_comparison(limit=100):
    setup_nltk()
    console = Console()
    
    query = f'note:"{MODEL_VOCAB}"'
    try:
        note_ids = AnkiConnector.find_notes(query)
    except Exception as e:
        console.print(f"[bold red]Anki 연결 실패: {e}[/bold red]")
        return

    if not note_ids:
        console.print("[yellow]비교할 카드가 없습니다.[/yellow]")
        return

    # 최근 100개 카드 가져오기
    sample_ids = note_ids[:limit]
    notes_info = AnkiConnector.get_notes_info(sample_ids)
    
    table = Table(title=f"품사 비교 테스트 (최대 {limit}개)")
    table.add_column("단어", style="cyan")
    table.add_column("현재 품사", style="magenta")
    table.add_column("NLTK 결과", style="green")
    table.add_column("일치 여부", justify="center")

    matches = 0
    
    for n in notes_info:
        word = n['fields'].get('단어', {}).get('value', '').strip()
        current_pos = n['fields'].get('품사', {}).get('value', '').strip()
        
        if not word: continue
        
        # HTML 태그 제거 (Anki 필드에 있을 수 있음)
        import re
        clean_word = re.sub('<[^<]+?>', '', word)
        
        new_pos = get_simple_pos(clean_word)
        
        is_match = "✅" if current_pos == new_pos else "❌"
        if current_pos == new_pos:
            matches += 1
            
        table.add_row(clean_word, current_pos, new_pos, is_match)

    console.print(table)
    console.print(f"\n[bold]전체 일치율: {matches}/{len(notes_info)} ({matches/len(notes_info)*100:.1f}%)[/bold]")

if __name__ == "__main__":
    test_pos_comparison()
