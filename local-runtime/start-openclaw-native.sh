#!/usr/bin/env bash
# start-openclaw-native.sh — Start the OpenClaw gateway subprocess
# Binds to 127.0.0.1:18789 only. Never uses shell=True or eval.
#
# Usage: bash start-openclaw-native.sh
# Stop:  Ctrl+C

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENDOR_DIR="${PROJECT_ROOT}/vendor/openclaw"
OPENCLAW_MJS="${VENDOR_DIR}/openclaw.mjs"

GATEWAY_HOST="127.0.0.1"
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"

# ---------------------------------------------------------------------------
# Check Node.js
# ---------------------------------------------------------------------------
if ! command -v node &>/dev/null; then
    echo "[ERROR] 'node' not found on PATH."
    echo "        Install Node.js 18 LTS from https://nodejs.org"
    exit 1
fi

NODE_VERSION="$(node --version 2>/dev/null || echo "unknown")"
echo "[INFO] Using Node.js ${NODE_VERSION}"

# ---------------------------------------------------------------------------
# Verify vendor/openclaw exists and has package.json
# ---------------------------------------------------------------------------
if [ ! -f "${VENDOR_DIR}/package.json" ]; then
    echo "[ERROR] vendor/openclaw/package.json not found at: ${VENDOR_DIR}"
    echo "        The OpenClaw submodule may not be initialised."
    echo ""
    echo "        To fix:"
    echo "          git submodule update --init vendor/openclaw"
    echo "          cd vendor/openclaw && npm install"
    exit 1
fi

# ---------------------------------------------------------------------------
# Warn if node_modules is missing
# ---------------------------------------------------------------------------
if [ ! -d "${VENDOR_DIR}/node_modules" ]; then
    echo "[WARN] node_modules not found in ${VENDOR_DIR}"
    echo "       Run the following before starting the gateway:"
    echo "         cd ${VENDOR_DIR}"
    echo "         npm install"
    echo ""
    echo "[INFO] Attempting to continue anyway (npx fallback may work)..."
fi

# ---------------------------------------------------------------------------
# Verify openclaw.mjs exists
# ---------------------------------------------------------------------------
if [ ! -f "${OPENCLAW_MJS}" ]; then
    echo "[ERROR] openclaw.mjs not found at: ${OPENCLAW_MJS}"
    echo "        The OpenClaw package may be incomplete."
    echo "        Run: git submodule update --init vendor/openclaw"
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
# Start the OpenClaw gateway
# Command is constructed as an array — never uses eval or shell expansion
# of external input. This is the equivalent of shell=False.
# ---------------------------------------------------------------------------
echo "[INFO] Starting OpenClaw gateway on ${GATEWAY_HOST}:${GATEWAY_PORT} ..."
echo "[INFO] Vendor path: ${VENDOR_DIR}"
echo ""
echo "  OpenClaw gateway: http://${GATEWAY_HOST}:${GATEWAY_PORT}"
echo "  Press Ctrl+C to stop."
echo ""

# All arguments are literals or controlled variables — no user input interpolated.
exec node \
    "${OPENCLAW_MJS}" \
    gateway \
    --host "${GATEWAY_HOST}" \
    --port "${GATEWAY_PORT}"
