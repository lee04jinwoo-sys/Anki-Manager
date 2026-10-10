# Anki Manager

영어 학습용 Anki 덱(Vocabulary / Sentence / Grammar)을 관리하는 **로컬 웹 대시보드**입니다.
FastAPI 백엔드가 AnkiConnect와 Gemini를 호출하고, React 프론트엔드가 `http://localhost:8001`에서 동작합니다.
(이전 CLI 메뉴와 YouTube 수집 기능은 v2에서 제거되었습니다.)

## 기능

| 영역 | 내용 |
|---|---|
| 대시보드 | English 하위 덱별 신규/Due/학습 중/성숙 카드, 30일 정답률, Leech 현황, Obsidian Inbox 대기 수 |
| Obsidian 가져오기 | `Anki_Inbox.md`의 `## Sentences` / `## Vocab` 항목을 선택 → Gemini로 뜻·예문·번역 보강 → Anki 등록. **실제로 등록된 항목만** Inbox에서 지웁니다. |
| 노트 정리 | 빈 필드 채우기(AI), TTS 오디오, 규칙별 덱 이동, 품사 자동 입력(NLTK), 중복 정리. 백그라운드 작업으로 실행되며 단계 사이에서 취소할 수 있습니다. |
| 링크 매니저 | 단어 ↔ 문장 역색인(`data/links.db`), 연결이 적은 단어에 예문 일괄 생성, 카드 뒷면 어휘 강조 템플릿 주입 |
| 청크 승격 | Leech 단어를 고빈도 연어/청크로 교체하고 카드를 새 카드로 초기화 |
| 디자인 | 카드 템플릿·CSS를 `data/design_config.json`으로 백업/복원 |
| Agent Bridge | `agent_bridge.py` — 대화 중 만든 문장/단어/문법을 CLI로 바로 등록 (`CLAUDE.md` 참고) |

### 되돌리기 관련 동작

- **중복 정리**는 노트를 삭제하지 않습니다. 같은 값(HTML·대소문자 무시) 중 리뷰가 가장 많은 노트를 남기고, 나머지에 `dup::review` 태그를 달아 일시정지합니다. 확인 후 Anki에서 직접 지우세요.
- **청크 승격**은 변경 전 노트 필드와 카드 스케줄 상태를 `data/backups/promote/<note_id>_<시각>.json`에 저장하고, 저장에 실패하면 중단합니다.
- **템플릿 주입**은 적용 전 `data/template_backups/`에 원본을 저장합니다.
- 서버는 로컬 출처(`localhost`, `127.0.0.1`)가 아닌 웹페이지에서 온 쓰기 요청을 403으로 거부합니다.

## 설치

필수: Python 3.10+, Node 18+, [Anki](https://apps.ankiweb.net/) + [AnkiConnect](https://ankiweb.net/shared/info/2055405234)

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
```

`.env`에 `GOOGLE_API_KEY`(Gemini)를 넣습니다. Google Cloud TTS 인증이 없으면 gTTS로 대체됩니다.
Obsidian 볼트 경로와 Inbox 파일명은 `data/settings.json`의 `OBSIDIAN_VAULT_PATH`, `OBSIDIAN_INBOX_FILE`로 바꿀 수 있습니다.

## 실행

```bash
.venv/bin/python main.py
```

Anki를 켠 상태에서 `http://localhost:8001`을 엽니다. 프론트엔드 개발 시에는 `cd frontend && npm run dev`(포트 5173, `/api`는 8001로 프록시).

## 테스트

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

`tests/unit`은 AnkiConnect를 모킹하며, 모킹하지 않은 Anki 호출은 실패하도록 막혀 있습니다.
실제 Anki에 붙는 읽기 전용 점검은 `scripts/check_pos_logic.py`, `scripts/check_idiom_detection.py`입니다 (`.venv/bin/python -m scripts.check_pos_logic`).

## 구조

```
server.py, main.py        FastAPI 앱 / 실행 진입점
backend/routers           HTTP 엔드포인트 (/api/...)
backend/services          카드 등록, 노트 정리, Obsidian 가져오기, 코퍼스, 작업 관리(JobManager)
core/                     Gemini 보강(completer), 링크 역색인(link_manager), 예문 일괄 생성
integrations/             AnkiConnect, TTS, Obsidian
utils/                    덱 이동, 중복 정리, 품사, 디자인 백업, 통계
scripts/                  일회성 마이그레이션·점검 스크립트
frontend/                 React 19 + Vite + Tailwind
```
