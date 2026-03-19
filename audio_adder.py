import requests
import json
import base64
import time
import re
import random
import traceback
import os

try:
    from gtts import gTTS
    from google.cloud import texttospeech
    from google.api_core import exceptions as google_exceptions
    from google.auth import exceptions as auth_exceptions
    import requests.exceptions
except ImportError:
    print("오류: 필요한 라이브러리가 설치되지 않았습니다.")
    print("터미널에 'pip install google-cloud-texttospeech requests gTTS'를 입력하여 설치해주세요.")
    exit()

from config import (
    ANKI_URL, VOICE_LIST, TARGET_NOTE_TYPES_FOR_AUDIO,
    TARGET_MODELS_FOR_AUDIO_SENTENCE, TARGET_MODELS_FOR_AUDIO_VOCAB,
    TTS_SENTENCE_LANGUAGE_CODE, TTS_VOCAB_LANGUAGE, TTS_VOCAB_TLD,
    TEMP_DIR, AUDIO_ADDER_MAX_WORKERS
)

def _print(pbar, *args, **kwargs):
    if pbar:
        pbar.write(" ".join(map(str, args)), **kwargs)
    else:
        print(*args, **kwargs)

class AnkiTTSFiller:
    _INVOKE_FAILED = object()

    @staticmethod
    def invoke(action, **params):
        try:
            response = requests.post(ANKI_URL, json={"action": action, "version": 6, "params": params}).json()
            if 'error' in response and response['error']: raise Exception(response['error'])
            return response.get('result')
        except requests.exceptions.ConnectionError as e:
            # Re-raise with a more specific error message
            raise ConnectionError("Anki 연결 실패: Anki 프로그램이 실행 중이고 AnkiConnect 애드온이 설치되었는지 확인하세요.") from e
        except Exception as e:
            raise e

    @classmethod
    def find_target_notes(cls, pbar=None):
        _print(pbar, "🔍 Anki 덱 스캔 중...")
        query = TARGET_NOTE_TYPES_FOR_AUDIO
        try:
            note_ids = cls.invoke("findNotes", query=query)
            if not note_ids:
                _print(pbar, "대상이 되는 노트를 찾을 수 없습니다.")
                return []

            notes_info = cls.invoke("notesInfo", notes=note_ids)
            if not notes_info:
                return []

            target_notes = []
            for n in notes_info:
                note_id = n['noteId']
                fields = n['fields']
                model_name = n['modelName']
                
                if model_name in TARGET_MODELS_FOR_AUDIO_SENTENCE:
                    if '문장' in fields and '소리' in fields and \
                       fields['문장']['value'].strip() and not fields['소리']['value'].strip():
                        target_notes.append({
                            "id": note_id,
                            "text": re.sub('<[^<]+?>', '', fields['문장']['value']).strip(),
                            "type": "sentence"
                        })
                elif model_name in TARGET_MODELS_FOR_AUDIO_VOCAB:
                    if '단어' in fields and '소리' in fields and \
                       fields['단어']['value'].strip() and not fields['소리']['value'].strip():
                        target_notes.append({
                            "id": note_id,
                            "text": re.sub('<[^<]+?>', '', fields['단어']['value']).strip(),
                            "type": "vocabulary"
                        })

            _print(pbar, f"🎯 오디오 생성이 필요한 카드: {len(target_notes)}개 발견!")
            return target_notes
        except Exception as e:
            _print(pbar, f"❌ Anki 덱 스캔 실패: {e}")
            return None


    @classmethod
    def generate_random_tts(cls, tts_client, text, pbar=None):
        if not text: return "", "No Text"
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            selected_voice_name = random.choice(VOICE_LIST)
            voice = texttospeech.VoiceSelectionParams(language_code=TTS_SENTENCE_LANGUAGE_CODE, name=selected_voice_name)
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            
            safe_text = re.sub(r'[^a-zA-Z0-9]', '_', text[:15])
            filename = f"anki_gcp_{selected_voice_name}_{safe_text}_{int(time.time())}.mp3"
            b64_audio = base64.b64encode(response.audio_content).decode('utf-8')
            
            cls.invoke("storeMediaFile", filename=filename, data=b64_audio)
            return f"[sound:{filename}]", selected_voice_name
            
        except google_exceptions.PermissionDenied:
            _print(pbar, "\n[에러] GCP 권한 거부: Google Cloud 프로젝트에서 Text-to-Speech API가 활성화되었는지, 그리고 현재 계정이 해당 API를 사용할 권한이 있는지 확인하세요.")
        except google_exceptions.ResourceExhausted:
            _print(pbar, "\n[에러] GCP 사용량 초과: Google Cloud의 TTS API 할당량(Quota)을 초과했습니다. 잠시 후 다시 시도하거나 GCP 콘솔에서 할당량을 확인하세요.")
        except google_exceptions.NotFound:
            _print(pbar, f"\n[에러] 잘못된 음성 모델: VOICE_LIST에 포함된 '{selected_voice_name}' 모델을 찾을 수 없습니다. 올바른 모델명인지 확인하세요.")
        except Exception as e:
            _print(pbar, f"\n[알 수 없는 TTS 에러] ({text[:10]}...): {e}")
            
        return "", "TTS Error"

    @classmethod
    def generate_google_translate_tts(cls, text, pbar=None):
        if not text: return "", "No Text"
        try:
            tts = gTTS(text, lang=TTS_VOCAB_LANGUAGE, tld=TTS_VOCAB_TLD)
            
            safe_text = re.sub(r'[^a-zA-Z0-9]', '_', text[:15])
            filename = f"anki_gtts_en-us_{safe_text}_{int(time.time())}.mp3"
            
            temp_file_path = os.path.join(TEMP_DIR, filename)
            tts.save(temp_file_path)

            with open(temp_file_path, 'rb') as f:
                b64_audio = base64.b64encode(f.read()).decode('utf-8')

            cls.invoke("storeMediaFile", filename=filename, data=b64_audio)
            
            return f"[sound:{filename}]", "Google_Translate"

        except Exception as e:
            _print(pbar, f"\n[gTTS 에러] ({text[:10]}...): {e}")
            return "", "gTTS Error"

    @classmethod
    def run_audio_addition(cls, pbar=None, step_points=0):
        target_notes = cls.find_target_notes(pbar=pbar)
        if target_notes is None: # Anki connection failed
            return False
        if not target_notes:
            _print(pbar, "✨ 작업을 시작할 카드가 없습니다.")
            if pbar and step_points > 0: pbar.update(step_points)
            return True

        _print(pbar, "🚀 오디오 자동 생성 및 삽입을 시작합니다...")
        
        tts_client = None
        try:
            if any(note['type'] != 'vocabulary' for note in target_notes):
                tts_client = texttospeech.TextToSpeechClient()
        except auth_exceptions.DefaultCredentialsError:
            _print(pbar, "\n❌ Google Cloud 인증 실패: GCP 기본 인증 정보를 찾을 수 없습니다.")
            _print(pbar, "터미널에서 'gcloud auth application-default login' 명령어를 실행하여 인증을 완료해주세요.")
            if not all(note['type'] == 'vocabulary' for note in target_notes):
                return False
        except Exception as e:
            _print(pbar, f"\n❌ Google TTS 클라이언트 초기화 중 알 수 없는 에러 발생: {e}")
            return False

        success_count = 0
        step_amount = step_points / len(target_notes) if step_points > 0 else 0

        import concurrent.futures

        def process_tts(note):
            text = note['text']
            note_type = note['type']
            try:
                if note_type == "vocabulary":
                    audio_tag, used_voice = cls.generate_google_translate_tts(text, pbar=pbar)
                    return note, audio_tag, used_voice, None
                else:
                    if tts_client is None:
                        return note, "", "", "GCP 클라이언트 없음"
                    audio_tag, used_voice = cls.generate_random_tts(tts_client, text, pbar=pbar)
                    return note, audio_tag, used_voice, None
            except Exception as e:
                return note, "", "", str(e)

        # 5개씩 동시에 TTS 생성 요청
        with concurrent.futures.ThreadPoolExecutor(max_workers=AUDIO_ADDER_MAX_WORKERS) as executor:
            future_to_note = {executor.submit(process_tts, note): note for note in target_notes}
            
            for idx, future in enumerate(concurrent.futures.as_completed(future_to_note), 1):
                note, audio_tag, used_voice, error_msg = future.result()
                text = note['text']
                note_type = note['type']
                
                # 병렬 처리이므로 순서가 뒤섞이지만 로그는 그대로 출력
                _print(pbar, f"[{idx}/{len(target_notes)}] 처리 완료 ({note_type}): {text[:30]}... ", end="")
                
                if error_msg:
                    _print(pbar, f"❌ 생성 실패: {error_msg}")
                elif audio_tag:
                    try:
                        cls.invoke("updateNoteFields", note={"id": note['id'], "fields": {"소리": audio_tag}})
                        _print(pbar, f"✔️ 완료 ({used_voice})")
                        success_count += 1
                    except Exception as e:
                        _print(pbar, f"❌ 필드 업데이트 실패: {e}")
                else:
                    _print(pbar, "❌ 생성 실패")
                
                if pbar and step_amount > 0: pbar.update(step_amount)

        _print(pbar, f"\n🎉 작업 완료! 총 {success_count}개의 카드에 오디오가 추가되었습니다.")
        return True

if __name__ == "__main__":
    AnkiTTSFiller.run_audio_addition()
