#!/usr/bin/env bash
# Régénère les images OG pendant le build Render via preview local (pas de capture prod live).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
PORT="${OG_PREVIEW_PORT:-10000}"
BASE_URL="http://127.0.0.1:${PORT}"

if [ "${OG_REGENERATE_ON_BUILD:-true}" = "false" ]; then
  echo "[og] OG_REGENERATE_ON_BUILD=false — skip"
  exit 0
fi

export OG_BUILD_LENIENT="${OG_BUILD_LENIENT:-true}"

echo "[og] Démarrage preview uvicorn sur ${BASE_URL} …"
cd "$BACKEND"
uvicorn app.main:app --host 127.0.0.1 --port "$PORT" &
UVICORN_PID=$!

cleanup() {
  kill "$UVICORN_PID" 2>/dev/null || true
  wait "$UVICORN_PID" 2>/dev/null || true
}
trap cleanup EXIT

READY=0
for _ in $(seq 1 45); do
  if curl -sf "${BASE_URL}/docs" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "[og] WARN: preview indisponible — fallback og-default.jpg"
  exit 0
fi

echo "[og] Preview prête — capture Playwright (mode lenient=${OG_BUILD_LENIENT}) …"
python "$ROOT/tools/regenerate_og.py" --base-url "$BASE_URL" --active-only || true
echo "[og] Régénération terminée (échecs partiels tolérés — fallback og-default.jpg)"
exit 0
