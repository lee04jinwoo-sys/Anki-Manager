import json
import os
from integrations.anki_connect import AnkiConnector
from config import USER_CONFIG_PATH

def export_anki_styles():
    """
    Fetches CSS and Templates from Anki for all note types defined in user_config.json
    and saves them back to user_config.json.
    """
    if not os.path.exists(USER_CONFIG_PATH):
        print(f"❌ {USER_CONFIG_PATH} not found.")
        return

    with open(USER_CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    if 'note_types' not in config:
        print("❌ 'note_types' not found in config.")
        return

    updated_count = 0
    for model_name, note_info in config['note_types'].items():
        print(f"📡 Exporting styles for model: {model_name}...")
        try:
            # Fetch model info from Anki
            model_info_list = AnkiConnector.invoke('modelTemplates', modelName=model_name)
            model_styling = AnkiConnector.invoke('modelStyling', modelName=model_name)
            
            if model_styling and 'css' in model_styling:
                config['note_types'][model_name]['css'] = model_styling['css']
            
            if model_info_list:
                # Anki-Connect modelTemplates returns a dict of template names to {Front, Back}
                # But it depends on the version/exact API behavior. 
                # modelTemplates typically returns {template_name: {"Front": "...", "Back": "..."}}
                config['note_types'][model_name]['templates'] = model_info_list
            
            updated_count += 1
            print(f"✅ Successfully exported {model_name}.")
        except Exception as e:
            print(f"⚠️ Could not export {model_name}: {e}")

    if updated_count > 0:
        with open(USER_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"\n🎉 Export complete! Updated {updated_count} note types in user_config.json.")
    else:
        print("\n❌ No styles were exported.")

if __name__ == "__main__":
    export_anki_styles()
