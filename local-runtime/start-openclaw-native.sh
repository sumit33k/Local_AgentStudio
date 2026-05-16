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
    echo ""
    echo "        The OpenClaw submodule may not be initialised. Run:"
    echo "          git submodule update --init vendor/openclaw"
    exit 1
fi

# ---------------------------------------------------------------------------
# Verify openclaw.mjs exists
# ---------------------------------------------------------------------------
if [ ! -f "${OPENCLAW_MJS}" ]; then
    echo "[ERROR] openclaw.mjs not found at: ${OPENCLAW_MJS}"
    echo ""
    echo "        Run: git submodule update --init vendor/openclaw"
    exit 1
fi

# ---------------------------------------------------------------------------
# Install dependencies if node_modules is missing
# ---------------------------------------------------------------------------
if [ ! -d "${VENDOR_DIR}/node_modules" ]; then
    echo "[INFO] node_modules not found — running npm install in ${VENDOR_DIR} ..."
    (cd "${VENDOR_DIR}" && npm install --prefer-offline 2>&1) || {
        echo "[ERROR] npm install failed."
        echo "        Make sure you have network access and npm is on your PATH."
        exit 1
    }
    echo "[INFO] npm install complete."
    echo ""
fi

# ---------------------------------------------------------------------------
# Build if dist/entry.mjs is missing (source-tree install)
# ---------------------------------------------------------------------------
DIST_ENTRY="${VENDOR_DIR}/dist/entry.mjs"
if [ ! -f "${DIST_ENTRY}" ]; then
    echo "[INFO] Build output not found at dist/entry.mjs — building OpenClaw ..."
    echo "[INFO] This runs once; subsequent starts will skip this step."
    echo ""

    # Prefer pnpm if available (project standard), fall back to npm
    if command -v pnpm &>/dev/null; then
        echo "[INFO] Using pnpm ..."
        (cd "${VENDOR_DIR}" && pnpm install && pnpm build 2>&1) || {
            echo "[ERROR] pnpm build failed."
            echo "        Try manually:"
            echo "          cd ${VENDOR_DIR} && pnpm install && pnpm build"
            exit 1
        }
    else
        echo "[INFO] pnpm not found; falling back to npm ..."
        (cd "${VENDOR_DIR}" && npm install && npm run build 2>&1) || {
            echo "[ERROR] npm build failed."
            echo "        Or install pnpm and retry:"
            echo "          npm install -g pnpm"
            echo "          cd ${VENDOR_DIR} && pnpm install && pnpm build"
            exit 1
        }
    fi

    echo ""
    echo "[INFO] Build complete."
    echo ""
fi

# Sanity-check: dist/entry.mjs must now exist
if [ ! -f "${DIST_ENTRY}" ]; then
    echo "[ERROR] Build finished but dist/entry.mjs still not found."
    echo "        Check the build output above for errors."
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
