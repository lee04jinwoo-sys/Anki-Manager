import re
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import MODEL_VOCAB, MODEL_SENTENCE, MODEL_GRAMMAR
from integrations.anki_connect import AnkiConnector
from core.link_manager import (
    LinkManager, backup_templates, clean_text, init_db
)
from core.batch_generator import BatchSentenceGenerator
from backend.services.corpus_service import evaluate_expression_rank_and_tier
from backend.services.leech_service import suggest_action

logger = logging.getLogger("LinksRouter")
router = APIRouter(prefix="/api/links", tags=["links"])


class BatchGenerateRequest(BaseModel):
    words: List[Dict[str, Any]] = Field(description="선택된 단어 목록 [{'note_id': ..., 'word': ..., 'meaning': ...}]")
    generate_audio: bool = Field(default=True, description="TTS 오디오 동시 생성 여부")
    lang: str = Field(default="en", description="언어 코드 (en, zh)")


@router.get("/stats")
def get_stats(lang: str = Query("en", description="언어 코드 (en, zh)")):
    """전체 통계 요약 조회"""
    try:
        return LinkManager.get_stats(lang=lang)
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vocab")
def get_vocab_list(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    filter_mode: Optional[str] = Query(None, description="필터 모드 (leech, zero, low, all)"),
    max_links: Optional[int] = Query(None, description="최대 연결 수 필터 (예: 0개, 1개 이하)"),
    search: Optional[str] = Query(None, description="단어 또는 뜻 검색"),
    lang: str = Query("en", description="언어 코드 (en, zh)")
):
    """연결 적은 순 정렬 단어 목록 조회"""
    try:
        res = LinkManager.get_vocab_list(
            limit=limit,
            offset=offset,
            filter_mode=filter_mode,
            max_links=max_links,
            search=search,
            lang=lang
        )
        if filter_mode == "leech" and lang == "en":
            # 단어별 처리 방법 추천 (영어 전용 로컬 코퍼스 DB 조회)
            for item in res.get("items", []):
                _, tier = evaluate_expression_rank_and_tier(item.get("word", ""))
                item["tier"] = tier
                item["suggestion"] = suggest_action(
                    word=item.get("word", ""), lapses=int(item.get("lapses", 0) or 0),
                    link_count=int(item.get("link_count", 0) or 0), tier=tier, pos=item.get("pos", ""),
                )
        return res
    except Exception as e:
        logger.error(f"단어 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/random")
def get_random_unlinked(
    count: int = Query(20, ge=1, le=50, description="추출할 랜덤 단어 수"),
    lang: str = Query("en", description="언어 코드 (en, zh)")
):
    """미연결 단어 중 무작위 N개 추출"""
    try:
        items = LinkManager.get_random_unlinked_vocab(count=count, lang=lang)
        return {"count": len(items), "items": items}
    except Exception as e:
        logger.error(f"랜덤 단어 추출 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leech")
def get_leech_unlinked(
    count: int = Query(20, ge=1, le=50, description="추출할 최다 오답 단어 수"),
    lang: str = Query("en", description="언어 코드 (en, zh)")
):
    """미연결 단어 중 가장 많이 틀린(Lapses 많은 순) N개 추출"""
    try:
        items = LinkManager.get_worst_leech_unlinked_vocab(count=count, lang=lang)
        return {"count": len(items), "items": items}
    except Exception as e:
        logger.error(f"최다 오답 단어 추출 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan")
def scan_and_rebuild(lang: str = Query("en", description="언어 코드 (en, zh)")):
    """100% 완전 자동 전체 재스캔 및 links.db 갱신"""
    try:
        result = LinkManager.scan_and_rebuild_links(lang=lang)
        return {"success": True, "message": f"[{lang.upper()}] 스캔 및 링크 동기화가 완료되었습니다.", "data": result}
    except Exception as e:
        logger.error(f"스캔 실패: {e}")
        raise HTTPException(status_code=500, detail=f"스캔 실패: {e}")


@router.post("/batch-generate")
def batch_generate_sentences(req: BatchGenerateRequest):
    """선택한 단어들에 대해 AI 문장 + TTS 일괄 생성 및 등록"""
    if not req.words:
        raise HTTPException(status_code=400, detail="선택된 단어가 없습니다.")
    try:
        generator = BatchSentenceGenerator()
        result = generator.generate_and_add_sentences(
            words_data=req.words,
            generate_audio=req.generate_audio,
            lang=req.lang
        )
        return result
    except Exception as e:
        logger.error(f"일괄 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply-templates")
