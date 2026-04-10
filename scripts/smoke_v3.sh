#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://enpro-fm-portal.onrender.com}"
SID="smoke-$(date +%s)"

echo "==> Smoke testing: ${BASE_URL}"

echo "==> GET /health"
curl -fsS "${BASE_URL}/health" >/tmp/fm_health.json
grep -q '"status"' /tmp/fm_health.json

echo "==> POST /api/chat"
curl -fsS -X POST "${BASE_URL}/api/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"lookup CLR510\",\"session_id\":\"${SID}\"}" >/tmp/fm_chat.json
grep -Eq '"response"|"products"|"mode"|\"type\"' /tmp/fm_chat.json

echo "==> POST /api/v3/chat"
curl -fsS -X POST "${BASE_URL}/api/v3/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"lookup CLR510\",\"session_id\":\"${SID}\"}" >/tmp/fm_v3_chat.json
grep -q '"response_type"' /tmp/fm_v3_chat.json
grep -q '"to_user"' /tmp/fm_v3_chat.json

echo "==> PASS: v3 smoke checks completed."
