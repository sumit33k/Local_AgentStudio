#!/bin/bash
# Local Ollama Chat - macOS/Linux launcher

set -e
cd "$(dirname "$0")"

echo "========================================="
echo "  Local Ollama Chat - Starting up"
echo "========================================="
echo

# 1. Check Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "[ERROR] Ollama not found."
    echo "Install with: brew install ollama"
    echo "Or download:  https://ollama.com/download"
    read -p "Press Enter to exit..."
    exit 1
fi

# 2. Start Ollama server if not running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama server..."
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
else
    echo "Ollama server already running."
fi

# 3. Pull models if missing (comment out any you don't want)
echo
echo "Checking models..."
if ! ollama list | grep -qi "qwen"; then
    echo "Pulling qwen2.5... this only happens once."
    ollama pull qwen2.5
fi
if ! ollama list | grep -qi "deepseek"; then
    echo "Pulling deepseek-r1... this only happens once."
    ollama pull deepseek-r1
fi

# 4. Open the chat UI in default browser
echo
echo "Opening chat interface..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "$(pwd)/index.html"
else
    xdg-open "$(pwd)/index.html" 2>/dev/null || echo "Open index.html manually in your browser."
fi

echo
echo "Done. Ollama server is running in the background."
echo "To stop it later: pkill ollama"
