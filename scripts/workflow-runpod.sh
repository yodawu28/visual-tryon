#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
if [[ $# -gt 0 ]]; then
  shift
fi

RUNPOD_BRANCH="${RUNPOD_BRANCH:-feature/kiosk-gpu-flow}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"
API_PROFILE="${API_PROFILE:-kiosk}"
KIOSK_UI_ENABLED="${KIOSK_UI_ENABLED:-true}"
KIOSK_UI_PATH="${KIOSK_UI_PATH:-/kiosk}"

export HOST
export PORT
export API_PROFILE
export KIOSK_UI_ENABLED
export KIOSK_UI_PATH

log() {
  printf '[runpod-workflow] %s\n' "$*"
}

switch_branch() {
  log "switch branch: ${RUNPOD_BRANCH}"
  git switch "$RUNPOD_BRANCH"
}

build_ui() {
  log "build kiosk UI"
  (
    cd ui/kiosk-app
    npm ci
    npm run build
  )
}

init_runtime() {
  log "initialize RunPod runtime paths"
  make runpod-init
}

run_api() {
  log "start kiosk API on ${HOST}:${PORT}"
  exec python -m scripts.run_kiosk_all "$@"
}

usage() {
  cat <<'EOF'
Usage: bash scripts/workflow-runpod.sh [mode]

Modes:
  build             git switch feature/kiosk-gpu-flow, then build kiosk UI
  run               switch branch, build UI, init paths, start API + worker
  run-with-ollama   switch branch, build UI, init paths, start API + worker + Ollama
  preflight         switch branch, then run scripts.kiosk_preflight
  check             switch branch, build UI, and run JSON readiness preflight

Environment:
  RUNPOD_BRANCH     Git branch to switch to. Default: feature/kiosk-gpu-flow
  HOST              API host. Default: 0.0.0.0
  PORT              API port. Default: 8080
  API_PROFILE       API profile. Default: kiosk
  KIOSK_UI_ENABLED  Serve kiosk UI from FastAPI. Default: true
  KIOSK_UI_PATH     Mounted kiosk UI path. Default: /kiosk
EOF
}

case "$MODE" in
  build)
    switch_branch
    build_ui
    ;;
  run)
    switch_branch
    build_ui
    init_runtime
    run_api "$@"
    ;;
  run-with-ollama)
    switch_branch
    build_ui
    init_runtime
    run_api --start-ollama "$@"
    ;;
  preflight)
    switch_branch
    python -m scripts.kiosk_preflight "$@"
    ;;
  check)
    switch_branch
    build_ui
    python -m scripts.kiosk_preflight --json "$@"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
