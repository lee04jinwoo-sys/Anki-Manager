import json
import os
from integrations.anki_connect import AnkiConnector
from utils.ui import UI

# Get the project root directory (one level up from 'utils')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGN_FILE = os.path.join(BASE_DIR, "data", "design_config.json")
TARGET_MODELS = ["English Vocabulary", "English Sentence", "English Grammar", "English Speaking"]

def export_design():
    """Fetches CSS and Templates from Anki and saves to design_config.json"""
    design_data = {}
    
    UI.subheader("Exporting Design from Anki")
    
    success_count = 0
    for model_name in TARGET_MODELS:
        with UI.wait(f"Fetching {model_name}"):
            try:
                # Get styling (CSS)
                styling = AnkiConnector.invoke('modelStyling', modelName=model_name)
                # Get templates (HTML)
                templates = AnkiConnector.invoke('modelTemplates', modelName=model_name)
                
                if not styling or not templates:
                    UI.warn(f"No data found for {model_name}")
                    continue

                design_data[model_name] = {
                    "css": styling.get('css', ""),
                    "templates": templates
                }
                success_count += 1
            except Exception as e:
                UI.error(f"Failed to fetch {model_name}: {e}")

    if success_count > 0:
        os.makedirs(os.path.dirname(DESIGN_FILE), exist_ok=True)
        with open(DESIGN_FILE, 'w', encoding='utf-8') as f:
            json.dump(design_data, f, indent=2, ensure_ascii=False)
        UI.success(f"Exported {success_count} models to:")
        UI.print(f"  {DESIGN_FILE}", style="cyan")
    else:
        UI.error("No models were exported. Check if Anki is running and models exist.")

def import_design():
    """Reads design_config.json and applies to Anki"""
    UI.subheader("Importing Design to Anki")
    
    if not os.path.exists(DESIGN_FILE):
        UI.error(f"Design file not found: {DESIGN_FILE}")
        return

    try:
        with open(DESIGN_FILE, 'r', encoding='utf-8') as f:
            design_data = json.load(f)
    except Exception as e:
        UI.error(f"Failed to read design file: {e}")
        return

    success_count = 0
    for model_name, design in design_data.items():
        with UI.wait(f"Updating {model_name}"):
            try:
                # Update CSS
                if "css" in design:
                    AnkiConnector.update_model_styling(model_name, design["css"])
                
                # Update Templates
                if "templates" in design:
                    AnkiConnector.update_model_templates(model_name, design["templates"])
                
                UI.success(f"Synchronized {model_name}")
                success_count += 1
            except Exception as e:
                UI.error(f"Failed to update {model_name}: {e}")

    UI.print(f"Total {success_count} models updated in Anki.", style="bold green")
