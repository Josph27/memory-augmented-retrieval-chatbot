#!/usr/bin/env python3
"""
Pi token usage & cache monitor.

Reads Pi's .jsonl session files and reports per-session and project-wide
token costs, cache hit rates, tool usage, and cache-breakage patterns.

Usage:
  python scripts/token_monitor.py                    # latest session detail
  python scripts/token_monitor.py --sessions          # list all sessions
  python scripts/token_monitor.py --project           # project-wide aggregate
  python scripts/token_monitor.py --session <id>      # specific session detail
  python scripts/token_monitor.py --cache-trace       # per-turn cache hit analysis
  python scripts/token_monitor.py --watch             # live-poll latest session
  python scripts/token_monitor.py --project --json    # machine-readable output
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Optional


SESSIONS_DIR = Path.home() / ".pi/agent/sessions"


def _path_to_session_key(path: Path) -> str:
    """Convert a filesystem path to Pi's session directory encoding.

    Pi encodes absolute paths as: leading -- for root /, then - as / separator,
    trailing -- for directories.  E.g. /home/josph/repo -> --home-josph-repo--
    """
    parts = str(path.resolve()).split("/")
    # parts[0] is '' (empty string before leading /), so parts[1:] are the segments
    segments = [p for p in parts if p]  # filter empty strings
    return "--" + "-".join(segments) + "--"


def find_project_dir() -> Optional[Path]:
    """Auto-detect the Pi sessions directory for the current project."""
    cwd = Path.cwd().resolve()
    cwd_key = _path_to_session_key(cwd)
    candidate = SESSIONS_DIR / cwd_key
    if candidate.is_dir():
        return candidate
    # Fallback: search for partial match
    cwd_name = "-".join(p for p in str(cwd).split("/") if p)
    for d in SESSIONS_DIR.iterdir():
        if d.is_dir() and cwd_name in d.name:
            return d
    return None


def find_all_project_dirs() -> list[Path]:
    """Return all project session directories."""
    if not SESSIONS_DIR.is_dir():
        return []
    return sorted(
        [d for d in SESSIONS_DIR.iterdir() if d.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def list_sessions(project_dir: Path) -> list[Path]:
    """Return sorted session .jsonl files for a project."""
    if not project_dir.is_dir():
        return []
    return sorted(
        project_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def parse_session(session_path: Path) -> Optional[dict]:
    """Parse a .jsonl session file and extract aggregate usage data."""
    messages = 0
    turns = 0
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_write = 0
    total_cost = 0.0
    tool_calls: dict[str, int] = defaultdict(int)
    cache_resets = 0
    prev_cache_read = -1
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None
    model: Optional[str] = None

    try:
        with open(session_path, encoding="utf-8") as f:
            for line in f:
                try:
                    msg = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                messages += 1
                ts = msg.get("timestamp", "")
                if not first_ts:
                    first_ts = ts
                last_ts = ts

                # Track model
                if msg.get("type") == "model_change":
                    model = msg.get("data", {}).get("model", model)

                # Count user turns
                if msg.get("type") == "message" and msg.get("message", {}).get("role") == "user":
                    turns += 1

                # Extract usage from assistant messages
                usage = msg.get("message", {}).get("usage") or msg.get("usage")
                if usage:
                    cr = int(usage.get("cacheRead", 0))
                    total_input += int(usage.get("input", 0))
                    total_output += int(usage.get("output", 0))
                    total_cache_read += cr
                    total_cache_write += int(usage.get("cacheWrite", 0))
                    total_cost += float(usage.get("cost", {}).get("total", 0))

                    # Detect cache resets: cache_read drops significantly
                    if prev_cache_read >= 0 and cr < prev_cache_read * 0.5:
                        cache_resets += 1
                    prev_cache_read = cr

                # Count tool calls
                if msg.get("type") == "message":
                    for block in msg.get("message", {}).get("content", []):
                        if block.get("type") == "toolCall":
                            tool_calls[block.get("name", "unknown")] += 1

    except (FileNotFoundError, PermissionError, OSError) as exc:
        print(f"Error reading {session_path}: {exc}", file=sys.stderr)
        return None

    total_input_tokens = total_input + total_cache_read
    return {
        "path": session_path,
        "name": session_path.name.replace(".jsonl", ""),
        "short_name": session_path.name[:19].replace("T", " "),
        "messages": messages,
        "turns": turns,
        "model": model or "unknown",
        "first_ts": first_ts,
        "last_ts": last_ts,
        "total_input": total_input,
        "total_output": total_output,
        "cache_read": total_cache_read,
        "cache_write": total_cache_write,
        "total_tokens": total_input + total_output + total_cache_read,
        "cost": total_cost,
        "tools": dict(tool_calls),
        "cache_resets": cache_resets,
        "cache_hit_pct": (total_cache_read / total_input_tokens * 100)
        if total_input_tokens > 0
        else 0,
    }


def format_cost(cost: float) -> str:
    if cost < 0.001:
        return f"${cost:.6f}"
    elif cost < 0.01:
        return f"${cost:.5f}"
    elif cost < 1:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def fmt(n: int) -> str:
    """Format integer with commas."""
    return f"{n:,}"


def print_session_detail(stats: dict):
    """Detailed breakdown for one session."""
    duration = ""
    if stats["first_ts"] and stats["last_ts"]:
        try:
            t1 = datetime.fromisoformat(stats["first_ts"].replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(stats["last_ts"].replace("Z", "+00:00"))
            secs = (t2 - t1).total_seconds()
            if secs < 120:
                duration = f"{secs:.0f}s"
            elif secs < 3600:
                duration = f"{secs / 60:.1f}m"
            else:
                duration = f"{secs / 3600:.1f}h"
        except (ValueError, TypeError):
            pass

    print(f"\n{'=' * 70}")
    print(f"Session: {stats['name']}")
    print(f"{'=' * 70}")
    print(f"  Duration:         {duration}  |  Model: {stats['model']}")
    print(f"  Messages:         {stats['messages']}  |  User turns: {stats['turns']}")
    print(f"  Cache resets:     {stats['cache_resets']}  (tool-list changes that broke cache)")
    print(f"  ---")
    print(f"  Fresh input:      {fmt(stats['total_input'])} tokens")
    print(f"  Cached read:      {fmt(stats['cache_read'])} tokens")
    print(f"  Cached write:     {fmt(stats['cache_write'])} tokens")
    print(f"  Output:           {fmt(stats['total_output'])} tokens")
    print(f"  Total tokens:     {fmt(stats['total_tokens'])}")
    print(f"  Cache hit rate:   {stats['cache_hit_pct']:.1f}%")
    print(f"  Cost:             {format_cost(stats['cost'])}")
    if stats["tools"]:
        print(f"\n  Top tool calls:")
        for tool, count in sorted(stats["tools"].items(), key=lambda x: -x[1])[:15]:
            print(f"    {tool:<30} {count:>4}")


def print_sessions_table(sessions: list[dict], title: str = "SESSIONS"):
    """Print a compact sessions table (multiple sessions in one project)."""
    print(f"\n{'=' * 100}")
    print(f"{title} ({len(sessions)} sessions)")
    print(f"{'=' * 100}")
    header = (
        f"  {'START':<20} {'TURNS':>5} {'MSGS':>5} {'CACHE_HIT':>9} "
        f"{'CACHE_R':>10} {'INPUT':>9} {'RESETS':>7} {'COST':>10}"
    )
    print(header)
    print(f"  {'-' * 85}")
    for s in sessions:
        print(
            f"  {s['short_name']:<20} {s['turns']:>5} {s['messages']:>5} "
            f"{s['cache_hit_pct']:>8.1f}% {fmt(s['cache_read']):>10} "
            f"{fmt(s['total_input']):>9} {s['cache_resets']:>7} "
            f"{format_cost(s['cost']):>10}"
        )


def print_project_summary(project_dir: Path, all_sessions: list[dict]):
    """Aggregate summary across all sessions in a project."""
    if not all_sessions:
        print("No session data found.")
        return

    total_cost = sum(s["cost"] for s in all_sessions)
    total_messages = sum(s["messages"] for s in all_sessions)
    total_turns = sum(s["turns"] for s in all_sessions)
    total_tokens = sum(s["total_tokens"] for s in all_sessions)
    total_cache_read = sum(s["cache_read"] for s in all_sessions)
    total_input = sum(s["total_input"] for s in all_sessions)
    total_resets = sum(s["cache_resets"] for s in all_sessions)
    total_input_with_cache = total_input + total_cache_read

    all_tools: dict[str, int] = defaultdict(int)
    for s in all_sessions:
        for tool, count in s["tools"].items():
            all_tools[tool] += count

    project_name = str(project_dir.name).replace("--", "/").replace("-home-josph-", "~")

    print(f"\n{'=' * 70}")
    print(f"PROJECT: {project_name}")
    print(f"{'=' * 70}")
    print(f"  Sessions:          {len(all_sessions)}")
    print(f"  Total messages:    {fmt(total_messages)}")
    print(f"  Total user turns:  {fmt(total_turns)}")
    print(f"  Cache resets:      {fmt(total_resets)}")
    print(f"  ---")
    print(f"  Fresh input:       {fmt(total_input)} tokens")
    print(f"  Cached read:       {fmt(total_cache_read)} tokens")
    print(
        f"  Overall hit rate:  {total_cache_read / total_input_with_cache * 100:.1f}%"
        if total_input_with_cache > 0
        else "  Overall hit rate:  N/A"
    )
    print(f"  Total cost:        {format_cost(total_cost)}")
    print(f"  Avg cost/session:  {format_cost(total_cost / len(all_sessions))}")

    if all_tools:
        print(f"\n  Top tools (project-wide):")
        for tool, count in sorted(all_tools.items(), key=lambda x: -x[1])[:15]:
            print(f"    {tool:<30} {count:>4}")


def _collect_turn_tools(msgs: list, user_idx: list) -> dict:
    """Map turn number -> set of tool names called during that turn."""
    turn_tools = {}
    for t, uidx in enumerate(user_idx, 1):
        next_uidx = user_idx[t] if t < len(user_idx) else len(msgs)
        tools = set()
        for m in msgs[uidx:next_uidx]:
            if m.get("type") == "message":
                for block in m.get("message", {}).get("content", []):
                    if block.get("type") == "toolCall":
                        tools.add(block.get("name", "?"))
        turn_tools[t] = tools
    return turn_tools


# Tools that mutate the tool list when called (cache-killers)
ACTIVATOR_TOOLS = {
    "pi_lens_activate_tools",  # activates ast_grep_search, lsp_navigation, etc.
    "skill_manage",  # create/update/delete skills → may change tool list
}

# MCP calls that connect to servers and register new tools
MCP_CONNECT_ACTION = "connect"


def _extract_mcp_connects(msgs: list) -> dict:
    """Find mcp connect calls and which server they connected to."""
    connects = {}
    for i, m in enumerate(msgs):
        if m.get("type") == "message":
            for block in m.get("message", {}).get("content", []):
                if block.get("type") == "toolCall" and block.get("name") == "mcp":
                    try:
                        args = json.loads(block.get("arguments", "{}"))
                        if args.get("connect"):
                            connects[i] = args["connect"]
                    except (json.JSONDecodeError, TypeError):
                        pass
    return connects


def print_cache_trace(session_path: Path):
    """Detailed per-turn cache hit analysis — reveals cache-breakage pattern.

    Identifies tool-list mutations (activator calls, MCP connections) and
    correlates them with cache resets. Shows which specific tools likely
    caused each cache break.
    """
    try:
        with open(session_path, encoding="utf-8") as f:
            msgs = [json.loads(line) for line in f if line.strip()]
    except (FileNotFoundError, PermissionError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return

    user_msg_indices = [
        i
        for i, m in enumerate(msgs)
        if m.get("type") == "message" and m.get("message", {}).get("role") == "user"
    ]

    turn_tools = _collect_turn_tools(msgs, user_msg_indices)
    mcp_connects = _extract_mcp_connects(msgs)

    # Collect ALL tool names seen cumulatively (for "new tools" detection)
    cumulative_tools: set = set()

    # Detect tool activator calls across all messages
    activator_calls = []
    for i, m in enumerate(msgs):
        if m.get("type") == "message" and m.get("message", {}).get("role") == "assistant":
            for block in m.get("message", {}).get("content", []):
                if block.get("type") == "toolCall":
                    name = block.get("name", "")
                    if name in ACTIVATOR_TOOLS:
                        activator_calls.append((i, name, m.get("timestamp", "")[:19]))
                    elif name == "mcp":
                        try:
                            args = json.loads(block.get("arguments", "{}"))
                            if args.get("connect"):
                                activator_calls.append(
                                    (i, f"mcp→{args['connect']}", m.get("timestamp", "")[:19])
                                )
                        except (json.JSONDecodeError, TypeError):
                            pass

    print(f"\n{'=' * 100}")
    print(f"Cache Trace: {session_path.name}")
    print(f"{'=' * 100}")

    # Print explanation header
    print(f"\n  📋 HOW CACHE WORKS:")
    print(f"  DeepSeek's prefix: [TOOL DEFINITIONS] → [system prompt] → [conversation messages]")
    print(
        f"  Cache BREAKS when: any tool is added/removed, shifting byte positions of everything after."
    )
    print(f"  Cache PERSISTS when: only new messages are appended (prefix unchanged).")
    print(
        f"  Activator tools that mutate the tool list: {', '.join(sorted(ACTIVATOR_TOOLS))}, mcp(connect=...)"
    )

    # Print activator timeline
    if activator_calls:
        print(f"\n  ⚡ TOOL-LIST MUTATIONS DETECTED:")
        for idx, name, ts in activator_calls:
            # Find which turn this was in
            turn = 1
            for t, uid in enumerate(user_msg_indices, 1):
                if idx > uid:
                    turn = t + 1
            print(f"    MSG {idx} [turn {turn}] [{ts}] → {name}")
    else:
        print(f"\n  ℹ️  No explicit tool-list mutations detected in this session.")
        print(f"     Cache resets may be from: DeepSeek server-side eviction,")
        print(f"     load-balancing to a different node, or implicit tool changes.")

    print(
        f"\n  {'TURN':>4} {'MSG#':>5} {'USER_TS':<20} {'GAP':>6} "
        f"{'CACHE_R':>9} {'INPUT':>8} {'HIT%':>6} {'RESET_COST':>10} {'NOTE'}"
    )
    print(f"  {'-' * 85}")

    prev_cache = 0
    prev_cr = 0
    for turn_num, user_idx in enumerate(user_msg_indices, 1):
        # Find the FIRST assistant message after this user message
        first_ast = None
        for j in range(user_idx + 1, len(msgs)):
            m = msgs[j]
            if m.get("type") == "message" and m.get("message", {}).get("role") == "assistant":
                usage = m.get("message", {}).get("usage", {})
                if usage.get("cacheRead", 0) > 0 or usage.get("input", 0) > 0:
                    first_ast = (j, m)
                    break

        if not first_ast:
            print(f"  {turn_num:>4} {user_idx:>5} (no assistant response found)")
            continue

        ast_idx, ast_msg = first_ast
        usage = ast_msg.get("message", {}).get("usage", {})
        cr = usage.get("cacheRead", 0)
        inp = usage.get("input", 0)
        cw = usage.get("cacheWrite", 0)
        total_in = cr + inp
        hit_pct = cr / total_in * 100 if total_in > 0 else 0

        # Gap from previous assistant's last message to this user message
        ts = msgs[user_idx].get("timestamp", "")[:19]
        gap = ""
        prev_ast_ts = None
        for j in range(user_idx - 1, -1, -1):
            if (
                msgs[j].get("type") == "message"
                and msgs[j].get("message", {}).get("role") == "assistant"
            ):
                prev_ast_ts = msgs[j].get("timestamp", "")
                break

        if prev_ast_ts and ts:
            try:
                t1 = datetime.fromisoformat(prev_ast_ts.replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                gap = f"{(t2 - t1).total_seconds():.0f}s"
            except (ValueError, TypeError):
                pass

        # Is this a cache reset?
        is_reset = turn_num > 1 and cr <= 30000

        # Estimate reset cost: the fresh input that SHOULD have been cached
        reset_cost_tokens = 0
        reset_cost_dollars = 0.0
        if is_reset and prev_cr > 30000:
            # The conversation that should have been cached = current input
            reset_cost_tokens = inp
            # DeepSeek input: ~$0.27/M tokens, cached: ~$0.01/M → diff ≈ $0.26/M
            reset_cost_dollars = reset_cost_tokens * 0.26 / 1_000_000

        # Cache analysis
        note = ""
        if turn_num == 1:
            note = "fresh session"
        elif is_reset:
            # Try to identify cause
            causes = []

            # Check for activator calls in the PREVIOUS turn's range
            prev_uidx = user_msg_indices[turn_num - 2] if turn_num >= 2 else 0
            for idx, name, _ in activator_calls:
                if prev_uidx <= idx < user_idx:
                    causes.append(name)

            # Check for new tools that appeared only AFTER this reset
            this_turn_tools = turn_tools.get(turn_num, set())
            new_tools = this_turn_tools - cumulative_tools

            if causes:
                note = f"🔴 RESET — caused by: {', '.join(causes)}"
            elif new_tools:
                note = f"🔴 RESET — new tools appeared: {', '.join(sorted(new_tools))}"
            else:
                note = "🔴 RESET — server-side (eviction/load-balance)"
        elif cr > prev_cache * 1.1:
            note = "🟢 cache grew (healthy)"
        else:
            note = "⚪ stable"

        prev_cache = cr
        prev_cr = cr

        # Track tools cumulatively
        cumulative_tools |= turn_tools.get(turn_num, set())

        reset_cost_str = f"{fmt(reset_cost_tokens)} tkn" if reset_cost_tokens > 0 else "-"

        print(
            f"  {turn_num:>4} {user_idx:>5} {ts:<20} {gap:>6} "
            f"{fmt(cr):>9} {fmt(inp):>8} "
            f"{hit_pct:>5.1f}% {reset_cost_str:>10}  {note}"
        )

    # Summary
    resets = sum(1 for _ in user_msg_indices)
    print(f"\n  💡 CACHE RESET = cache_read drops to baseline (~29K system prompt only).")
    print(f"     This means conversation history was NOT cached → recharged at full input price.")
    print(f"     Each reset costs ~$0.26/M tokens of conversation history.")


def watch_session(session_path: Path):
    """Poll a session file for new messages (live monitoring)."""
    import time

    print(f"Watching: {session_path}")
    last_size = session_path.stat().st_size if session_path.exists() else 0

    while True:
        try:
            current_size = session_path.stat().st_size
            if current_size > last_size:
                with open(session_path, encoding="utf-8") as f:
                    f.seek(last_size)
                    for line in f:
                        try:
                            msg = json.loads(line.strip())
                            usage = msg.get("message", {}).get("usage")
                            if usage:
                                ts = msg.get("timestamp", "")[:19]
                                cr = usage.get("cacheRead", 0)
                                inp = usage.get("input", 0)
                                out = usage.get("output", 0)
                                cost = usage.get("cost", {}).get("total", 0)
                                total_in = cr + inp
                                hit = cr / total_in * 100 if total_in > 0 else 0
                                print(
                                    f"  [{ts}] cache={fmt(cr)} input={fmt(inp)} "
                                    f"out={fmt(out)} hit={hit:.0f}% "
                                    f"cost={format_cost(cost)}"
                                )
                        except (json.JSONDecodeError, KeyError):
                            pass
                last_size = current_size
            time.sleep(2)
        except KeyboardInterrupt:
            print("\nStopped watching.")
            break
        except FileNotFoundError:
            time.sleep(2)


def to_json(data) -> str:
    """Serialize to JSON string."""

    def default(obj):
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(data, indent=2, default=default)


def main():
    parser = argparse.ArgumentParser(description="Pi token usage & cache monitor")
    parser.add_argument("--session", type=str, help="Specific session ID (prefix match)")
    parser.add_argument("--sessions", action="store_true", help="List all sessions in project")
    parser.add_argument("--project", action="store_true", help="Project-wide aggregate")
    parser.add_argument("--cache-trace", action="store_true", help="Per-turn cache hit analysis")
    parser.add_argument("--watch", action="store_true", help="Live-poll latest session")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--top", type=int, default=10, help="Sessions to show (default: 10)")
    args = parser.parse_args()

    project_dir = find_project_dir()
    if not project_dir:
        print(f"Error: No Pi session data found for {Path.cwd()}", file=sys.stderr)
        print(f"Sessions dir: {SESSIONS_DIR}", file=sys.stderr)
        sys.exit(1)

    # --session: specific session
    if args.session:
        matching = [s for s in list_sessions(project_dir) if args.session in s.name]
        if not matching:
            print(f"No session matching '{args.session}'", file=sys.stderr)
            sys.exit(1)
        session_path = matching[0]

        if args.cache_trace:
            print_cache_trace(session_path)
        elif args.json:
            stats = parse_session(session_path)
            if stats:
                print(to_json(stats))
        else:
            stats = parse_session(session_path)
            if stats:
                print_session_detail(stats)
        return

    # --watch: live polling
    if args.watch:
        sessions = list_sessions(project_dir)
        if not sessions:
            print("No sessions found.", file=sys.stderr)
            sys.exit(1)
        watch_session(sessions[0])
        return

    # Gather all sessions
    all_stats = [s for s in (parse_session(p) for p in list_sessions(project_dir)) if s is not None]

    if not all_stats:
        print("No readable session data found.", file=sys.stderr)
        sys.exit(1)

    # --cache-trace on latest
    if args.cache_trace:
        print_cache_trace(all_stats[0]["path"])
        return

    # --project: aggregate
    if args.project:
        if args.json:
            summary = {
                "project": str(project_dir.name).replace("--", "/"),
                "sessions": len(all_stats),
                "total_turns": sum(s["turns"] for s in all_stats),
                "total_messages": sum(s["messages"] for s in all_stats),
                "total_input": sum(s["total_input"] for s in all_stats),
                "total_cache_read": sum(s["cache_read"] for s in all_stats),
                "total_cache_write": sum(s["cache_write"] for s in all_stats),
                "total_output": sum(s["total_output"] for s in all_stats),
                "total_tokens": sum(s["total_tokens"] for s in all_stats),
                "total_cost": sum(s["cost"] for s in all_stats),
                "total_cache_resets": sum(s["cache_resets"] for s in all_stats),
                "cache_hit_pct": sum(s["cache_read"] for s in all_stats)
                / sum(s["total_input"] + s["cache_read"] for s in all_stats)
                * 100
                if sum(s["total_input"] + s["cache_read"] for s in all_stats) > 0
                else 0,
            }
            print(to_json(summary))
        else:
            print_project_summary(project_dir, all_stats)
            print_sessions_table(all_stats[: args.top])
        return

    # --sessions: list all
    if args.sessions:
        print_sessions_table(all_stats[: args.top], title=f"SESSIONS — {project_dir.name}")
        return

    # Default: latest session detail + compact session table
    print_session_detail(all_stats[0])
    print_sessions_table(all_stats[1 : args.top + 1], title="OTHER RECENT SESSIONS")


if __name__ == "__main__":
    main()
