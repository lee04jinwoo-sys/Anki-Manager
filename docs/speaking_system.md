# English Speaking Coach (질문 은행 + 전용 텔레그램 봇)

하루 1개는 필수, 더 하고 싶으면 계속 이어서 말한다. 질문은 서버 DB에서 순서대로 나오고, 교정된 문장과 표현은 Anki 문장/단어 덱으로 자동 추가된다.

## 1. 구조 요약
- **질문**: `speaking/question_bank.py`의 72개(일상 카테고리 54개 먼저, 기술·발표 18개 뒤). 질문 하나씩만 보여 준다.
- **진행 상태**: `data/speaking.db`의 `question_progress`(open/done). 한 바퀴를 다 돌면 처음부터 다시 시작한다. 큐 구현은 `speaking/db_deck.py`.
- **Anki Speaking 덱은 쓰지 않는다.** 예전 FSRS 방식(72장 시딩, Again/Hard/Good/Easy)은 폐기했다. 스피킹에는 간격반복이 맞지 않고, 외울 가치가 있는 것은 질문이 아니라 내가 틀린 문장과 표현이기 때문이다.
- **30초 규칙**: 질문 답변은 30초 이상이어야 한다(`MIN_ANSWER_SEC`). 더 짧으면 채점·저장·카드 추가 없이 "다시 녹음" 안내만 보내고 질문은 그대로 둔다. `다음 질문`·`/next`도 30초 이상 답한 기록이 있어야 넘어간다(건너뛰려면 `/skip`). `/debrief`에는 적용하지 않는다.
- **하루 완료**: 그날 평가(다음 질문으로 넘어감)된 답변이 1개 이상이면 스트릭에 반영된다.
- **전용 봇**: `integrations/speaking_bot.py` (`SPEAKING_BOT_TOKEN`). `@ankimanager_bot`(`telegram_intake.py`)은 카드 입력 전용.

## 2. 흐름

```text
Telegram (스피킹 봇)
  ├─ 09:00 푸시 (anki-speaking-morning.timer) ──▶ POST /api/speaking/queue/start
  ├─ /today /next /skip /last /summary /stats /debrief
  ├─ 음성 메시지 ──▶ POST /api/speaking/voice
  │     ├─ ~/speaking_audio/YYYY-MM-DD/card_<id>_<HHMMSS>.oga 저장 (백업 없음, 90일 정리 예정)
  │     ├─ Groq whisper-large-v3-turbo 전사 (.oga는 .ogg로 바꿔 전송) + WPM·필러·침묵 측정
  │     ├─ core/llm_router.py 채점: 점수, 요약, 문장별 교정, 교정된 전체 답변, 카드 후보
  │     ├─ 후보 자동 추가: 문장 ≤5 · 표현 ≤5 (하루 상한 문장 10 · 표현 10), 태그 speaking, speaking::auto
  │     └─ GCP Chirp 3 HD 모범 음성 회신 + [재녹음] [다음 질문 ▶]
  ├─ spk_retry                ──▶ POST /api/speaking/retry (1차 vs 재녹음 비교)
  ├─ spk_rate:<id>:3          ──▶ POST /api/speaking/rate (다음 질문으로 넘어감, 중복 탭 무시)
  └─ /next                    ──▶ POST /api/speaking/next (답했으면 완료 처리, 아니면 건너뛰고 다음 질문)
```

## 3. 명령어
| 명령 | 동작 |
| --- | --- |
| `/today` | 오늘 질문 받기·이어하기 |
| `/next` (`/more`) | 다음 질문. 30초 이상 답한 뒤에만 넘어감 |
| `/skip` | 이 질문을 건너뛰고 다른 질문 |
| `/last` | 최근 답변의 문장별 교정 |
| `/summary` | 오늘 요약, 아직 추가 안 한 후보 |
| `/stats` | 스트릭, 오늘 답한 질문 수, 최근 14일 WPM·필러·긴 침묵 |
| `/debrief` | 외부 대화에서 막힌 표현 회수. 질문이 없을 때 음성을 보내도 자동 |

명령어 메뉴는 봇이 시작할 때 `setMyCommands`로 등록한다.

## 4. 운영
- 서비스: `anki-speaking-bot.service`(상시), `anki-speaking-morning.timer`(09:00 America/Toronto). `.env.speaking_bot`에 `SPEAKING_BOT_TOKEN`.
- 배포는 `deploy/deploy.sh`. 이미 켜져 있으면 봇을 재시작한다.
- 자동 추가 카드 정리: Anki에서 `tag:speaking::auto` 검색.
- 학습 설계 메모: 연습량이 핵심이므로 한 세션에 여러 질문을 이어서 하는 것이 목표(워밍업 효과). 첫 질문과 마지막 질문 지표 비교는 아직 없음.

## 5. 알려진 한계
- 질문이 한 바퀴(72개) 돌면 같은 질문이 반복된다. 신규 질문 생성은 아직 없음.
- Whisper는 발음 실수를 매끄러운 철자로 받아 적을 수 있어 전사문에 실수가 가려질 수 있다.
- 오디오 90일 자동 정리, 한 달 뒤 재도전 비교는 미구현.
- 예전 Anki `Speaking` 덱과 72개 노트는 더 이상 쓰이지 않는다. 삭제는 사용자 확인 후.
