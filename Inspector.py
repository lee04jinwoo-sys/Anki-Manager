import sys

def inspect_items(items, display_func=None):
    """
    리스트의 전체 항목을 한 번에 보여준 뒤, 제외(Drop)할 항목의 번호만 쉼표로 입력받습니다.
    
    Args:
        items (list): 검수할 항목들의 리스트입니다.
        display_func (callable, optional): 항목을 화면에 표시할 때 사용할 포맷팅 함수입니다.
                                           지정하지 않으면 str(item)이 사용됩니다.
                                           
    Returns:
        list: 사용자가 제외하지 않고 유지하기로 선택한 항목들의 리스트입니다.
    """
    if not items:
        print("검수할 항목이 없습니다.")
        return []

    total_items = len(items)
    
    print(f"\n--- {total_items}개 항목에 대한 최종 검수를 시작합니다 ---")
    
    # 리스트 전체 출력
    for i, item in enumerate(items, 1):
        # 항목 표시
        if display_func:
            try:
                display_text = display_func(item)
            except Exception as e:
                display_text = str(item)
        else:
            display_text = str(item)
            
        print(f"\n[{i}] {display_text}")

    print("-" * 50)
    
    # 제외할 번호 입력받기
    while True:
        choice = input("\n제외(Drop)할 항목의 번호를 쉼표(,)로 구분하여 입력하세요 (없으면 Enter): ").strip()
        
        if not choice:
            print(f"\n--- 검수 완료: 모든 {total_items}개 항목이 유지되었습니다. ---")
            return items
            
        # 입력값 파싱 및 검증
        drop_indices = set()
        invalid_input = False
        
        for part in choice.split(','):
            part = part.strip()
            if not part:
                continue
                
            if not part.isdigit():
                print(f"오류: '{part}'는 유효한 숫자가 아닙니다.")
                invalid_input = True
                break
                
            idx = int(part)
            if idx < 1 or idx > total_items:
                print(f"오류: 번호 {idx}는 범위를 벗어났습니다 (1~{total_items}).")
                invalid_input = True
                break
                
            drop_indices.add(idx)
            
        if not invalid_input:
            break
            
    # 항목 제외
    kept_items = []
    for i, item in enumerate(items, 1):
        if i not in drop_indices:
            kept_items.append(item)
            
    print(f"\n--- 검수 완료: {len(drop_indices)}개 제외, 총 {len(kept_items)}개의 항목이 유지되었습니다. ---")
    return kept_items

if __name__ == '__main__':
    # 간단한 테스트용 데이터
    test_data = [
        {"word": "apple", "meaning": "과일"},
        {"word": "banana", "meaning": "또 다른 과일"},
        {"word": "car", "meaning": "탈 것", "bad_data": True},
        {"word": "dog", "meaning": "동물"}
    ]
    
    def format_item(item):
        return f"단어: {item.get('word')} / 의미: {item.get('meaning')}"
        
    final_list = inspect_items(test_data, display_func=format_item)
    print("\n최종 리스트:")
    for item in final_list:
        print(item)
