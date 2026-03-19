import json
import urllib.request
import urllib.error
import sys
import os

def request(action, **params):
    return {'action': action, 'params': params, 'version': 6}

def invoke(action, **params):
    requestJson = json.dumps(request(action, **params)).encode('utf-8')
    try:
        response = urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8765', requestJson))
    except urllib.error.URLError as e:
        print(f"Error connecting to Anki. Make sure Anki is open and AnkiConnect is installed. Error: {e}")
        sys.exit(1)
        
    responseJson = json.load(response)
    if len(responseJson) != 2:
        raise Exception('response has an unexpected number of fields')
    if 'error' not in responseJson:
        raise Exception('response is missing required error field')
    if 'result' not in responseJson:
        raise Exception('response is missing required result field')
    if responseJson['error'] is not None:
        raise Exception(responseJson['error'])
    return responseJson['result']

def main():
    json_path = os.path.join(os.path.dirname(__file__), 'anki_style.json')
    
    if not os.path.exists(json_path):
        print(f"Error: Could not find '{json_path}'. Make sure the file exists.")
        sys.exit(1)

    print(f"Reading styles from {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        styles_data = json.load(f)

    for model_name, model_data in styles_data.items():
        print(f"\nProcessing model: '{model_name}'")
        
        # Update CSS styling
        if 'css' in model_data:
            print(f"  - Updating CSS...")
            try:
                invoke('updateModelStyling', model={
                    "name": model_name,
                    "css": model_data['css']
                })
                print("    Success!")
            except Exception as e:
                print(f"    Failed to update CSS: {e}")
                
        # Update Templates
        if 'templates' in model_data:
            print(f"  - Updating Templates...")
            templates_to_update = {}
            for card_name, card_data in model_data['templates'].items():
                templates_to_update[card_name] = {
                    "Front": card_data.get("Front", ""),
                    "Back": card_data.get("Back", "")
                }
            
            try:
                invoke('updateModelTemplates', model={
                    "name": model_name,
                    "templates": templates_to_update
                })
                print("    Success!")
            except Exception as e:
                print(f"    Failed to update Templates: {e}")

    print("\nAnki style update completed!")

if __name__ == '__main__':
    main()
