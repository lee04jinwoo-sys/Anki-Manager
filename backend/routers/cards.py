import logging
from fastapi import APIRouter, HTTPException, status
from backend.schemas.cards import (
    CardStatusResponse,
    SentenceCreateRequest, SentenceBulkCreateRequest,
    VocabCreateRequest, VocabBulkCreateRequest, GrammarCreateRequest,
    CardResponse, BulkCardResponse
)
from backend.services import card_service

logger = logging.getLogger("CardsRouter")
router = APIRouter(prefix="/api/cards", tags=["Cards Gateway"])


@router.api_route("/status", methods=["GET", "HEAD"], response_model=CardStatusResponse)
def get_gateway_status() -> CardStatusResponse:
    """AnkiConnect 연결 상태 및 중앙 게이트웨이 헬스체크"""
    return card_service.check_anki_status()


@router.post("/launch")
def launch_anki():
    """Anki 데스크톱 앱 실행 (macOS)"""
    res = card_service.launch_anki_app()
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=res.get("error"))
    return res


@router.post("/sentence", response_model=CardResponse)
def add_sentence(req: SentenceCreateRequest) -> CardResponse:
    """단일 문장 카드 등록 (오디오/AI번역/링크 인덱싱 포함)"""
    res = card_service.create_sentence_card(req)
    if not res.success and not res.duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.error or "Failed to add sentence card")
    return res


@router.post("/sentence/bulk", response_model=BulkCardResponse)
def bulk_add_sentences(req: SentenceBulkCreateRequest) -> BulkCardResponse:
    """다중 문장 카드 병렬 등록"""
    res = card_service.create_bulk_sentences(req)
    if not res.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.error or "Failed to bulk add sentence cards")
    return res


@router.post("/vocab", response_model=CardResponse)
def add_vocab(req: VocabCreateRequest) -> CardResponse:
    """단일 단어 카드 등록 (플레이스홀더 정규화, 유의어 제거, gTTS, 링크 인덱싱)"""
    res = card_service.create_vocab_card(req)
    if not res.success and not res.duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.error or "Failed to add vocab card")
    return res


@router.post("/vocab/bulk", response_model=BulkCardResponse)
def bulk_add_vocabs(req: VocabBulkCreateRequest) -> BulkCardResponse:
    """다중 단어 카드 병렬 등록"""
    res = card_service.create_bulk_vocabs(req)
    if not res.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.error or "Failed to bulk add vocab cards")
    return res


@router.post("/grammar", response_model=CardResponse)
def add_grammar(req: GrammarCreateRequest) -> CardResponse:
    """문법 객관식 카드 등록 (정답 빈칸 검증, 누락 필드 보강, 오디오, 링크 인덱싱)"""
    res = card_service.create_grammar_card(req)
    if not res.success and not res.duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.error or "Failed to add grammar card")
    return res
