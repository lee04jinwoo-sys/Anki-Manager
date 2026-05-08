import json
import os

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "settings.json")

def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

def get_setting(key, default):
    return load_settings().get(key, default)
