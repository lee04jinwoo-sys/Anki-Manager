# English Speaking Coach v2 (Anki FSRS 질문 카드 + 전용 텔레그램 봇)

## 1. v1 -> v2 전환 이유
- **1카드 = 1질문 Anki 네이티브 스케줄링**: v1의 고정 1장 트래커(`1 -> 0`)와 자체 `topic_srs`를 폐기하고, Anki `1. Language::1.1. English::Speaking` 덱에 **72개 Daily 질문 카드**를 등록해 실제 Anki FSRS 스케줄(`answerCards`)로 복습한다.
- **전용 텔레그램 봇 분리**: `@ankimanager_bot`(`integrations/telegram_intake.py`)은 기존 단어/문장 카드 입력 전용으로 복원하고, 스피킹 문답은 전용 봇(`integrations/speaking_bot.py`)에서 독립 운영한다.
- **영구 녹음 보관**: 모든 사용자 음성 녹음(`.ogg`)을 `data/` 백업 대상 바깥(`~/speaking_audio/YYYY-MM-DD/card_<card_id>_<HHMMSS>.ogg`, `SPEAKING_AUDIO_DIR`)에 저장한다.

---

## 2. 아키텍처

```text
Telegram (전용 스피킹 봇: integrations/speaking_bot.py)
  ├─ 09:00 푸시 (anki-speaking-morning.timer) ──▶ POST /api/speaking/queue/start
  ├─ 음성 메시지 (voice/audio)               ──▶ POST /api/speaking/voice
  │     ├─ ~/speaking_audio/YYYY-MM-DD/...ogg 저장
  │     ├─ Groq whisper-large-v3-turbo 단어 타임스탬프 + 흡수 침묵(0.6s+) 측정
  │     ├─ core/llm_router.py 채점 (점수 + 추천 등급 + 교정 + 원어민 대안)
  │     └─ GCP Chirp 3 HD OGG_OPUS 모범 음성 회신 + [재녹음] / [Again Hard Good Easy]
  ├─ spk_retry                               ──▶ POST /api/speaking/retry (1차 vs 재녹음 WPM 비교)
  ├─ spk_rate:<card_id>:<ease>               ──▶ POST /api/speaking/rate
  │     ├─ AnkiConnect answerCards (실제 FSRS 반영)
  │     ├─ 해당 카드 뒷면(뒷면 필드) 복습 요약 표 갱신
  │     ├─ 다음 카드 [k+1/N] 출제 또는 0장 완료 시 하루 요약 + 후보 버튼 전송
  └─ spk_add:<cand_id>                       ──▶ POST /api/speaking/candidates/{id}/add
                                                  └─▶ card_service (tags=["speaking"]) + AnkiWeb 동기화
```

---

## 3. Anki 덱 · 프리셋 · 질문 은행 규격

- **덱**: `1. Language::1.1. English::Speaking` (`Basic` 모델, 태그 `speaking::question`, `speaking::daily`, `speaking::id::<id>`)
- **전용 프리셋 (`English Speaking`)**:
  - 일일 한도: `new.perDay = 1`, `rev.perDay = 3` (하루 최대 15~20분 상한)
  - 목표 보존율: `desiredRetention = 0.85`
  - 당일 재노출 억제: `new.delays = []`, `lapse.delays = []` (Anki가 빈 배열을 거부할 경우 `[1440.0]` 자동 폴백) → `Good` 1회로 즉시 오늘 큐에서 졸업
- **질문 은행 ([speaking/question_bank.py](file:///Users/leejinwoo/Desktop/Projects/Anki%20Manager/speaking/question_bank.py))**: 8개 Daily 카테고리 × 9문항 = **72장** (`Campus & Classes`, `Toronto Life`, `Small Talk & Updates`, `Opinions & Tech`, `Social & Boundaries`, `Requests & Problem Solving`, `Stories & Reflections`, `Projects & Presentations`).
- **기존 통계 보호**: [backend/services/stats_service.py](file:///Users/leejinwoo/Desktop/Projects/Anki%20Manager/backend/services/stats_service.py)는 `Vocabulary`/`Sentence`/`Grammar`만 집계하므로 스피킹 덱이 기존 정답률/복습량 통계를 오염시키지 않는다.

---

## 4. BotFather 토큰 등록 및 활성화 (`oracle-main`)

1. Telegram `@BotFather`에서 `/newbot`으로 스피킹 전용 봇 토큰 발급
2. 서버에 토큰 저장 및 `anki-speaking-bot.service` + `anki-speaking-morning.timer` 시작:
   ```bash
   ssh -t oracle-main 'umask 077; read -rsp "SPEAKING_BOT_TOKEN: " T; echo; printf "SPEAKING_BOT_TOKEN=%s\n" "$T" > ~/anki-manager/.env.speaking_bot; sudo systemctl enable --now anki-speaking-bot anki-speaking-morning.timer; cd ~/anki-manager && set -a && source .env.speaking_bot && source telegram_chat.env && set +a && .venv/bin/python -m speaking.morning_push'
   ```
