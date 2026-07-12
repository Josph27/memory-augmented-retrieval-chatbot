#!/bin/bash
set -e
cd "$(dirname "$0")/.."

# Setup trap to kill child processes on exit
trap 'kill $(jobs -p) 2>/dev/null || true' EXIT INT TERM

# Make sure logs directory exists
mkdir -p logs

echo "[1/2] Starting Chainlit backend on port 8000..."
# Use python module to start chainlit to avoid dependency on uv in PATH
.venv/bin/python -m chainlit run app.py --port 8000 --headless >logs/chainlit.log 2>&1 &
BACKEND_PID=$!

echo "[2/2] Starting Vite frontend on port 5173..."
cd braemon
# Use npx to find vite
npx vite --port 5173 >../logs/vite.log 2>&1 &
FRONTEND_PID=$!
cd ..

echo "Development environment running."
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000"
echo ""
echo "Tailing logs... (Press Ctrl+C to stop both servers)"
echo "---------------------------------------------------"

touch logs/chainlit.log logs/vite.log logs/browser.log
tail -f logs/chainlit.log logs/vite.log logs/browser.log
