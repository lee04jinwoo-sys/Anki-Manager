# English Speaking Coach (`speaking/`) 설계 및 운영 문서

## 1. 배경 및 진단 (2026-11-18 로컬 Anki DB 실측)

- **기존 영어 Anki 현황 (최근 30일)**: 30/30일 출석, 일 평균 354회 / 60.4분 (성숙 어휘 15,492장, 성숙 문장 9,254장, 성숙 문법 1,306장). `daily-english-diary` 에세이는 IELTS Task 2 Band 6.5~7.0 (5편 후 약 1개월 중단).
- **스피킹 병목**:
  1. 주당 실제 영어 대화 < 1~3시간 → 한국어 모드에서 영어 모드로 전환되는 초반 워밍업 지연(Cold-Start).
  2. 12초 단문 번역(`Sentence`)과 다른 60~120초 연속 발화·구조화·즉흥 꼬리질문 훈련 부재.
  3. 로컬 웹앱 실행 마찰(귀차니즘)과 시작·종료 기준 부재.
- **설계 원칙**: Anki 카드 내부에 1~2분 녹음을 억지로 넣지 않고, 기존 `@ankimanager_bot` + `Anki Manager` 백엔드로 **Anki식 유한 완료 메커니즘**을 구현한다.

---

## 2. v1 아키텍처

```text
Telegram (@ankimanager_bot)
  ├─ 텍스트 메시지 / /undo  ──▶ 기존 /api/cards/* (변경 없음, 예외 격리)
  ├─ /speak [daily|interview|ielts]  ──▶ POST /api/speaking/start
  ├─ 음성 메시지 (voice/audio)       ──▶ POST /api/speaking/voice
  │     ├─ 활성 세션 있음: 3단계 상태 머신 (warmup_1 -> warmup_2 -> main_pass1 -> main_pass2 -> followup)
  │     └─ 활성 세션 없음: 외부 대화 표현 회수(Debrief)
  └─ 인라인 버튼 (spk_add:<id>)      ──▶ POST /api/speaking/candidates/{id}/add
                                          └─▶ card_service (tags=["speaking"]) + AnkiWeb 동기화

Anki Manager Backend (127.0.0.1:8001)
  ├─ speaking/store.py   (data/speaking.db — 기존 anki-backup.timer 자동 백업)
  ├─ speaking/speech.py  (Groq whisper-large-v3-turbo 단어 타임스탬프 + Chirp 3 HD OGG_OPUS)
  ├─ speaking/coach.py   (core/llm_router.py 무료 라우터 JSON 평가)
  └─ speaking/tracker.py (1. Language::1.1. English::Speaking 고정 카드 1장: Due 1 <-> 0)
```

---

## 3. 일일 15~20분 3단계 프로토콜

1. **Step 1 — 워밍업 (약 2분)**: 준비 시간 없이 쉬운 일상 질문 2개 × 30~45초 녹음 (초반 영어 모드 시동).
2. **Step 2 — 메인 2-Pass 압축 (약 10분)**:
   - 3개 트랙 순환 (`daily` 토론토 일상/수업 · `interview` 테크 STAR/프로젝트 · `ielts` IELTS/TOEFL Part 2). `speaking.db` 내부 SRS가 점수 ≤ 6.5 주제를 3일 뒤 자동 재출제.
   - Anki `English Vocabulary` 최근 30일/취약(`lapses>=4`) 표현 2~3개를 선택적 보너스 미션으로 제시.
   - **1차(90초)** → `Groq Whisper` 실측 지표(길이·WPM·필러·1.5초+ 침묵) + LLM 교정 + `Chirp 3 HD` 원어민 대안 음성 회신.
   - **2차(60초 압축 재발화)** → 1차 대비 WPM·필러·침묵 변화량 비교.
3. **Step 3 — 즉흥 꼬리질문 (약 3분)** → 완료 시:
   - 스트릭 +1 기록
   - Anki `1. Language::1.1. English::Speaking` 고정 트래커 카드 1장에 `setDueDate("1")` + 백그라운드 동기화 (`1 → 0`)
   - 세션 중 추출된 교정 후보 2~4개를 인라인 버튼으로 제시 → 클릭한 항목만 `speaking` 태그로 Anki 등록.

