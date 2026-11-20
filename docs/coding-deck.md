# Coding 덱 (2. Coding::2.1. Quant)

## 결정 (2026-11-19, 사용자 선택)
- 타겟: 내 프로젝트 코드 70% + 코딩테스트 기초 30%. 이번 1차는 퀀트 레포(quant-validator, portfolio, bitcoin-kimchi-predictor)에서 36장.
- 배분: Layer A(Pandas/NumPy 구현) 18, Layer B(설계·버그 방어) 11, Layer C(수식↔코드) 7.
- 포맷: 전부 주관식 단일 카드. 앞면은 정답 구간을 `_____`로 가림, 뒷면은 파란 밑줄 + `① 원리 / ② 누락·오류 시 버그`.
- 디자인: English Vocabulary 직계(14px 라운드 카드, 알약 배지, #f1f3f5 박스, #0071e3 포인트) + Python 구문 색.
- 신규 한도: 프리셋 `Coding` 7장/일 (English 프리셋은 변경 없음).

## 구현
- 노트 타입 `Coding Cloze`: 필드 제목, 정답, 코드, 분류, 출처, 설명. 템플릿 JS가 `코드` 안의 `정답`을 찾아 마스킹/강조한다 (코드·정답은 HTML 이스케이프로 저장).
- 시드: `scripts/seeds/coding_seed_quant_36.json`, 등록: `python -m scripts.add_coding_seed` (`--dry-run` 지원, 추가만 하고 기존 노트는 건드리지 않음).
- 시드 불변식: 모든 카드에서 `정답`이 `코드`에 정확히 1회 등장.

## 한계
- 36장의 코드·줄 번호는 2026-11-18 기준 레포 상태. 레포가 바뀌면 출처 줄 번호가 어긋날 수 있다.
- 실제 Anki 클라이언트(Mac/모바일) 렌더링은 미확인. 템플릿 JS는 Node 모의 DOM으로만 검증.
- 카드 내용의 정확성(why/bug 서술)은 원본 코드와 대조했으나 일부 서술(예: 부트스트랩·순열 검정의 통계적 설명)은 사용자 검수 필요.
