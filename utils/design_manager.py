import json
import logging
import os
from integrations.anki_connect import AnkiConnector

logger = logging.getLogger("AnkiManager.design")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGN_FILE = os.path.join(BASE_DIR, "data", "design_config.json")
TARGET_MODELS = ["English Vocabulary", "English Sentence", "English Grammar", "English Speaking", "Knowledge Q&A"]


def export_design() -> dict:
    """Fetches CSS and Templates from Anki and saves to data/design_config.json"""
    design_data = {}
    success_count = 0

    for model_name in TARGET_MODELS:
        try:
            styling = AnkiConnector.invoke("modelStyling", modelName=model_name)
            templates = AnkiConnector.invoke("modelTemplates", modelName=model_name)
            if not styling or not templates:
                continue

            design_data[model_name] = {
                "css": styling.get("css", ""),
                "templates": templates,
            }
            success_count += 1
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", model_name, e)

    if success_count > 0:
        os.makedirs(os.path.dirname(DESIGN_FILE), exist_ok=True)
        with open(DESIGN_FILE, "w", encoding="utf-8") as f:
            json.dump(design_data, f, indent=2, ensure_ascii=False)
        return {"status": "success", "count": success_count, "path": DESIGN_FILE}
    else:
        raise RuntimeError("내보낼 모델을 Anki에서 찾지 못했습니다. Anki 실행 여부를 확인하세요.")


def import_design() -> dict:
    """Reads design_config.json and applies to Anki"""
    if not os.path.exists(DESIGN_FILE):
        raise FileNotFoundError(f"디자인 파일이 없습니다: {DESIGN_FILE}")

    with open(DESIGN_FILE, "r", encoding="utf-8") as f:
        design_data = json.load(f)

    success_count = 0
    for model_name, design in design_data.items():
        try:
            if "css" in design:
                AnkiConnector.update_model_styling(model_name, design["css"])
            if "templates" in design:
                AnkiConnector.update_model_templates(model_name, design["templates"])
            success_count += 1
        except Exception as e:
            logger.warning("Failed to update %s: %s", model_name, e)

    return {"status": "success", "count": success_count}
