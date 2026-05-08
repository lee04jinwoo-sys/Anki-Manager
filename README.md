# Anki Manager 🚀

Anki Manager는 Google Gemini AI를 활용하여 영어 학습 카드를 자동으로 생성, 보강 및 관리하는 강력한 CLI 도구입니다. YouTube 자막, 웹사이트, Notion, Obsidian 등 다양한 소스에서 데이터를 추출하여 고품질의 Anki 노트를 만들어줍니다.

---

## 📂 디렉토리 구조 (Directory Structure)

```text
Anki Manager/
├── collectors/          # 데이터 추출 모듈 (Data Fetchers)
│   ├── youtube.py       # YouTube 자막 추출
│   ├── obsidian.py      # Obsidian Inbox 메모 로드
│   └── local_file.py    # 로컬 마크다운 파일 읽기
├── core/                # 핵심 로직 (AI & Processing)
│   ├── generator.py     # 주제별 상황/표현 AI 생성 (Smart Discovery)
│   ├── selector.py      # 추출된 텍스트에서 학습 가치 높은 문장/어휘 선별
│   └── completer.py     # AI를 통한 카드 내용 보강 (뜻, 예문, 설명 등)
├── integrations/        # 외부 서비스 연동 (External Services)
│   ├── anki_connect.py  # AnkiConnect API 통신 (노트 추가, 디자인 업데이트)
│   ├── audio.py         # Google TTS를 이용한 음성 생성 및 Anki 주입
│   └── obsidian.py      # Obsidian 연동 유틸리티
├── utils/               # 유틸리티 및 관리 도구 (Utilities)
│   ├── ui.py            # CLI 인터페이스 및 터미널 출력 관리
│   ├── stats.py         # Anki 덱 통계 및 학습 현황 분석
│   ├── organizer.py     # 노트 타입별 덱 자동 분류
│   ├── cluster.py       # 유의어 그룹화 및 클러스터링 분석
│   ├── cleaner.py       # 중복 카드 제거 및 리치(Leech) 카드 관리
│   ├── schema_updater.py# 설정 파일(JSON) 디자인을 Anki에 동기화
│   ├── schema_exporter.py# Anki 모델 디자인을 설정 파일로 내보내기
│   └── synonym_sync.py  # 유의어 필드 동기화
├── data/                # 설정 및 데이터 저장
│   └── user_config.json # 카드 모델, 스타일, 템플릿 등 사용자 설정
├── main.py              # 프로그램 메인 실행 파일 (Interactive CLI)
├── config.py            # 전역 환경 설정 및 파일 로드 로직
└── config.json          # 시스템 기본 설정 데이터
```

---

## 🛠 주요 스크립트 역할 (Script Roles)

### 1. `main.py`
프로그램의 엔트리 포인트입니다. 대화형 메뉴를 통해 전체 워크플로우를 실행하거나 특정 관리 도구(통계, 오디오 생성, 중복 제거 등)를 호출합니다.

### 2. `core/completer.py`
AI(Gemini)를 사용하여 단순한 단어나 문장에 풍부한 정보를 덧붙입니다. 한글 뜻, 품사, 유의어, 상세한 뉘앙스 설명, 그리고 원어민스러운 예문을 생성하여 고품질 카드를 완성합니다.

### 3. `integrations/audio.py`
Anki에 추가된 노트를 스캔하여 오디오가 없는 항목에 대해 Google Cloud TTS를 사용하여 음성 파일을 생성하고 Anki 미디어 폴더에 저장합니다.

### 4. `utils/schema_updater.py`
`data/user_config.json`에 정의된 CSS 스타일과 카드 템플릿(HTML)을 실제 Anki 앱에 즉시 적용합니다. Anki 앱 안에서 복잡하게 수정할 필요 없이 설정 파일만으로 디자인을 관리할 수 있게 해줍니다.

---

## 📖 메뉴별 실행 흐름 (Menu Execution Flow)

각 메뉴 선택 시 내부적으로 작동하는 스크립트 순서는 다음과 같습니다:

1. **자동화 워크플로우 (URL, Notion, Situ, Obsidian)**
   - `collectors/*.py` (데이터 추출) → `core/selector.py` (AI 선별) → `core/completer.py` (AI 보강) → `integrations/anki_connect.py` (노트 추가) → `integrations/audio.py` (오디오 생성) → `utils/organizer.py` (덱 분류)

2. **Anki 덱 통계 분석**
   - `utils/stats.py` (학습 통계 및 고갈일 계산)

3. **누락된 오디오 생성**
   - `integrations/audio.py` (미디어가 비어있는 노트 스캔 및 TTS 주입)

4. **카드 자동 정리 (Deck 이동)**
   - `utils/organizer.py` (설정된 규칙에 따라 노트를 하위 덱으로 자동 분배)

5. **중복 카드 제거**
   - `utils/cleaner.py` (동일한 단어/문장을 가진 중복 노트 탐색 및 삭제)

6. **빈 필드 AI 자동 채우기**
   - `core/completer.py` (Anki 내의 정보가 부족한 노트를 스캔하여 AI가 내용 보충)

7. **유의어 AI 분석 및 동기화**
   - `utils/cluster.py` (단어 간 의미론적 유사도 분석 및 클러스터 생성) → `utils/synonym_sync.py` (Anki 필드에 결과 반영)

8. **카드 디자인 -> Anki (Sync)**
   - `utils/schema_updater.py` (`user_config.json`의 CSS/HTML을 Anki 모델에 덮어쓰기)

9. **Anki -> 설정 파일 (Export)**
   - `utils/schema_exporter.py` (현재 Anki에 적용된 디자인을 `user_config.json`으로 백업)

---

## 🔄 시스템 워크플로우 (Flowline)

Anki Manager의 데이터 처리 흐름은 다음과 같습니다:

1.  **콘텐츠 추출 (Collect)**
    *   사용자가 선택한 소스(YouTube, Notion 등)로부터 원문 텍스트나 데이터를 긁어옵니다.
2.  **AI 선별 (Select)**
    *   Gemini AI가 방대한 텍스트 중에서 실제 학습 가치가 높은 '핵심 문장'과 '필수 어휘'를 자동으로 골라냅니다.
3.  **데이터 검수 (Inspect)**
    *   CLI 상에서 사용자가 AI가 고른 항목들을 직접 확인하고, 불필요한 항목은 제외하거나 수정할 수 있는 기회를 가집니다.
4.  **노트 보강 (Enrich)**
    *   선별된 항목에 대해 AI가 카드에 들어갈 모든 필드(설명, 예문, 품사 등)를 JSON 형식으로 완성합니다.
5.  **Anki 주입 (Inject)**
    *   AnkiConnect를 통해 완성된 정보를 Anki 앱의 지정된 덱에 노트로 추가합니다.
6.  **후처리 (Post-Process)**
    *   **오디오 생성:** 노트를 위한 TTS 음성을 생성합니다.
    *   **덱 정리:** 설정된 규칙에 따라 카드를 적절한 하위 덱으로 이동시킵니다.
    *   **클러스터링:** 새로 추가된 단어와 기존 단어 간의 유의어 관계를 분석하여 정리합니다.

---

## 🚀 시작하기

### 실행 방법
```bash
# 가상환경 활성화 후
python3 main.py
```

### 필수 조건
*   Anki 앱 실행 중
*   [AnkiConnect](https://ankiweb.net/shared/info/2055492159) 플러그인 설치 및 활성화
*   `.env` 파일에 Google Gemini API Key 설정
