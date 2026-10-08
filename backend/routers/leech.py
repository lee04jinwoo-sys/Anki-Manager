from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import concurrent.futures
import html
import re
import json
import logging
from google import genai
from google.genai import types

from config import MODEL_VOCAB, MODEL_SENTENCE, DECK_SENTENCE, GOOGLE_API_KEY
from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from utils.organizer import run_organizer
from backend.routers.workflow import emit_log, workflow_state

logger = logging.getLogger("AnkiManagerLeech")
router = APIRouter(prefix="/api/leech", tags=["leech"])

class LeechItem(BaseModel):
    id: int # noteId
    card_id: int
    word: str
    meaning: str
    pos: Optional[str] = ""
    explain: Optional[str] = ""
    example: Optional[str] = ""
    lapses: int = 0
    reps: int = 0
    ease: float = 130.0
    interval: int = 0

class DiagnoseRequest(BaseModel):
    candidates: List[LeechItem]

class DiagnoseResultItem(BaseModel):
    id: int
    card_id: int
    word: str
    action: str # "revamp_idiom", "revamp_collocation", "sentence", "delete", "reset_only"
    reason: str
    target_word: str
    target_meaning: str
    target_explain: str
    sentence_en: str
    sentence_ko: str

class ApplyRequest(BaseModel):
    actions: List[DiagnoseResultItem]

@router.get("/candidates")
def get_candidates(limit: int = 100):
    """
    Vocabulary 덱에서 Ease <= 1.3 (130%) 이거나 Lapses >= 4인 만성 오답 카드 추출.
    역대 최다 오답(Lapses) 내림차순, 총 복습수 내림차순 정렬.
    """
    try:
        # AnkiConnect search
        query = f'note:"{MODEL_VOCAB}" (prop:ease<=1.3 OR prop:lapses>=4) -is:suspended'
        card_ids = AnkiConnector.invoke("findCards", query=query)
        total_remaining = len(card_ids)

        if not card_ids:
            return {
                "status": "success",
                "total_remaining": 0,
                "candidates": []
            }

        # Process in chunks to fetch cards info
        chunk_size = 2000
        cards_info = []
        for i in range(0, min(len(card_ids), 3000), chunk_size):
            chunk = card_ids[i:i+chunk_size]
            cards_info.extend(AnkiConnector.invoke("cardsInfo", cards=chunk))

        # Sort by lapses desc, reps desc
        cards_info.sort(key=lambda c: (c.get("lapses", 0), c.get("reps", 0)), reverse=True)
        top_cards = cards_info[:limit]

        # Fetch notesInfo for rich fields
        note_ids = [c["note"] for c in top_cards]
        notes_info = AnkiConnector.invoke("notesInfo", notes=note_ids)
        notes_dict = {n["noteId"]: n for n in notes_info}

        candidates = []
        seen_notes = set()
        for c in top_cards:
            nid = c["note"]
            if nid in seen_notes:
                continue
            seen_notes.add(nid)

            note_data = notes_dict.get(nid, {})
            fields = note_data.get("fields", {})

            w = html.unescape(fields.get("단어", {}).get("value", "")).strip()
            m = html.unescape(fields.get("뜻", {}).get("value", "")).strip()
            p = html.unescape(fields.get("품사", {}).get("value", "")).strip()
            exp = html.unescape(fields.get("설명", {}).get("value", "")).strip()
            ex = html.unescape(fields.get("예문", {}).get("value", "")).strip()

            candidates.append({
                "id": nid,
                "card_id": c["cardId"],
                "word": w,
                "meaning": m,
                "pos": p,
                "explain": exp,
                "example": ex,
                "lapses": c.get("lapses", 0),
                "reps": c.get("reps", 0),
                "ease": round((c.get("factor", 0) / 10.0), 1),
                "interval": c.get("interval", 0)
            })

        return {
            "status": "success",
            "total_remaining": total_remaining,
            "candidates": candidates
        }
    except Exception as e:
        logger.error(f"Error fetching candidates: {e}")
        return {
            "status": "error",
            "message": str(e),
            "total_remaining": 0,
            "candidates": []
        }

