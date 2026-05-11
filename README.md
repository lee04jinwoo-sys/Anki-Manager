# 🚀 Anki Manager CLI (안키 매니저)

[English](#english) | [한국어](#한국어)

---

## 한국어

안키(Anki) 워크플로우를 자동화하는 강력한 모듈형 CLI 도구입니다. 콘텐츠를 수집하고, AI로 노트를 풍성하게 만들며, 카드 디자인을 관리하고 학습 진행 상황을 추적합니다.

### ✨ 주요 기능

#### 1. 노트 추가 (스마트 자동화)
*   **YouTube**: 자막을 가져와 핵심 문장과 단어를 자동으로 선택합니다.
*   **Situation**: 간단한 상황 설명만으로 상황별 학습 자료를 생성합니다.
*   **Obsidian**: 옵시디언의 "Inbox" 노트를 안키로 직접 동기화합니다.
*   **AI 보강**: 정의, 예문, 번역을 자동으로 채워줍니다.

#### 2. 노트 정리 (유지 관리)
*   **오디오 채우기**: 카드에 고품질 TTS 오디오를 자동으로 추가합니다.
*   **필드 완성**: 모든 노트 모델에서 누락된 필드를 자동 완성합니다.
*   **자동 정리**: 스마트 카드 이동 및 덱 구성 기능을 제공합니다.
*   **중복 제거**: 불필요한 중복 카드를 삭제하여 컬렉션을 가볍게 유지합니다.

#### 3. 디자인 관리
*   **가져오기/내보내기**: 안키 카드 템플릿과 CSS를 JSON 파일로 관리합니다.
*   **버전 관리**: 카드 디자인을 안전하게 보관하고 다른 프로필과 쉽게 공유합니다.

#### 4. 통계 및 분석
*   **성과 추적**: 덱 유지율과 새 카드 진행률을 한눈에 확인합니다.
*   **시각적 보고서**: 터미널에서 깔끔한 표 형태로 통계를 제공합니다.

### ⌨️ 고급 인터랙티브 선택기
최신 색상 코드가 적용된 인터랙티브 선택기를 제공합니다:
*   **시각적 피드백**: 선택 상태를 [초록]ON[/] / [빨강]OFF[/] 배경으로 표시합니다.
*   **일괄 작업**: `A` (모두 선택), `N` (선택 해제).
*   **언어 지원**: 영어 단축키뿐만 아니라 한국어(`ㅁ`, `ㅜ`, `ㅊ`, `ㅂ`) 단축키도 지원합니다.

### 🚀 시작하기

#### 필수 조건
*   Python 3.10+
*   [Anki](https://apps.ankiweb.net/) 및 [AnkiConnect](https://ankiweb.net/shared/info/2055405234) 플러그인 설치.

#### 설치 및 실행
1.  저장소 클론 및 이동:
    ```bash
    git clone https://github.com/lee04jinwoo-sys/Anki-Manager.git
    cd "Anki Manager"
    ```
2.  가상 환경 설정 및 패키지 설치:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
3.  `.env` 파일에 필요한 API 키를 설정합니다.
4.  메인 메뉴 실행:
    ```bash
    python main.py
    ```

---

## English

A powerful, modular CLI tool to automate your Anki workflow. Seamlessly fetch content, enrich notes with AI, manage card designs, and track your learning progress.

### ✨ Key Features

#### 1. Add Notes (Smart Automation)
*   **YouTube**: Fetch transcripts and automatically select key sentences and vocabulary.
*   **Situation**: Generate contextual learning material based on a simple description.
*   **Obsidian**: Sync your "Inbox" notes directly into Anki.
*   **AI Enrichment**: Automatically fills definitions, examples, and translations.

#### 2. Organize Notes (Maintenance)
*   **Audio Filler**: Automatically add high-quality TTS audio to your cards.
*   **Field Completion**: Auto-fill missing fields across all note models.
*   **Auto-Organizer**: Smart card migration and deck organization.
*   **Duplicate Cleaner**: Keep your collection lean by removing redundant cards.

#### 3. Design Management
*   **Import/Export**: Manage your Anki card templates and CSS as JSON files.
*   **Version Control**: Keep your card designs safe and easily synchronizable across profiles.

#### 4. Statistics & Analytics
*   **Performance Tracking**: Quick overview of deck retention and new card progress.
*   **Visual Reports**: Clean, table-based statistics directly in your terminal.

### ⌨️ Advanced Interactive Selector
The CLI features a modern, color-coded interactive selector:
*   **Visual Feedback**: [green]ON[/] / [red]OFF[/] backgrounds for selection.
*   **Bulk Actions**: `A` (Select All), `N` (Deselect None).
*   **Language Support**: Shortcuts work in both English and Korean (`ㅁ`, `ㅜ`, `ㅊ`, `ㅂ`).

### 🚀 Getting Started

#### Prerequisites
*   Python 3.10+
*   [Anki](https://apps.ankiweb.net/) with [AnkiConnect](https://ankiweb.net/shared/info/2055405234) installed.

#### Installation & Usage
1. Clone the repository:
   ```bash
   git clone https://github.com/lee04jinwoo-sys/Anki-Manager.git
   cd "Anki Manager"
   ```
2. Set up virtual environment & Install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Configure your `.env` file with necessary API keys.
4. Run the interactive menu:
   ```bash
   python main.py
   ```
