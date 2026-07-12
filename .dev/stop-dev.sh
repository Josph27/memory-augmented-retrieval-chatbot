#!/bin/bash
# stop-dev.sh — safely shut down running development servers via PID files
set -o pipefail

PID_DIR="/tmp/braemon-pids"
MAX_WAIT=5

echo "Stopping development servers..."

for svc in chainlit vite; do
	pidfile="$PID_DIR/$svc.pid"
	if [ ! -f "$pidfile" ]; then
		echo "  [$svc] not running (no PID file)"
		continue
	fi
	pid=$(cat "$pidfile" 2>/dev/null) || continue
	if ! kill -0 "$pid" 2>/dev/null; then
		echo "  [$svc] not running (stale PID $pid)"
		rm -f "$pidfile"
		continue
	fi
	echo "  [$svc] sending SIGTERM to PID $pid..."
	kill -TERM "$pid" 2>/dev/null || true
done

# Wait for graceful exit
started=$(date +%s)
while true; do
	all_dead=true
	for svc in chainlit vite; do
		pidfile="$PID_DIR/$svc.pid"
		[ -f "$pidfile" ] || continue
		pid=$(cat "$pidfile" 2>/dev/null) || continue
		if kill -0 "$pid" 2>/dev/null; then
			all_dead=false
			break
		fi
	done
	$all_dead && break
	if [ $(($(date +%s) - started)) -ge $MAX_WAIT ]; then
		echo "  Force-killing remaining processes..."
		for svc in chainlit vite; do
			pidfile="$PID_DIR/$svc.pid"
			[ -f "$pidfile" ] || continue
			pid=$(cat "$pidfile" 2>/dev/null) || continue
			kill -KILL "$pid" 2>/dev/null || true
		done
		break
	fi
	sleep 0.3
done

rm -f "$PID_DIR"/chainlit.pid "$PID_DIR"/vite.pid
echo "All servers stopped."
