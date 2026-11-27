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
    use_free_router: bool = True  # True면 무료 등급 모델부터 시도 (기본 활성화)
    tags: List[str] = Field(default_factory=list)

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
    explanation: Optional[str] = "" # Ignored (설명 필드 제거)

class VocabCreateRequest(BaseModel):
    word: str
    meaning: Optional[str] = ""
    pos: Optional[str] = ""
    synonyms: Optional[str] = "" # Ignored, set to ""
    example: Optional[str] = ""
    explanation: Optional[str] = "" # Ignored (설명 필드 제거)
    auto_enrich: bool = True
    generate_audio: bool = True
    use_free_router: bool = True  # True면 무료 등급 모델부터 시도 (기본 활성화)
    tags: List[str] = Field(default_factory=list)

class VocabBulkCreateRequest(BaseModel):
    items: List[VocabItem]
    auto_enrich: bool = False
    generate_audio: bool = True

class GrammarCreateRequest(BaseModel):
    sentence: str                      # 완성 문장 (정답이 들어간 형태)
    answer: str                        # 문장 속에서 빈칸이 될 부분
    distractors: List[str] = Field(default_factory=list)  # 주어진 오답 (예: 학습자가 실제로 쓴 틀린 형태), 최대 3개
    translation: Optional[str] = ""    # 해설. 비면 생성
    explanation: Optional[str] = ""    # Ignored (설명 필드 제거)
    auto_enrich: bool = True
    generate_audio: bool = True
    tags: List[str] = Field(default_factory=list)

class KnowledgeCreateRequest(BaseModel):
    """learning 저장소(study.py)가 보내는 지식 카드. 내용은 보내는 쪽이 정하고 보강하지 않는다."""
    question: str                      # 질문 (앞면, 중복 판정 기준)
    answer: str                        # 정답
    explanation: Optional[str] = ""    # 설명 (왜 그런지, 흔한 실수)
    topic: Optional[str] = ""          # 주제 (과목명)
    source: Optional[str] = ""         # 출처 (자료명 p.N)
    tags: List[str] = Field(default_factory=list)

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
