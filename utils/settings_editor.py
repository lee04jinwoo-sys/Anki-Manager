from utils.ui import UI
from utils.cli_selector import InteractiveSelector
from utils.settings_manager import load_settings, save_settings
import os

def menu_settings():
    while True:
        UI.clear()
        UI.header("설정 관리자")
        
        current = load_settings()
        
        # Define editable fields and their friendly names
        fields = [
            ("CURRENT_TARGET", "Anki 대상 프로필 (ME / GIRLFRIEND_LOCAL)"),
            ("OBSIDIAN_VAULT_PATH", "Obsidian 보관함 경로"),
            ("OBSIDIAN_INBOX_FILE", "Obsidian 인박스 파일명"),
            ("SENTENCE_SELECTOR_MODEL", "AI 모델 (문장 선별)"),
            ("VOCAB_SELECTOR_MODEL", "AI 모델 (단어 선별)"),
            ("b", "뒤로 가기")
        ]
        
        display_options = []
        for key, label in fields:
            if key == "b":
                display_options.append(label)
                continue
            val = current.get(key, "(기본값)")
            # Shorten long paths for display
            if len(str(val)) > 40:
                val = "..." + str(val)[-37:]
            display_options.append(f"{label}: [yellow]{val}[/]")
            
        choice_text = InteractiveSelector.select_one(display_options, title="수정할 설정을 선택하세요")
        
        if not choice_text or "뒤로 가기" in choice_text:
            break
            
        # Find which key was selected
        selected_key = None
        for key, label in fields:
            if label in choice_text or (key != "b" and key in choice_text):
                selected_key = key
                break
        
        if selected_key and selected_key != "b":
            UI.subheader(f"설정 수정: {selected_key}")
            UI.info(f"현재 값: {current.get(selected_key, '(기본값)')}")
            
            if selected_key == "CURRENT_TARGET":
                new_val = InteractiveSelector.select_one(["ME", "GIRLFRIEND_LOCAL"], title="대상 프로필 선택")
                if new_val:
                    current[selected_key] = new_val
                    save_settings(current)
                    UI.success("설정이 저장되었습니다. 재시작 시 적용됩니다.")
            else:
                new_val = UI.ask(f"{selected_key}의 새로운 값을 입력하세요").strip()
                if new_val:
                    current[selected_key] = new_val
                    save_settings(current)
                    UI.success("설정이 저장되었습니다. 재시작 시 적용됩니다.")
            
            UI.ask("계속하려면 Enter를 누르세요")
