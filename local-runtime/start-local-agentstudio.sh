#!/usr/bin/env bash
# start-local-agentstudio.sh — Start Local AgentStudio Pro (backend + frontend)
# Binds all services to 127.0.0.1 only. Never exposes ports on 0.0.0.0.
#
# Usage: bash start-local-agentstudio.sh
# Stop:  Ctrl+C

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve script and project root paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/deepseek-skill-studio/backend"
FRONTEND_DIR="${PROJECT_ROOT}/deepseek-skill-studio/frontend"

BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
FRONTEND_PORT="3000"

# PID tracking for cleanup
BACKEND_PID=""
FRONTEND_PID=""

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo "=============================================="
echo "   Local AgentStudio Pro"
echo "=============================================="
echo ""

# ---------------------------------------------------------------------------
# Dependency checks (warn only — do not exit on missing tools)
# ---------------------------------------------------------------------------
check_dependency() {
    local cmd="$1"
    local install_hint="$2"
    if ! command -v "${cmd}" &>/dev/null; then
        echo "[WARN] '${cmd}' not found on PATH."
        echo "       ${install_hint}"
        echo ""
    fi
}

check_dependency python3 "Install Python 3.10+ from https://python.org"
check_dependency node    "Install Node.js 18 LTS from https://nodejs.org"

# ---------------------------------------------------------------------------
# Virtual environment check
# ---------------------------------------------------------------------------
VENV_DIR="${BACKEND_DIR}/.venv"
if [ ! -d "${VENV_DIR}" ]; then
    echo "[WARN] Python virtual environment not found at: ${VENV_DIR}"
    echo "       To create it, run:"
    echo "         cd ${BACKEND_DIR}"
    echo "         python3 -m venv .venv"
    echo "         source .venv/bin/activate"
    echo "         pip install -r requirements.txt"
    echo ""
fi

# Determine the uvicorn binary to use (prefer venv)
if [ -x "${VENV_DIR}/bin/uvicorn" ]; then
    UVICORN="${VENV_DIR}/bin/uvicorn"
elif command -v uvicorn &>/dev/null; then
    UVICORN="uvicorn"
else
    echo "[ERROR] uvicorn not found. Please install it:"
    echo "        cd ${BACKEND_DIR}"
    echo "        python3 -m venv .venv && source .venv/bin/activate"
    echo "        pip install -r requirements.txt"
    exit 1
fi

# ---------------------------------------------------------------------------
# Load .env if present
# ---------------------------------------------------------------------------
ENV_FILE="${SCRIPT_DIR}/.env"
if [ -f "${ENV_FILE}" ]; then
    echo "[INFO] Loading environment from ${ENV_FILE}"
    # shellcheck disable=SC1090
    set -a
    source "${ENV_FILE}"
    set +a
fi

# ---------------------------------------------------------------------------
# Cleanup on Ctrl+C
# ---------------------------------------------------------------------------
cleanup() {
    echo ""
    echo "[INFO] Shutting down Local AgentStudio Pro..."

    if [ -n "${BACKEND_PID}" ] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
        echo "[INFO] Stopping backend (pid=${BACKEND_PID})..."
        kill "${BACKEND_PID}" 2>/dev/null || true
        wait "${BACKEND_PID}" 2>/dev/null || true
    fi

    if [ -n "${FRONTEND_PID}" ] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
        echo "[INFO] Stopping frontend (pid=${FRONTEND_PID})..."
        kill "${FRONTEND_PID}" 2>/dev/null || true
        wait "${FRONTEND_PID}" 2>/dev/null || true
    fi

    echo "[INFO] Stopped. Goodbye."
    exit 0
}

trap cleanup SIGINT SIGTERM

# ---------------------------------------------------------------------------
# Start FastAPI backend
# ---------------------------------------------------------------------------
echo "[INFO] Starting FastAPI backend on ${BACKEND_HOST}:${BACKEND_PORT} ..."

(
    cd "${BACKEND_DIR}"
    "${UVICORN}" main:app \
        --host "${BACKEND_HOST}" \
        --port "${BACKEND_PORT}" \
        --reload
) &
BACKEND_PID="$!"

# ---------------------------------------------------------------------------
# Start Next.js frontend
# ---------------------------------------------------------------------------
echo "[INFO] Starting Next.js frontend on ${BACKEND_HOST}:${FRONTEND_PORT} ..."

(
    cd "${FRONTEND_DIR}"
    # HOST env var tells Next.js dev server which interface to bind
    HOST="${BACKEND_HOST}" npm run dev -- --port "${FRONTEND_PORT}"
) &
FRONTEND_PID="$!"

# ---------------------------------------------------------------------------
# Print ready message
# ---------------------------------------------------------------------------
echo ""
echo "----------------------------------------------"
echo "  Local AgentStudio Pro is starting up."
echo ""
echo "  Frontend:  http://${BACKEND_HOST}:${FRONTEND_PORT}"
echo "  API docs:  http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
echo "  Health:    http://${BACKEND_HOST}:${BACKEND_PORT}/health"
echo ""
echo "  Press Ctrl+C to stop all services."
echo "----------------------------------------------"
echo ""

# ---------------------------------------------------------------------------
# Wait for background processes
# ---------------------------------------------------------------------------
wait "${BACKEND_PID}" "${FRONTEND_PID}"
