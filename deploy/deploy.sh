#!/usr/bin/env bash
# Anki Manager를 서버(oracle-quant)에 배포한다. Mac의 저장소 루트에서 실행:
#   deploy/deploy.sh            테스트 → 빌드 → 전송 → 재시작 → 상태 확인
#   deploy/deploy.sh --dry-run  보낼 파일만 보여 주고 아무것도 바꾸지 않음
#
# - 커밋된 상태만 배포한다 (추적 파일에 커밋 안 된 변경이 있으면 멈춤).
# - git 추적 파일 + frontend/dist만 보낸다. data/, .env*, telegram_chat.env는 보내지 않고,
#   서버에서 파일을 지우지 않는다 (data/는 서버가 원본).
# - requirements.txt, deploy/*.service|*.timer가 바뀌었을 때만 설치한다.
set -euo pipefail

HOST=oracle-quant
REMOTE=/home/ubuntu/anki-manager
SERVICES=(anki-manager anki-telegram)
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

cd "$(git rev-parse --show-toplevel)"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "❌ 커밋 안 된 변경이 있습니다. 커밋한 뒤 배포하세요:"; git status --short --untracked-files=no; exit 1
fi
COMMIT=$(git rev-parse --short HEAD)
echo "== 배포 대상 커밋 $COMMIT ($(git log -1 --format=%s))"

echo "== 테스트"
.venv/bin/python -m pytest -q 2>&1 | tail -1
(cd frontend && npx vitest run 2>&1 | grep -E "Tests " )
echo "== 웹 화면 빌드"
(cd frontend && npm run build >/dev/null)

LIST=$(mktemp)
trap 'rm -f "$LIST"' EXIT
git ls-files | grep -v -E '^data/|(^|/)\.env|telegram_chat\.env' > "$LIST"
find frontend/dist -type f >> "$LIST"

if [[ $DRY == 1 ]]; then
  echo "== (dry-run) 바뀔 파일:"
  rsync -azin --files-from="$LIST" ./ "$HOST:$REMOTE/" | grep -v '^\.' || echo "(없음)"
  exit 0
fi

REQ_BEFORE=$(ssh "$HOST" "md5sum $REMOTE/requirements.txt 2>/dev/null | cut -d' ' -f1" </dev/null)
UNITS_BEFORE=$(ssh "$HOST" "cd $REMOTE/deploy 2>/dev/null && md5sum *.service *.timer 2>/dev/null" </dev/null || true)

echo "== 전송"
rsync -az --files-from="$LIST" ./ "$HOST:$REMOTE/"

if [[ "$REQ_BEFORE" != "$(md5sum < requirements.txt | cut -d' ' -f1)" ]]; then
  echo "== requirements.txt 바뀜 → 설치"
  ssh "$HOST" "cd $REMOTE && .venv/bin/pip install -q -r requirements.txt" </dev/null
fi

UNITS_AFTER=$(ssh "$HOST" "cd $REMOTE/deploy && md5sum *.service *.timer" </dev/null)
if [[ "$UNITS_BEFORE" != "$UNITS_AFTER" ]]; then
  echo "== 서비스 파일 바뀜 → 설치"
  ssh "$HOST" "cd $REMOTE/deploy && sudo install -m644 *.service *.timer /etc/systemd/system/ && sudo systemctl daemon-reload" </dev/null
fi

echo "== 재시작: ${SERVICES[*]}"
ssh "$HOST" "sudo systemctl restart ${SERVICES[*]} && echo $COMMIT > $REMOTE/DEPLOYED_COMMIT" </dev/null

echo "== 상태 확인"
ok=0
for i in $(seq 20); do
  if ssh "$HOST" "curl -sf -m5 127.0.0.1:8001/api/cards/status >/dev/null" </dev/null; then ok=1; break; fi
  sleep 2
done
ssh "$HOST" "systemctl is-active ${SERVICES[*]} anki anki-sync.timer | paste -sd' '" </dev/null
if [[ $ok == 1 ]]; then echo "✅ 배포 완료: $COMMIT"; else echo "❌ 백엔드가 응답하지 않습니다: journalctl -u anki-manager"; exit 1; fi
