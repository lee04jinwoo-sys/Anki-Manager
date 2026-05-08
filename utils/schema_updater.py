import json
import os
from config import USER_CONFIG_PATH
from integrations.anki_connect import AnkiConnector

def apply_card_styles(pbar=None):
    """
    Reads card styles and templates from user_config.json 
    and applies them to the connected Anki profile.
    """
    if not os.path.exists(USER_CONFIG_PATH):
        print(f"❌ 설정 파일을 찾을 수 없습니다: {USER_CONFIG_PATH}")
        return False

    with open(USER_CONFIG_PATH, 'r', encoding='utf-8') as f:
        user_config = json.load(f)

    note_types = user_config.get("note_types", {})
    if not note_types:
        print("ℹ️ 업데이트할 카드 스타일 설정이 없습니다.")
        return True

    print("\n🎨 Anki 카드 스타일 및 템플릿 동기화 중...")
    
    success_count = 0
    for model_name, config in note_types.items():
        try:
            print(f"🔄 [{model_name}] 스타일 업데이트 중...")
            
            # 1. Update CSS (Styling)
            if "css" in config:
                AnkiConnector.update_model_styling(model_name, config["css"])
            
            # 2. Update Templates (Front/Back)
            if "templates" in config:
                AnkiConnector.update_model_templates(model_name, config["templates"])
            
            print(f"✅ [{model_name}] 동기화 완료")
            success_count += 1
        except Exception as e:
            print(f"❌ [{model_name}] 업데이트 실패: {e}")

    print(f"\n✨ 총 {success_count}개의 카드 모델 스타일을 성공적으로 동기화했습니다.")
    return True

if __name__ == "__main__":
    apply_card_styles()
