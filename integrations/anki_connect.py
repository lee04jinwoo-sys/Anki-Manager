import requests
import os
from config import ANKI_URL

class AnkiConnector:
    @staticmethod
    def invoke(action, **params):
        try:
            response = requests.post(ANKI_URL, json={"action": action, "version": 6, "params": params}).json()
            if 'error' in response and response['error']:
                # 중복 에러는 호출부에서 처리할 수 있도록 에러 메시지 그대로 유지
                raise Exception(response['error'])
            return response['result']
        except Exception as e:
            if "duplicate" in str(e).lower():
                raise e # 중복 에러는 상위에서 잡도록 던짐
            raise Exception(f"AnkiConnect 에러: {e}")

    @classmethod
    def add_note(cls, deck_name, model_name, fields, tags=None, options=None):
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": fields,
            "tags": tags or [],
            "options": options or {"allowDuplicate": False}
        }
        return cls.invoke('addNote', note=note)

    @classmethod
    def add_notes(cls, notes):
        return cls.invoke('addNotes', notes=notes)

    @classmethod
    def find_notes(cls, query):
        return cls.invoke('findNotes', query=query)

    @classmethod
    def get_notes_info(cls, note_ids):
        return cls.invoke('notesInfo', notes=note_ids)

    @classmethod
    def update_note_fields(cls, note_id, fields):
        return cls.invoke('updateNoteFields', note={'id': note_id, 'fields': fields})

    @classmethod
    def get_deck_names(cls):
        return cls.invoke('deckNames')

    @classmethod
    def get_deck_config(cls, deck_name):
        return cls.invoke('getDeckConfig', deck=deck_name)

    @classmethod
    def update_model_styling(cls, model_name, styling):
        return cls.invoke('updateModelStyling', model={'name': model_name, 'css': styling})

    @classmethod
    def update_model_templates(cls, model_name, templates):
        return cls.invoke('updateModelTemplates', model={'name': model_name, 'templates': templates})

    @classmethod
    def get_existing_vocab_words(cls, model_vocab_name):
        import re
        existing = set()
        try:
            note_ids = cls.find_notes(query=f'"note:{model_vocab_name}"')
            if note_ids:
                notes_info = cls.get_notes_info(note_ids)
                for note in notes_info:
                    if '단어' in note['fields']:
                        clean = re.sub('<[^<]+?>', '', note['fields']['단어']['value']).strip().lower()
                        existing.add(clean)
        except:
            pass
        return list(existing)
