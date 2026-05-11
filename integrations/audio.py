import requests
import base64
import time
import re
import random
import os
import concurrent.futures
import uuid
import html
from gtts import gTTS
from google.cloud import texttospeech
from config import (
    VOICE_LIST, TARGET_NOTE_TYPES_FOR_AUDIO,
    TARGET_MODELS_FOR_AUDIO_SENTENCE, TARGET_MODELS_FOR_AUDIO_VOCAB,
    TTS_SENTENCE_LANGUAGE_CODE, TTS_VOCAB_LANGUAGE, TTS_VOCAB_TLD,
    TEMP_DIR, AUDIO_ADDER_MAX_WORKERS
)
from integrations.anki_connect import AnkiConnector

def _print(pbar, *args, **kwargs):
    if pbar:
        if hasattr(pbar, 'write'): pbar.write(" ".join(map(str, args)), **kwargs)
        else: print(*args, **kwargs)
    else: print(*args, **kwargs)

def clean_html(text):
    """HTML 태그 제거 및 HTML 엔터티(&#x27; 등)를 실제 문자로 복원"""
    if not text: return ""
    # 1. HTML 엔터티 복원 (&#x27; -> ', &nbsp; -> 공백 등)
    text = html.unescape(text)
    # 2. 둥근 따옴표 등 특수 문자 정규화 (TTS 오작동 방지)
    text = text.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    # 3. HTML 태그 제거
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text).strip()

class AnkiTTSFiller:
    @classmethod
    def generate_random_tts(cls, tts_client, text, pbar=None):
        if not text: return "", "No Text"
        clean_text = clean_html(text)
        try:
            synthesis_input = texttospeech.SynthesisInput(text=clean_text)
            selected_voice_name = random.choice(VOICE_LIST)
            lang_code = "-".join(selected_voice_name.split("-")[:2])
            voice = texttospeech.VoiceSelectionParams(language_code=lang_code, name=selected_voice_name)
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.1
            )
            response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            
            # 고유한 파일명 생성 (uuid 추가)
            filename = f"anki_gcp_{selected_voice_name}_{uuid.uuid4().hex[:8]}.mp3"
            b64_audio = base64.b64encode(response.audio_content).decode('utf-8')
            AnkiConnector.invoke("storeMediaFile", filename=filename, data=b64_audio)
            return f"[sound:{filename}]", selected_voice_name
        except Exception as e:
            _print(pbar, f"❌ GCP TTS 에러: {e}")
            return "", "Error"

    @classmethod
    def generate_gtts(cls, text, pbar=None):
        if not text: return "", "No Text"
        clean_text = clean_html(text)
        try:
            tts = gTTS(clean_text, lang=TTS_VOCAB_LANGUAGE, tld=TTS_VOCAB_TLD)
            # 고유한 파일명 생성 (uuid 추가)
            filename = f"anki_gtts_{uuid.uuid4().hex[:8]}.mp3"
            path = os.path.join(TEMP_DIR, filename)
            tts.save(path)
            with open(path, 'rb') as f:
                b64_audio = base64.b64encode(f.read()).decode('utf-8')
            AnkiConnector.invoke("storeMediaFile", filename=filename, data=b64_audio)
            
            # 임시 파일 삭제
            if os.path.exists(path):
                os.remove(path)
                
            return f"[sound:{filename}]", "gTTS"
        except Exception as e:
            _print(pbar, f"❌ gTTS 에러: {e}")
            return "", "Error"

    @classmethod
    def process_single_note(cls, note, tts_client, pbar, step_amt):
        """개별 노트의 오디오를 생성하고 업데이트하는 함수 (워커용)"""
        tag = ""
        method = ""
        
        try:
            if note['type'] == "vocab":
                tag, method = cls.generate_gtts(note['text'], pbar=pbar)
            else:
                # GCP TTS 시도, 실패 시 gTTS로 폴백
                if tts_client:
                    tag, method = cls.generate_random_tts(tts_client, note['text'], pbar=pbar)
                
                if not tag:
                    _print(pbar, f"🔄 {note['text'][:10]}... gTTS로 폴백 시도")
                    tag, method = cls.generate_gtts(note['text'], pbar=pbar)
            
            if tag:
                AnkiConnector.update_note_fields(note['id'], {"소리": tag})
                _print(pbar, f"✅ 완료: {note['text'][:15]}... ({method})")
            else:
                _print(pbar, f"⚠️ 실패: {note['text'][:15]}...")
        finally:
            if pbar: pbar.update(step_amt)

    @classmethod
    def run_audio_addition(cls, pbar=None, step_points=0):
        query = TARGET_NOTE_TYPES_FOR_AUDIO
        try:
            note_ids = AnkiConnector.find_notes(query=query)
        except Exception as e:
            _print(pbar, f"❌ Anki 연결 실패: {e}")
            return False

        if not note_ids:
            if pbar and step_points > 0: pbar.update(step_points)
            else: print("✨ 오디오를 채울 카드가 없습니다.")
            return True
        
        notes_info = AnkiConnector.get_notes_info(note_ids)
        target_notes = []
        for n in notes_info:
            fields = n['fields']
            model = n['modelName']
            # 소리 필드가 비어있는지 확인 (공백 제거 후 체크)
            audio_field = fields.get('소리', {}).get('value', '').strip()
            
            if model in TARGET_MODELS_FOR_AUDIO_SENTENCE:
                if fields.get('문장', {}).get('value') and not audio_field:
                    target_notes.append({"id": n['noteId'], "text": fields['문장']['value'], "type": "sentence"})
            elif model in TARGET_MODELS_FOR_AUDIO_VOCAB:
                if fields.get('단어', {}).get('value') and not audio_field:
                    target_notes.append({"id": n['noteId'], "text": fields['단어']['value'], "type": "vocab"})

        if not target_notes:
            if pbar and step_points > 0: pbar.update(step_points)
            else: print("✨ 오디오를 채울 카드가 없습니다.")
            return True

        # pbar가 없으면 여기서 생성
        from tqdm import tqdm
        standalone = False
        if pbar is None:
            pbar = tqdm(total=len(target_notes), desc="오디오 채우기")
            step_points = len(target_notes)
            standalone = True

        tts_client = None
        try: 
            tts_client = texttospeech.TextToSpeechClient()
        except Exception as e:
            _print(pbar, f"ℹ️ GCP TTS 클라이언트 생성 실패 (gTTS만 사용 가능): {e}")

        step_amt = step_points / len(target_notes) if len(target_notes) > 0 else 0
        
        # 멀티쓰레딩 적용
        max_workers = min(AUDIO_ADDER_MAX_WORKERS, len(target_notes))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(cls.process_single_note, note, tts_client, pbar, step_amt) 
                for note in target_notes
            ]
            concurrent.futures.wait(futures)
        
        if standalone:
            pbar.close()
            print(f"✅ 총 {len(target_notes)}개 카드 오디오 채우기 완료")
        return True
