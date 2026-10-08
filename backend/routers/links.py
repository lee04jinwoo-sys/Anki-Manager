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

logger = logging.getLogger("LinksRouter")
router = APIRouter(prefix="/api/links", tags=["links"])


class BatchGenerateRequest(BaseModel):
    words: List[Dict[str, Any]] = Field(description="선택된 단어 목록 [{'note_id': ..., 'word': ..., 'meaning': ...}]")
    generate_audio: bool = Field(default=True, description="TTS 오디오 동시 생성 여부")


@router.get("/stats")
def get_stats():
    """전체 통계 요약 조회"""
    try:
        return LinkManager.get_stats()
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vocab")
def get_vocab_list(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    max_links: Optional[int] = Query(None, description="최대 연결 수 필터 (예: 0개, 1개 이하)"),
    search: Optional[str] = Query(None, description="단어 또는 뜻 검색")
):
    """연결 적은 순 정렬 단어 목록 조회"""
    try:
        return LinkManager.get_vocab_list(
            limit=limit,
            offset=offset,
            max_links=max_links,
            search=search
        )
    except Exception as e:
        logger.error(f"단어 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/random")
def get_random_unlinked(count: int = Query(20, ge=1, le=50, description="추출할 랜덤 단어 수")):
    """미연결 단어 중 무작위 N개 추출"""
    try:
        items = LinkManager.get_random_unlinked_vocab(count=count)
        return {"count": len(items), "items": items}
    except Exception as e:
        logger.error(f"랜덤 단어 추출 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leech")
def get_leech_unlinked(count: int = Query(20, ge=1, le=50, description="추출할 최다 오답 단어 수")):
    """미연결 단어 중 가장 많이 틀린(Lapses 많은 순) N개 추출"""
    try:
        items = LinkManager.get_worst_leech_unlinked_vocab(count=count)
        return {"count": len(items), "items": items}
    except Exception as e:
        logger.error(f"최다 오답 단어 추출 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan")
def scan_and_rebuild():
    """100% 완전 자동 전체 재스캔 및 links.db 갱신"""
    try:
        result = LinkManager.scan_and_rebuild_links()
        return {"success": True, "message": "스캔 및 링크 동기화가 완료되었습니다.", "data": result}
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
            generate_audio=req.generate_audio
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

        # 3. English Sentence 템플릿 주입
        sentence_templates = AnkiConnector.invoke("modelTemplates", modelName=MODEL_SENTENCE)
        sentence_badge_html = """
<!-- ANKI_LINK_MANAGER_SENTENCE -->
<div class="synonyms-box" id="alm-sentence-box" style="display:none; margin: 10px auto 14px;"></div>
<script>
(function() {
  var raw = "{{문장}}";
  var s = raw.replace(/<[^>]+>/g, '').trim();
  if (!s) return;
  fetch("http://127.0.0.1:8001/api/links/badge/sentence?text=" + encodeURIComponent(s))
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d && d.words && d.words.length > 0) {
        var box = document.getElementById("alm-sentence-box");
        if (box) {
          box.innerHTML = d.words.map(function(w) {
            return '<span class="synonym-tag">' + w + '</span>';
          }).join("");
          box.style.display = "flex";
        }
      }
    })
    .catch(function() {});
})();
</script>
<style>
.card #alm-sentence-box,
#alm-sentence-box {
  display: flex !important;
  flex-wrap: wrap !important;
  justify-content: center !important;
  gap: 6px !important;
  margin: 10px auto 14px !important;
}
.card #alm-sentence-box .synonym-tag,
#alm-sentence-box .synonym-tag {
  font-family: '나눔고딕', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  padding: 4px 12px !important;
  border-radius: 999px !important;
  background: #f3f4f6 !important;
  color: #374151 !important;
  border: 1px solid #d1d5db !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
  display: inline-block !important;
  line-height: 1.5 !important;
}
.card.nightMode #alm-sentence-box .synonym-tag,
.nightMode #alm-sentence-box .synonym-tag {
  background: #374151 !important;
  color: #d1d5db !important;
  border-color: #4b5563 !important;
}
</style>
<!-- /ANKI_LINK_MANAGER_SENTENCE -->
"""
        updated_sentence_templates = {}
        for cname, cdata in sentence_templates.items():
            back = cdata["Back"]
            # 기존 주입 태그 제거
            back = re.sub(r"<!-- ANKI_LINK_MANAGER_SENTENCE -->.*?<!-- /ANKI_LINK_MANAGER_SENTENCE -->\n?", "", back, flags=re.DOTALL)
            # {{문장}} 태그 바로 뒤(문장 바로 밑)에 삽입
            if "{{문장}}" in back:
                pattern = r"({{문장}}.*?</div>)"
                if re.search(pattern, back, flags=re.DOTALL):
                    back = re.sub(pattern, r"\1\n" + sentence_badge_html.strip(), back, count=1, flags=re.DOTALL)
                else:
                    back = back + "\n" + sentence_badge_html.strip()
            else:
                back = back + "\n" + sentence_badge_html.strip()

            updated_sentence_templates[cname] = {
                "Front": cdata["Front"],
                "Back": back
            }

        AnkiConnector.invoke("updateModelTemplates", model={"name": MODEL_SENTENCE, "templates": updated_sentence_templates})

        # 4. English Grammar 템플릿 주입 (Card 3 Sentence 카드 포함)
        try:
            grammar_templates = AnkiConnector.invoke("modelTemplates", modelName=MODEL_GRAMMAR)
            updated_grammar_templates = {}
            for cname, cdata in grammar_templates.items():
                back = cdata["Back"]
                back = re.sub(r"<!-- ANKI_LINK_MANAGER_SENTENCE -->.*?<!-- /ANKI_LINK_MANAGER_SENTENCE -->\n?", "", back, flags=re.DOTALL)
                if "{{문장}}" in back:
                    pattern = r"({{문장}}.*?</div>)"
                    if re.search(pattern, back, flags=re.DOTALL):
                        back = re.sub(pattern, r"\1\n" + sentence_badge_html.strip(), back, count=1, flags=re.DOTALL)
                    else:
                        back = back + "\n" + sentence_badge_html.strip()
                else:
                    back = back + "\n" + sentence_badge_html.strip()

                updated_grammar_templates[cname] = {
                    "Front": cdata["Front"],
                    "Back": back
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
def get_vocab_badge(word: str = Query(..., description="조회할 단어")):
    """Vocab 카드 뒷면 비동기 호출용: 연결된 문장 수 반환"""
    try:
        sentences = LinkManager.get_linked_sentences_for_vocab(word)
        return {"word": word, "count": len(sentences)}
    except Exception as e:
        logger.error(f"Vocab 뱃지 조회 실패: {e}")
        return {"word": word, "count": 0}


@router.get("/badge/sentence")
def get_sentence_badge(text: str = Query(..., description="조회할 문장 텍스트")):
    """Sentence 카드 뒷면 비동기 호출용: 포함된 어휘 목록 반환"""
    try:
        words = LinkManager.get_linked_vocab_for_sentence(text)
        return {"sentence": text, "words": words}
    except Exception as e:
        logger.error(f"Sentence 뱃지 조회 실패: {e}")
        return {"sentence": text, "words": []}
