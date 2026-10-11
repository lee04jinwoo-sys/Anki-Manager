import requests
import os
from config import ANKI_URL

_TIMEOUT_SEC = 60


def _post(payload):
    # 요청마다 새 연결을 쓴다. AnkiConnect는 응답 뒤 연결을 닫는데, SSH 터널을 거치면
    # 클라이언트가 이를 모르고 재사용하다 두 번에 한 번 끊긴다. 재시도는 addNote 중복 위험이 있어 쓰지 않는다.
    # AnkiConnect는 localhost(또는 터널)로만 붙으므로 http_proxy 등 환경변수 프록시를 무시한다.
    with requests.Session() as session:
        session.trust_env = False
        return session.post(ANKI_URL, json=payload, timeout=_TIMEOUT_SEC)


class AnkiConnector:
    @staticmethod
    def invoke(action, **params):
        try:
            response = _post({"action": action, "version": 6, "params": params}).json()
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
    def update_notes_fields_batch(cls, updates, chunk_size=100):
        """
        AnkiConnect 'multi' 액션을 사용하여 여러 개의 updateNoteFields를 
        1번의 HTTP POST 페이로드로 묶어 초고속 일괄 처리.
        updates 형식: [{'id': note_id, 'fields': {'예문': ...}}, ...]
        """
        if not updates:
            return []
        all_results = []
        for i in range(0, len(updates), chunk_size):
            chunk = updates[i:i + chunk_size]
            actions = [
                {
                    "action": "updateNoteFields",
                    "params": {"note": {"id": item["id"], "fields": item["fields"]}}
                }
                for item in chunk
            ]
            res = cls.invoke("multi", actions=actions)
            if res:
                all_results.extend(res)
        return all_results

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

    @classmethod
    def ensure_model_fields(cls, model_name, fields_to_add):
        try:
            current_fields = cls.invoke('modelFieldNames', modelName=model_name)
            for field in fields_to_add:
                if field not in current_fields:
                    cls.invoke('modelFieldAdd', modelName=model_name, fieldName=field)
        except Exception as e:
            pass