@router.post("/diagnose")
def diagnose_leeches(req: DiagnoseRequest):
    """
    Gemini AI를 활용해 망각 단어들의 실패 원인을 진단하고 맞춤형 최적 조치 제안.
    - revamp_idiom: 자주 쓰이는 이디엄/청크/동사구 표현으로 재포장 (단어 표기 표준화 A, B, V 적용)
    - revamp_collocation: 단어는 유지하되 필수 짝꿍 표현과 뉘앙스를 뜻/설명에 강조
    - sentence: 통문장으로 체화할 수 있도록 Sentence 덱으로 승격
    - delete: 지엽적이거나 사어/불필요 중복인 경우 영구 삭제
    """
    candidates = req.candidates
    if not candidates:
        return {"status": "error", "message": "진단할 단어가 없습니다."}

    client = genai.Client(api_key=GOOGLE_API_KEY)
    chunk_size = 10
    chunks = [candidates[i:i + chunk_size] for i in range(0, len(candidates), chunk_size)]
    results = []

    sys_instruct = """당신은 인지언어학 기반 영어 어휘 학습 설계 전문가입니다.
학생이 Anki에서 수십 번 반복해서 틀리는 만성 망각(Leech) 단어들을 정밀 진단하고, 각 단어에 최적화된 처방을 내려주세요.

[처방 액션 기준]
1. "revamp_idiom" (최우선 고려):
   - 외톨이 단어(단일 동사/형용사/명사)로 외우기 어렵고, 원어민들이 특정 숙어나 구동사, 덩어리 표현(Chunk)으로 압도적으로 많이 쓰는 경우.
   - 단어 필드 자체를 'make a nuisance of oneself', 'spring A on B', 'be at a loss to V' 처럼 자주 쓰이는 실전 표현으로 재포장합니다.
   - 숙어의 대상(누가, 무엇을)은 반드시 대문자 'A', 'B', 'V' 등으로 표준화하십시오. (sb, sth 쓰지 말 것)
2. "revamp_collocation":
   - 단어 자체는 독립형으로 익혀야 하지만, 앞뒤 전치사나 짝꿍 명사/형용사(연어) 힌트 및 뉘앙스 구별이 명확하지 않아 틀리는 경우.
   - 뜻과 설명에 짝꿍 표현과 구체적 쓰임새를 명확히 보강합니다.
3. "sentence":
   - 단어의 뉘앙스가 추상적이거나 맥락(문맥) 없이 뜻만 외우는 것이 불가능하여, 실전 통문장으로 입에 붙여야 하는 경우.
4. "delete":
   - 현대 영어에서 거의 쓰이지 않는 고어/사어이거나, 너무 지엽적인 전문용어, 또는 이미 다른 카드로 충분히 대체 가능한 불필요한 단어인 경우.

반드시 유효한 JSON 형식으로만 응답해야 하며, 아래 필드를 포함하는 객체 리스트를 'diagnoses' 키에 담아 반환하세요:
[
  {
    "id": (전달받은 noteId 정수),
    "card_id": (전달받은 cardId 정수),
    "word": "(기존 단어)",
    "action": "revamp_idiom" | "revamp_collocation" | "sentence" | "delete",
    "reason": "한 줄로 작성한 구체적 처방 사유 (예: '단독 어휘보다 make a ~ of oneself 덩어리로 외워야 발화 가능')",
    "target_word": "개편될 단어 표기 (revamp_idiom이면 청크 표현, 아니면 기존 단어)",
    "target_meaning": "핵심을 찌르는 명확하고 자연스러운 한국어 뜻",
    "target_explain": "3단계 설명 (①구체적 뉘앙스, ②유의어 대비, ③자주 쓰이는 콜로케이션)",
    "sentence_en": "실제 미국/영국 구어에서 흔히 쓰는 자연스러운 영어 예문",
    "sentence_ko": "예문의 자연스러운 한국어 번역"
  }
]"""

    def process_chunk(chunk):
        items_summary = []
        for c in chunk:
            items_summary.append({
                "id": c.id,
                "card_id": c.card_id,
                "word": c.word,
                "meaning": c.meaning,
                "pos": c.pos,
                "lapses": c.lapses,
                "explain": c.explain[:100] if c.explain else ""
            })
        prompt = f"다음 단어 목록을 분석하고 최적 처방을 JSON으로 작성하세요:\n{json.dumps(items_summary, ensure_ascii=False)}"
        try:
            resp = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=[sys_instruct, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3
                )
            )
            raw = json.loads(resp.text, strict=False)
            if isinstance(raw, dict) and "diagnoses" in raw:
                return raw["diagnoses"]
            elif isinstance(raw, list):
                return raw
            return []
        except Exception as err:
            logger.error(f"Diagnose chunk failed: {err}")
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_chunk, ch) for ch in chunks]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                results.extend(res)

    # Map results by note ID to ensure order and completeness
    result_map = {r.get("id"): r for r in results if isinstance(r, dict) and "id" in r}
    final_diagnoses = []
    for c in candidates:
        diag = result_map.get(c.id)
        if diag:
            final_diagnoses.append(diag)
        else:
            # Fallback diagnosis if AI failed on a specific item
            final_diagnoses.append({
                "id": c.id,
                "card_id": c.card_id,
                "word": c.word,
                "action": "revamp_collocation",
                "reason": "단어 기본 뉘앙스 및 콜로케이션 재보강 추천",
                "target_word": c.word,
                "target_meaning": c.meaning,
                "target_explain": c.explain,
                "sentence_en": c.example,
                "sentence_ko": ""
            })

    return {
        "status": "success",
        "count": len(final_diagnoses),
        "diagnoses": final_diagnoses
    }

