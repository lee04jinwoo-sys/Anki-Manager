from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CardStatusResponse(BaseModel):
    anki_connected: bool
    gateway: str = "Anki Manager Gateway v2"
    anki_url: str

class SentenceItem(BaseModel):
    sentence: str
    translation: Optional[str] = ""

class SentenceCreateRequest(BaseModel):
    sentence: str
    translation: Optional[str] = ""
    auto_enrich: bool = True
    generate_audio: bool = True

class SentenceBulkCreateRequest(BaseModel):
    items: List[SentenceItem]
    auto_enrich: bool = True
    generate_audio: bool = True

class VocabItem(BaseModel):
    word: str
    meaning: Optional[str] = ""
    pos: Optional[str] = ""
    synonyms: Optional[str] = "" # Received for compatibility, strictly cleared internally
    example: Optional[str] = ""
    explanation: Optional[str] = ""

class VocabCreateRequest(BaseModel):
    word: str
    meaning: Optional[str] = ""
    pos: Optional[str] = ""
    synonyms: Optional[str] = "" # Ignored, set to ""
    example: Optional[str] = ""
    explanation: Optional[str] = ""
    auto_enrich: bool = True
    generate_audio: bool = True

class VocabBulkCreateRequest(BaseModel):
    items: List[VocabItem]
    auto_enrich: bool = False
    generate_audio: bool = True

class GrammarCreateRequest(BaseModel):
    sentence: str                      # 완성 문장 (정답이 들어간 형태)
    answer: str                        # 문장 속에서 빈칸이 될 부분
    distractors: List[str] = Field(default_factory=list)  # 주어진 오답 (예: 학습자가 실제로 쓴 틀린 형태), 최대 3개
    translation: Optional[str] = ""    # 해설. 비면 생성
    explanation: Optional[str] = ""    # 설명. 비면 생성
    auto_enrich: bool = True
    generate_audio: bool = True

class CardResponse(BaseModel):
    success: bool
    note_id: Optional[int] = None
    duplicate: bool = False
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class BulkCardResponse(BaseModel):
    success: bool
    count: int = 0
    total: int = 0
    skipped: int = 0  # 중복 등으로 추가할 수 없어 건너뛴 노트 수
    error: Optional[str] = None
