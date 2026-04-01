#!/bin/bash
# Start the job agent React dashboard (FastAPI backend + Vite frontend)

REPO="$(cd "$(dirname "$0")" && pwd)"

echo "Starting FastAPI backend on :8000..."
cd "$REPO"
source venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!

echo "Starting React frontend on :5173..."
cd "$REPO/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Dashboard: http://localhost:3001"
echo "API:       http://localhost:8001"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