def apply_card_templates():
    """
    기존 템플릿을 백업한 후, English Vocabulary 및 English Sentence 카드의
    뒷면(Back)에 연결 뱃지 스크립트를 안전하게 주입합니다.
    """
    try:
        # 1. 원본 템플릿 백업
        backup_path = backup_templates()
        logger.info(f"템플릿 원본 백업 완료: {backup_path}")

        # 2. English Vocabulary 템플릿 정리 (단어 카드에는 문장 개수 뱃지를 완전히 제거)
        vocab_templates = AnkiConnector.invoke("modelTemplates", modelName=MODEL_VOCAB)
        updated_vocab_templates = {}
        for cname, cdata in vocab_templates.items():
            back = cdata["Back"]
            # 기존 주입 태그 완전 제거하여 원상 복구
            back = re.sub(r"<!-- ANKI_LINK_MANAGER_VOCAB -->.*?<!-- /ANKI_LINK_MANAGER_VOCAB -->\n?", "", back, flags=re.DOTALL)
            updated_vocab_templates[cname] = {
                "Front": cdata["Front"],
                "Back": back.strip()
            }

        AnkiConnector.invoke("updateModelTemplates", model={"name": MODEL_VOCAB, "templates": updated_vocab_templates})

        # 3. English Sentence 템플릿 주입 (인라인 밑줄 & 어휘 강조)
        from scripts.update_sentence_highlight import SENTENCE_BACK_TEMPLATE
        sentence_templates = AnkiConnector.invoke("modelTemplates", modelName=MODEL_SENTENCE)
        updated_sentence_templates = {}
        for cname, cdata in sentence_templates.items():
            updated_sentence_templates[cname] = {
                "Front": cdata["Front"],
                "Back": SENTENCE_BACK_TEMPLATE if cname == "Card 1" else cdata["Back"]
            }
        AnkiConnector.invoke("updateModelTemplates", model={"name": MODEL_SENTENCE, "templates": updated_sentence_templates})

        # 4. English Grammar 템플릿 주입 (Card 1 알약 제거, Card 3 인라인 강조)
        try:
            grammar_templates = AnkiConnector.invoke("modelTemplates", modelName=MODEL_GRAMMAR)
            updated_grammar_templates = {}
            for cname, cdata in grammar_templates.items():
                back = cdata["Back"]
                # 기존 알약 뱃지 태그 완전 제거
                back = re.sub(r"<!-- ANKI_LINK_MANAGER_SENTENCE -->.*?<!-- /ANKI_LINK_MANAGER_SENTENCE -->\n?", "", back, flags=re.DOTALL)
                if cname == "Card 3":
                    back = SENTENCE_BACK_TEMPLATE

                updated_grammar_templates[cname] = {
                    "Front": cdata["Front"],
                    "Back": back.strip()
                }
            AnkiConnector.invoke("updateModelTemplates", model={"name": MODEL_GRAMMAR, "templates": updated_grammar_templates})
        except Exception as ge:
            logger.warning(f"English Grammar 템플릿 주입 건너뜀: {ge}")


        return {
            "success": True,
            "message": "기존 템플릿 백업 완료 후 새 뱃지 스크립트가 성공적으로 주입되었습니다.",
            "backup_file": backup_path
        }
    except Exception as e:
        logger.error(f"템플릿 적용 실패: {e}")
        raise HTTPException(status_code=500, detail=f"템플릿 적용 실패: {e}")


@router.get("/badge/vocab")
def get_vocab_badge(
    word: str = Query(..., description="조회할 단어"),
    lang: str = Query("en", description="언어 코드 (en, zh)")
):
    """Vocab 카드 뒷면 비동기 호출용: 연결된 문장 수 반환"""
    try:
        sentences = LinkManager.get_linked_sentences_for_vocab(word, lang=lang)
        return {"word": word, "count": len(sentences)}
    except Exception as e:
        logger.error(f"Vocab 뱃지 조회 실패: {e}")
        return {"word": word, "count": 0}


@router.get("/badge/sentence")
def get_sentence_badge(
    text: str = Query(..., description="조회할 문장 텍스트"),
    lang: str = Query("en", description="언어 코드 (en, zh)")
):
    """Sentence 카드 뒷면 비동기 호출용: 포함된 어휘 목록 및 뜻 반환"""
    try:
        items = LinkManager.get_linked_vocab_for_sentence(text, lang=lang)
        words = [item["word"] for item in items]
        return {"sentence": text, "words": words, "items": items}
    except Exception as e:
        logger.error(f"Sentence 뱃지 조회 실패: {e}")
        return {"sentence": text, "words": [], "items": []}
