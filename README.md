# Anki Manager

## 프로젝트 소개

Anki Manager는 Anki 카드 생성을 자동화하고 관리하는 도구입니다.

## 주요 기능

- **콘텐츠 추출**: YouTube 자막 및 웹사이트 텍스트를 자동으로 추출하여 학습 자료로 변환합니다.
- **AI 기반 선별**: Google Gemini AI 모델을 사용하여 추출된 텍스트에서 학습 가치가 높은 문장과 핵심 어휘를 지능적으로 선별합니다.
- **노트 자동 생성**: 선별된 문장과 어휘를 기반으로 Anki 노트(문장, 단어)를 자동으로 생성하고, 상세한 해설과 예문을 추가합니다.
- **음성 파일 자동 추가**: Google Cloud Text-to-Speech 및 gTTS를 활용하여 Anki 노트에 원어민 발음 음성 파일을 자동으로 추가합니다.
- **카드 정리**: Anki 카드 덱을 설정된 규칙에 따라 자동으로 분류하고 정리합니다.
- **설정 중앙화**: 모든 설정이 `config.py` 파일에 통합되어 있어, 손쉽게 프로젝트를 커스터마이징하고 관리할 수 있습니다.

## 프로젝트 구조

- [`Anki/`](Anki): Anki 카드와 관련된 리소스(예: 미디어 파일)가 저장되는 디렉토리입니다.
- [`config.py`](config.py): 프로젝트의 모든 설정(API 키, Anki 덱 이름, 노트 모델, 파일 경로 등)을 정의하는 중앙 구성 파일입니다.
- [`requirements.txt`](requirements.txt): 프로젝트 실행에 필요한 모든 Python 라이브러리 및 종속성이 나열된 파일입니다.

## 시작하기

### 1. 환경 설정

#### Python 환경

Python 3.8 이상이 설치되어 있는지 확인하십시오. 필요한 라이브러리는 `requirements.txt`에 명시되어 있습니다.

```bash
pip install -r requirements.txt
```

#### AnkiConnect

Anki 데스크톱 애플리케이션에 AnkiConnect 애드온이 설치되어 있어야 합니다. Anki를 실행하고 AnkiConnect가 활성화되어 있는지 확인하십시오.

#### Google Gemini API 키

Google AI Studio에서 Gemini API 키를 발급받아 프로젝트 루트 디렉토리의 `.env` 파일에 `GOOGLE_API_KEY="YOUR_API_KEY"` 형식으로 저장해야 합니다.

#### Google Cloud Text-to-Speech (선택 사항)

음성 생성을 위해 Google Cloud Text-to-Speech API를 사용하려면, Google Cloud 프로젝트를 설정하고 해당 API를 활성화해야 합니다. 또한, `gcloud auth application-default login` 명령어를 통해 인증을 완료해야 합니다.

### 2. `config.py` 설정

`Anki Manager/config.py` 파일에서 모든 핵심 설정을 관리할 수 있습니다. 다음 항목들을 필요에 따라 수정하십시오.

- **AI 모델**: 사용할 Gemini 모델(`SENTENCE_SELECTOR_MODEL`, `VOCAB_SELECTOR_MODEL`, `NOTE_COMPLETOR_MODEL`, `SITUATION_GENERATOR_MODEL`)을 지정합니다.
- **AnkiConnect URL**: AnkiConnect 서버 주소를 설정합니다.
- **파일 경로**: 임시 파일 및 결과 파일의 저장 경로를 지정합니다.
- **Anki 덱 및 노트 모델**: Anki에서 사용할 덱 이름과 노트 모델 이름을 정의합니다.
- **음성 설정**: TTS(Text-to-Speech) 언어 및 목소리 목록을 커스터마이징합니다.
- **카드 정리 규칙**: 카드를 특정 덱으로 자동 이동하는 규칙을 정의합니다.

## 사용법

### 워크플로우 실행

통합 워크플로우는 `workflow_manager.py`를 통해 실행할 수 있습니다. 추출할 YouTube 또는 웹사이트 URL을 인자로 전달합니다.

```bash
python Anki Manager/workflow_manager.py "[YOUR_YOUTUBE_OR_WEBSITE_URL]"
```

또는 스크립트 실행 시 URL을 입력할 수도 있습니다.

```bash
python Anki Manager/workflow_manager.py
```

### 개별 스크립트 실행

각 기능은 개별 스크립트로도 실행할 수 있습니다. 예를 들어:

- `youtube_extractor.py`: YouTube 자막 및 웹사이트 콘텐츠 추출
- `sentence_selector.py`: 문장 선별
- `vocabulary_selector.py`: 어휘 선별
- `note_completor.py`: 노트 자동 생성 및 AI 보강
- `audio_adder.py`: 음성 파일 추가
- `organizor.py`: Anki 카드 정리

자세한 내용은 각 스크립트 파일을 참조하십시오.

## Anki 노트 구조

이 프로젝트는 특정 Anki 노트 모델을 가정하고 있습니다. `config.py`에서 정의된 `MODEL_SENTENCE`, `MODEL_VOCAB`에 맞는 필드가 Anki에 존재해야 합니다. 예를 들어:

- **English Sentence** 노트 모델: `문장`, `해설`, `소리` 필드
- **English Vocabulary** 노트 모델: `단어`, `뜻`, `품사`, `유의어`, `예문`, `설명`, `소리` 필드