@router.post("/apply")
def apply_leech_actions(req: ApplyRequest):
    """
    사용자가 검토 및 조정한 조치 리스트를 Anki에 일괄 반영:
    1. revamp_idiom: 단어/뜻/설명 업데이트 + 오디오 갱신 + Ease 250% 복구
    2. revamp_collocation: 뜻/설명 업데이트 + Ease 250% 복구
    3. sentence: English Sentence 덱에 신규 예문 추가(TTS 포함) + 원본 Ease 250% 복구
    4. delete: Anki에서 해당 노트 영구 삭제
    """
    actions = req.actions
    if not actions:
        return {"status": "error", "message": "적용할 항목이 없습니다."}

    summary = {
        "revamped_idioms": 0,
        "revamped_collocations": 0,
        "sentences_added": 0,
        "deleted": 0,
        "eases_reset": 0,
        "errors": []
    }

    cards_to_reset_ease = []
    notes_to_delete = []
    sentences_to_add = []

    for item in actions:
        nid = item.id
        cid = item.card_id
        act = item.action

        try:
            if act == "delete":
                notes_to_delete.append(nid)
                summary["deleted"] += 1
                continue

            if act == "revamp_idiom":
                # Update fields
                fields_to_update = {
                    "단어": item.target_word,
                    "뜻": item.target_meaning,
                    "설명": item.target_explain
                }
                if item.sentence_en:
                    fields_to_update["예문"] = item.sentence_en

                # Regenerate audio for the new idiom expression
                tag, _ = AnkiTTSFiller.generate_gtts(item.target_word)
                if tag:
                    fields_to_update["소리"] = tag

                AnkiConnector.update_note_fields(nid, fields_to_update)
                cards_to_reset_ease.append(cid)
                summary["revamped_idioms"] += 1

            elif act == "revamp_collocation":
                fields_to_update = {
                    "뜻": item.target_meaning,
                    "설명": item.target_explain
                }
                if item.sentence_en:
                    fields_to_update["예문"] = item.sentence_en

                AnkiConnector.update_note_fields(nid, fields_to_update)
                cards_to_reset_ease.append(cid)
                summary["revamped_collocations"] += 1

            elif act == "sentence":
                # Add to sentence deck
                if item.sentence_en and item.sentence_ko:
                    sentences_to_add.append({
                        "sentence": item.sentence_en,
                        "translation": item.sentence_ko
                    })
                    summary["sentences_added"] += 1
                cards_to_reset_ease.append(cid)

            elif act == "reset_only":
                cards_to_reset_ease.append(cid)

        except Exception as e:
            summary["errors"].append(f"{item.word}: {str(e)}")

    # 1. Batch delete
    if notes_to_delete:
        try:
            AnkiConnector.invoke("deleteNotes", notes=notes_to_delete)
        except Exception as e:
            summary["errors"].append(f"Delete notes failed: {e}")

    # 2. Batch add sentences
    if sentences_to_add:
        for s in sentences_to_add:
            try:
                AnkiConnector.add_note(DECK_SENTENCE, MODEL_SENTENCE, {
                    "문장": s["sentence"],
                    "해설": s["translation"]
                })
            except Exception as e:
                pass
        # Add audio and organize sentences
        try:
            AnkiTTSFiller.run_audio_addition()
            run_organizer()
        except Exception as e:
            pass

    # 3. Batch reset Ease factors to 250% (2500)
    if cards_to_reset_ease:
        try:
            # AnkiConnect setEaseFactors takes cards and easeFactors
            ease_factors = [2500] * len(cards_to_reset_ease)
            AnkiConnector.invoke("setEaseFactors", cards=cards_to_reset_ease, easeFactors=ease_factors)
            summary["eases_reset"] = len(cards_to_reset_ease)
        except Exception as e:
            summary["errors"].append(f"Ease reset failed: {e}")

    return {
        "status": "success",
        "message": f"총 {len(actions)}개 카드 중 이디엄 개편 {summary['revamped_idioms']}개, 콜로케이션 보강 {summary['revamped_collocations']}개, 문장 추가 {summary['sentences_added']}개, 삭제 {summary['deleted']}개, Ease 정상화 {summary['eases_reset']}개를 완료했습니다.",
        "summary": summary
    }
