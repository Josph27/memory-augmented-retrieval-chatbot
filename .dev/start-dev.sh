#!/bin/bash
# start-dev.sh — safely start backend + frontend, track PIDs, clean shutdown
set -o pipefail
cd "$(dirname "$0")/.."

PID_DIR="/tmp/braemon-pids"
mkdir -p "$PID_DIR" logs

# ── Cleanup: SIGTERM → wait → SIGKILL ──────────────────────────
cleanup() {
	echo ""
	echo "Shutting down development servers..."
	local MAX_WAIT=5

	for svc in chainlit vite; do
		local pidfile="$PID_DIR/$svc.pid"
		[ -f "$pidfile" ] || continue
		local pid
		pid=$(cat "$pidfile" 2>/dev/null) || continue
		# Send SIGTERM for graceful shutdown
		kill -TERM "$pid" 2>/dev/null || true
	done

	# Wait for processes to exit gracefully
	local started
	started=$(date +%s)
	while true; do
		local all_dead=true
		for svc in chainlit vite; do
			local pidfile="$PID_DIR/$svc.pid"
			[ -f "$pidfile" ] || continue
			local pid
			pid=$(cat "$pidfile" 2>/dev/null) || continue
			if kill -0 "$pid" 2>/dev/null; then
				all_dead=false
				break
			fi
		done
		$all_dead && break
		if [ $(($(date +%s) - started)) -ge $MAX_WAIT ]; then
			echo "Some processes did not exit gracefully, force-killing..."
			for svc in chainlit vite; do
				local pidfile="$PID_DIR/$svc.pid"
				[ -f "$pidfile" ] || continue
				local pid
				pid=$(cat "$pidfile" 2>/dev/null) || continue
				kill -KILL "$pid" 2>/dev/null || true
			done
			break
		fi
		sleep 0.3
	done

	rm -f "$PID_DIR"/chainlit.pid "$PID_DIR"/vite.pid
	echo "Shutdown complete."
}
trap cleanup EXIT INT TERM

# ── Backend ─────────────────────────────────────────────────────
echo "[1/2] Starting Chainlit backend on port 8000..."
.venv/bin/python -m chainlit run app.py --port 8000 --headless \
	>logs/chainlit.log 2>&1 &
echo $! >"$PID_DIR/chainlit.pid"

# Wait for backend to be ready
echo -n "      Waiting for backend... "
for _ in $(seq 1 30); do
	if curl -s -o /dev/null http://localhost:8000 2>/dev/null; then
		echo "ready"
		break
	fi
	sleep 0.5
done

# ── Frontend ────────────────────────────────────────────────────
echo "[2/2] Starting Vite frontend on port 5173..."
cd braemon
npx vite --port 5173 >../logs/vite.log 2>&1 &
echo $! >"$PID_DIR/vite.pid"
cd ..

echo ""
echo "Development environment running."
echo "  Frontend : http://localhost:5173"
echo "  Backend  : http://localhost:8000"
echo "  PIDs     : $PID_DIR/"
echo ""
echo "Tailing logs... (Press Ctrl+C to stop both servers)"
echo "---------------------------------------------------"

touch logs/chainlit.log logs/vite.log logs/browser.log
tail -f logs/chainlit.log logs/vite.log logs/browser.log
