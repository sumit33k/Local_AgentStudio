#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "Checking Ollama..."
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Install it from https://ollama.com and rerun this script."
  exit 1
fi

if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Starting Ollama service..."
  ollama serve >/tmp/ollama-skill-studio.log 2>&1 &
  sleep 3
fi

echo "Checking DeepSeek model..."
if ! ollama list | grep -q "deepseek-r1"; then
  echo "Pulling deepseek-r1:8b. This may take a while."
  ollama pull deepseek-r1:8b
fi

echo "Starting backend..."
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

echo "Starting frontend..."
cd frontend
npm install
npm run dev &
FRONTEND_PID=$!
cd ..

echo "DeepSeek Skill Studio is running at http://localhost:3000"
echo "Press Ctrl+C to stop."
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true" EXIT
wait
