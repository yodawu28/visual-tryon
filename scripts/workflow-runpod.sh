#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
if [[ $# -gt 0 ]]; then
  shift
fi

RUNPOD_BRANCH="${RUNPOD_BRANCH:-feature/kiosk-gpu-flow}"
RUNPOD_INSTALL_SYSTEM_DEPS="${RUNPOD_INSTALL_SYSTEM_DEPS:-1}"
RUNPOD_MODEL_DIR="${RUNPOD_MODEL_DIR:-/workspace/tryon-models}"
RUNPOD_INSTALL_STATE_DIR="${RUNPOD_INSTALL_STATE_DIR:-${RUNPOD_MODEL_DIR}/install-state}"
RUNPOD_FORCE_INSTALL="${RUNPOD_FORCE_INSTALL:-0}"
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

install_nodejs() {
  log "install Node.js 20 and npm"
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  mkdir -p /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --batch --yes --dearmor -o /etc/apt/keyrings/nodesource.gpg
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list
  apt-get update
  apt-get install -y nodejs
}

install_system_dependencies() {
  if command -v npm >/dev/null 2>&1; then
    log "npm already available: $(npm -v)"
    return
  fi

  if [[ "${RUNPOD_INSTALL_SYSTEM_DEPS}" != "1" ]]; then
    printf '%s\n' "npm is required but was not found. Set RUNPOD_INSTALL_SYSTEM_DEPS=1 or install Node.js 20." >&2
    exit 127
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    printf '%s\n' "npm is required but was not found, and apt-get is unavailable in this image." >&2
    exit 127
  fi

  install_nodejs
}

build_ui() {
  log "build kiosk UI"
  mkdir -p "${RUNPOD_INSTALL_STATE_DIR}"
  if [[ "${RUNPOD_FORCE_INSTALL}" != "1" ]] \
    && python -m scripts.install_state \
      --state-dir "${RUNPOD_INSTALL_STATE_DIR}" \
      --name kiosk-ui-npm \
      --path ui/kiosk-app/package.json \
      --path ui/kiosk-app/package-lock.json \
      --value "node=$(node -v)" \
      --value "npm=$(npm -v)" \
      --exists ui/kiosk-app/node_modules \
      check; then
    log "kiosk UI npm dependencies already installed; skipping npm ci"
  else
    (
      cd ui/kiosk-app
      npm ci
    )
    python -m scripts.install_state \
      --state-dir "${RUNPOD_INSTALL_STATE_DIR}" \
      --name kiosk-ui-npm \
      --path ui/kiosk-app/package.json \
      --path ui/kiosk-app/package-lock.json \
      --value "node=$(node -v)" \
      --value "npm=$(npm -v)" \
      --exists ui/kiosk-app/node_modules \
      write
  fi
  (
    cd ui/kiosk-app
    npm run build
  )
}

bootstrap_runtime() {
  log "bootstrap RunPod Python/runtime dependencies"
  make runpod-bootstrap
}

import_default_size_charts() {
  log "import default size charts"
  make runpod-import-default-size-charts
}

import_default_garments() {
  log "import default garments"
  make runpod-import-default-garments
}

run_api() {
  log "start kiosk API on ${HOST}:${PORT}"
  exec python -m scripts.run_kiosk_all "$@"
}

usage() {
  cat <<'EOF'
Usage: bash scripts/workflow-runpod.sh [mode]

Modes:
  build             switch branch, ensure Node/npm, then build kiosk UI
  bootstrap         switch branch, ensure Node/npm, then run make runpod-bootstrap
  import-default-size-charts
                    switch branch, then import default RunPod size charts
  import-default-garments
                    switch branch, then import default RunPod garment catalog
  run               switch branch, install deps, import size charts/garments, build UI, start API + worker
  run-with-ollama   switch branch, install deps, import size charts/garments, build UI, start API + worker + Ollama
  preflight         switch branch, then run scripts.kiosk_preflight
  check             switch branch, install deps, import size charts/garments, build UI, and run JSON readiness preflight

Environment:
  RUNPOD_BRANCH     Git branch to switch to. Default: feature/kiosk-gpu-flow
  RUNPOD_INSTALL_SYSTEM_DEPS  Install Node.js 20 via apt-get when npm is missing. Default: 1
  RUNPOD_INSTALL_STATE_DIR    Install-state cache directory. Default: /workspace/tryon-models/install-state
  RUNPOD_FORCE_INSTALL        Reinstall dependencies even when install-state matches. Default: 0
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
    install_system_dependencies
    build_ui
    ;;
  bootstrap)
    switch_branch
    install_system_dependencies
    bootstrap_runtime
    ;;
  import-default-size-charts)
    switch_branch
    import_default_size_charts
    ;;
  import-default-garments)
    switch_branch
    import_default_garments
    ;;
  run)
    switch_branch
    install_system_dependencies
    bootstrap_runtime
    import_default_size_charts
    import_default_garments
    build_ui
    run_api "$@"
    ;;
  run-with-ollama)
    switch_branch
    install_system_dependencies
    bootstrap_runtime
    import_default_size_charts
    import_default_garments
    build_ui
    run_api --start-ollama "$@"
    ;;
  preflight)
    switch_branch
    python -m scripts.kiosk_preflight "$@"
    ;;
  check)
    switch_branch
    install_system_dependencies
    bootstrap_runtime
    import_default_size_charts
    import_default_garments
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
