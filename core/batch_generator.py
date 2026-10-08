import os
import json
import logging
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from config import (
    GOOGLE_API_KEY, NOTE_COMPLETOR_MODEL, GEMINI_DEFAULT_TEMPERATURE,
    DECK_SENTENCE, MODEL_SENTENCE
)
from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from core.link_manager import get_db_connection, clean_text, PatternMatcher

logger = logging.getLogger("BatchSentenceGenerator")


class GeneratedSentenceItem(BaseModel):
    word: str = Field(description="대상 어휘 또는 숙어")
    sentence: str = Field(description="해당 단어가 자연스럽게 포함된 실생활 영어 문장 (A, B 플레이스홀더를 실제 대상 단어로 대체)")
    translation: str = Field(description="문장의 자연스러운 한국어 번역")


class BatchSentenceResponse(BaseModel):
    items: List[GeneratedSentenceItem]


BATCH_SENTENCE_PROMPT = """원어민 실생활 영어 문장과 자연스러운 한국어 번역을 작성하세요.
규칙:
1. 각 단어마다 1개의 완성된 실용 문장 작성
2. 'A, B, V, V-ing' 기호는 반드시 실제 자연스러운 사람, 사물, 동작으로 대체 (기호 노출 절대 금지)
3. 출력 형식: JSON 2차원 배열만 반환 -> [["단어", "영어문장", "한국어번역"], ...]"""


class BatchSentenceGenerator:
    """선택된 단어들에 대해 AI 문장을 일괄 생성하고 Anki 덱에 등록 및 자동 링크하는 클래스"""

    def __init__(self):
        self.api_key = GOOGLE_API_KEY or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY가 설정되어 있지 않습니다.")
        self.client = genai.Client(api_key=self.api_key)
        # 토큰 절약 & 초고속 응답을 위해 flash-lite 고정
        self.model_id = "gemini-2.5-flash-lite"

    def generate_and_add_sentences(
        self,
        words_data: List[Dict[str, Any]],
        generate_audio: bool = True
    ) -> Dict[str, Any]:
        """
        words_data: [{"note_id": 1234, "word": "come in clutch", "meaning": "..."}, ...]
        1. Gemini Flash-Lite로 초절약 2차원 배열 문장 생성
        2. 정규 GCP Chirp3-HD TTS 오디오 생성 (선택)
        3. Anki Sentence 덱에 노트 추가
        4. links.db에 링크 정보 저장 및 vocab_cache 갱신
        """
        if not words_data:
            return {"success": True, "created_count": 0, "results": []}

        # 단어 프롬프트 압축: 긴 뜻 중 첫 번째 대표 뜻만 컴팩트하게 추출 (입력 토큰 30% 절감)
        words_prompt_lines = []
        for item in words_data:
            raw_m = item.get("meaning", "").strip()
            short_m = raw_m.split(",")[0].split(";")[0].split("(")[0].strip()[:20]
            words_prompt_lines.append(f"- {item['word']}" + (f" ({short_m})" if short_m else ""))

        user_prompt = "다음 어휘들로 실생활 예문과 번역을 생성해 주세요:\n" + "\n".join(words_prompt_lines)

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=BATCH_SENTENCE_PROMPT,
                    temperature=0.3,
                    response_mime_type="application/json",
                )
            )
            raw_items = json.loads(response.text)
            # 만약 딕셔너리로 감싸져 오면 리스트 언랩
            if isinstance(raw_items, dict):
                raw_items = next((v for v in raw_items.values() if isinstance(v, list)), [])
        except Exception as e:
            logger.error(f"Gemini API 문장 생성 실패: {e}")
            raise Exception(f"Gemini 문장 생성 실패: {e}")

        # 단어 매핑을 위한 딕셔너리
        vocab_map = {item["word"].strip().lower(): item for item in words_data}

        # GCP TTS 클라이언트 초기화 (오디오 생성 시)
        tts_client = None
        if generate_audio:
            try:
                from google.cloud import texttospeech
                tts_client = texttospeech.TextToSpeechClient()
            except Exception as e:
                logger.warning(f"GCP TTS 클라이언트 초기화 실패 (gTTS 대체 예정): {e}")

        created_results = []
        links_to_insert = []
        vocab_ids_updated = set()

        for gen_item in raw_items:
            if isinstance(gen_item, (list, tuple)) and len(gen_item) >= 3:
                w_str, sent_str, trans_str = gen_item[0], gen_item[1], gen_item[2]
            elif isinstance(gen_item, dict):
                w_str = gen_item.get("word", "")
                sent_str = gen_item.get("sentence", "")
                trans_str = gen_item.get("translation", "")
            else:
                continue

            norm_word = str(w_str).strip().lower()
            matched_vocab = vocab_map.get(norm_word)

            # 정확히 매칭 안 되면 부분 일치 시도
            if not matched_vocab:
                for k, v in vocab_map.items():
                    if k in norm_word or norm_word in k:
                        matched_vocab = v
                        break

            clean_sentence = clean_text(str(sent_str))
            clean_translation = clean_text(str(trans_str))

            if not clean_sentence:
                continue

            # TTS 오디오 생성
            sound_field = ""
            if generate_audio:
                try:
                    sound_field, _ = AnkiTTSFiller.generate_random_tts(tts_client, clean_sentence)
                except Exception as e:
                    logger.error(f"TTS 생성 실패 ({clean_sentence}): {e}")

            # Anki 노트 필드 구성
            fields = {
                "문장": clean_sentence,
                "해설": clean_translation,
                "소리": sound_field
            }

            try:
                new_note_id = AnkiConnector.add_note(
                    deck_name=DECK_SENTENCE,
                    model_name=MODEL_SENTENCE,
                    fields=fields
                )
                logger.info(f"Anki 문장 카드 생성 완료: {clean_sentence} (ID: {new_note_id})")

                if matched_vocab:
                    v_id = matched_vocab["note_id"]
                    v_word = matched_vocab["word"]
                    links_to_insert.append((v_id, v_word, new_note_id, clean_sentence))
                    vocab_ids_updated.add(v_id)

                created_results.append({
                    "word": w_str,
                    "sentence": clean_sentence,
                    "translation": clean_translation,
                    "note_id": new_note_id
                })
            except Exception as e:
                logger.error(f"Anki 카드 추가 실패: {e}")

        # links.db 및 vocab_cache 업데이트
        if links_to_insert:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR IGNORE INTO links (vocab_note_id, vocab_word, sentence_note_id, sentence_text)
                    VALUES (?, ?, ?, ?)
                """, links_to_insert)

                for v_id in vocab_ids_updated:
                    cursor.execute("""
                        UPDATE vocab_cache
                        SET link_count = link_count + 1
                        WHERE note_id = ?
                    """, (v_id,))
                conn.commit()

        return {
            "success": True,
            "created_count": len(created_results),
            "results": created_results
        }