### 외부 대화 표현 회수 (Debrief)
- `/speak` 세션이 없는 상태에서 음성 메시지를 보내면(한국어/영어 혼용 가능), 막혔던 상황을 분석해 자연스러운 영어 표현 후보 + 원어민 음성 + Anki 등록 버튼을 반환한다. (일일 스피킹 완료 카운트에는 포함하지 않음.)

---

## 4. Anki 1장 트래커 및 실시간 로그 규칙 (`speaking::tracker`)

- 덱: `1. Language::1.1. English::Speaking`, 모델: `Basic`, 태그: `speaking::tracker`.
- 매일 04:05(`America/Toronto`, `deploy/anki-speaking-reset.timer`) 서버가 `unsuspend` + `setDueDate("0")` + 동기화를 실행하여 Anki 화면에 `1`을 띄운다.
- 세션 완료 시 `updateNoteFields`로 고정 트래커 카드 1장의 **앞면**(연속 스트릭, 최근 14일 평균 WPM·필러·긴 침묵, 직전 세션 요약 및 핵심 원어민 문장)과 **뒷면**(최근 14회 세션 로그 Markdown 표)을 자동 갱신한 뒤 `setDueDate("1")`로 `1 → 0` 차감한다 (`updateNoteFields` 실패 시에도 차감은 예외 격리되어 정상 수행).
- `answerCards` 대신 `setDueDate("1")`를 쓰므로 기존 FSRS 스케줄·정답률·리뷰 시간 통계를 오염시키지 않는다 (`utils/stats.py` 및 `backend/services/stats_service.py`는 `ease == 0` 수동 변경을 제외하고 `Vocabulary/Sentence/Grammar`만 집계).
- `integrations/nightly_maintenance.py`는 `Basic` 노트를 대상으로 하지 않으므로 트래커 카드를 건드리지 않는다.

---

## 5. 실측 레이턴시 및 시행착오 로그 (2026-11-19)

- **성능 예산(Budget)**: 턴당 음성 업로드~피드백 응답 **15,000 ms 이내**
- **실측치** (macOS `say` 3초 영어 샘플 WAV → `Groq whisper-large-v3-turbo` → `core/llm_router.py`):
  - Groq Whisper STT: **376 ms**
  - 무료 LLM 라우터 코칭 JSON: **12,444 ms**
  - 합계: **12,820 ms** (예산 15,000 ms 대비 -2,180 ms 여유)
- **실측 중 발견한 오류 및 수정**:
  - 초기 `analyze_transcript_metrics`는 단어 간 틈(`curr.start - prev.end >= 1.5s`)만 침묵으로 계산했다.
  - 실제 1.8초 침묵(`[[slnc 1800]]`)을 넣은 Groq Whisper 실측 결과, Whisper가 앞선 침묵을 다음 단어의 `start~end` 구간에 흡수(`'I': 0.94 -> 3.10s`, 단어 간 틈 `0.0s`)하여 `long_pause_count=0`으로 누락됨을 발견했다.
  - 수정: 직전 단어 이후 단일 단어 스팬에서 정상 발화 상한(`0.6s`)을 뺀 흡수 침묵(`(end - start) - 0.6s`)을 명시적 틈과 함께 평가하도록 TDD로 수정(`tests/unit/test_speaking_speech.py`).

---

## 6. 배포 및 최초 활성화 절차 (`oracle-main`)

1. 로컬에서 테스트 통과 및 커밋 확인 후 배포:
   ```bash
   ./deploy/deploy.sh --dry-run
   ./deploy/deploy.sh
   ```
2. 서버에서 일일 리셋 타이머 활성화 및 최초 트래커 카드 1장 생성 확인:
   ```bash
   ssh oracle-main "sudo systemctl enable --now anki-speaking-reset.timer"
   ssh oracle-main "cd ~/anki-manager && .venv/bin/python -m speaking.daily_reset"
   ```
3. 텔레그램 `@ankimanager_bot`에서 `/speak` → 음성 테스트 → 완료 후 Anki Sync로 `Speaking: 1 → 0` 반영 확인.
