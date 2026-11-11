#!/usr/bin/env bash
# Re-checks the three claims in README.md's "What this project found" against
# the installed engine, each with and without the fix, and writes everything
# (versions, commands, raw output) to evidence.txt.
#
#   ./setup.sh     # once, if .venv doesn't exist yet
#   ./retest.sh
#
# Needs RASA_LICENSE and the LLM_PROVIDER's API key, same as start.sh (.env is
# loaded if present). Runs on its own port (RETEST_PORT, default 5055) in
# throwaway copies of this folder, so it never touches this folder's models/,
# a running start.sh, or NoteVs's own agent on 5005. Tool calls are pointed at
# an unreachable NoteVs URL on purpose, so no real notes are read or changed.
# Costs a handful of LLM calls (RETEST_TRIES first messages, default 3, in
# each of runs A, C and D).
# Each message waits RETEST_COOLDOWN seconds (default 65) first: one Mantle
# call is ~3k input tokens, and Groq's free tier allows 7k per minute, so
# back-to-back runs otherwise fail with RateLimitError, not the behaviour
# under test. Any LLM error is printed with the run's output.
set -uo pipefail
cd "$(dirname "$0")"
SRC="$PWD"
OUT="$SRC/evidence.txt"
PORT="${RETEST_PORT:-5055}"
MESSAGE="list my notes"
COOLDOWN="${RETEST_COOLDOWN:-65}"
TRIES="${RETEST_TRIES:-3}"
FOLDER="/tmp/notevs-retest-folder"

if [ ! -d .venv ]; then
  echo "No .venv found — run ./setup.sh first." >&2
  exit 1
fi
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
LLM_PROVIDER="${LLM_PROVIDER:-groq}"
case "$LLM_PROVIDER" in
  groq) API_KEY_VAR=GROQ_API_KEY ;;
  openai) API_KEY_VAR=OPENAI_API_KEY ;;
  anthropic) API_KEY_VAR=ANTHROPIC_API_KEY ;;
  *) echo "Unknown LLM_PROVIDER '$LLM_PROVIDER'." >&2; exit 1 ;;
esac
if [ -z "${!API_KEY_VAR:-}" ] || [ -z "${RASA_LICENSE:-}" ]; then
  echo "$API_KEY_VAR and RASA_LICENSE must both be set (see .env.example)." >&2
  exit 1
fi
export LLM_PROVIDER RASA_PRO_LICENSE="${RASA_PRO_LICENSE:-$RASA_LICENSE}"
export NOTEVS_FOLDER_PATH="$FOLDER"
export NOTEVS_CALL_URL="http://127.0.0.1:9/call"

source .venv/bin/activate
WORK="$(mktemp -d)"
SERVER_PID=""
# `rasa run --debug` logs the provider API key in its LLM request lines, so
# the kept copy is redacted first.
keep_logs() {
  # Logs and trackers only (the project copies would read as extra
  # projects), redacted inside $WORK and moved into place only if redaction
  # succeeded: a failure keeps nothing.
  local tmp="$WORK/redacted"
  rm -rf "$SRC/retest-logs" "$tmp"
  mkdir -p "$tmp"
  cp "$WORK"/*.log "$WORK"/*.json "$tmp/" 2>/dev/null
  if python3 - "$tmp" "$SRC/.env" <<'PY'
import os, pathlib, re, sys
tmp, env_file = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
name = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|LICENSE", re.I)
values = {v for k, v in os.environ.items() if name.search(k)}
if env_file.is_file():
    for line in env_file.read_text().splitlines():
        k, sep, v = line.partition("=")
        if sep and name.search(k):
            values.add(v.strip().strip("'\""))
values = sorted((v for v in values if len(v) >= 8), key=len, reverse=True)
tokens = re.compile(r"gsk_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{16,}|(?i:bearer)\s+[A-Za-z0-9._~+/=-]{16,}")
fields = re.compile(r"""(?i)(["']?(?:api_key|token|secret|password|authorization)["']?\s*[:=]\s*["'])[^"']{8,}(["'])""")
for f in tmp.iterdir():
    s = f.read_text(errors="replace")
    for v in values:
        s = s.replace(v, "<redacted>")
    s = tokens.sub("<redacted>", s)
    s = fields.sub(r"\1<redacted>\2", s)
    f.write_text(s)
PY
  then
    mv "$tmp" "$SRC/retest-logs"
  else
    rm -rf "$tmp"
    echo "log redaction failed: no logs kept" >&2
  fi
}
cleanup() { stop_server; keep_logs; rm -rf "$WORK"; }
trap cleanup EXIT

: > "$OUT"
log() { printf '%s\n' "$*" | tee -a "$OUT"; }
section() { log ""; log "=================================================================="; log "$*"; log "=================================================================="; }

# Fresh copy of the project (no .venv/models/.env) with the llm: block set.
make_copy() {
  local dest="$WORK/$1"
  mkdir -p "$dest"
  (cd "$SRC" && tar -cf - --exclude=.venv --exclude=models --exclude=.env \
    --exclude=evidence.txt --exclude=.rasa . ) | (cd "$dest" && tar -xf -)
  python3 "$dest/set_llm_provider.py" >/dev/null
  echo "$dest"
}

train() {
  local dir="$1" name="$2"
  log "\$ rasa train   (in $name copy)"
  (cd "$dir" && rasa train > "$WORK/$name.train.log" 2>&1)
  local rc=$?
  log "exit code: $rc"
  if [ $rc -ne 0 ]; then
    log "--- last 30 lines of training log ---"
    tail -30 "$WORK/$name.train.log" | tee -a "$OUT"
  fi
  return $rc
}

# Starts `rasa run` in the background; returns 0 once GET / answers, 1 if the
# process exits first or it doesn't come up within 180s.
start_server() {
  local dir="$1" name="$2"
  log "\$ rasa run --enable-api --port $PORT --debug   (in $name copy)"
  (cd "$dir" && PYTHONUNBUFFERED=1 exec rasa run --enable-api --port "$PORT" --debug) > "$WORK/$name.run.log" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 1 180); do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      wait "$SERVER_PID"; local rc=$?
      SERVER_PID=""
      log "server process exited on its own, exit code: $rc"
      return 1
    fi
    if curl -s -o /dev/null "http://localhost:$PORT/"; then
      # Give anything that starts right after the REST listener (e.g. the
      # inspector channel) time to start, or to crash.
      sleep 10
      if kill -0 "$SERVER_PID" 2>/dev/null; then
        log "server is up: $(curl -s "http://localhost:$PORT/")"
        return 0
      fi
    fi
    sleep 1
  done
  log "server did not come up within 180s"
  return 1
}

stop_server() {
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" 2>/dev/null
    wait "$SERVER_PID" 2>/dev/null
    SERVER_PID=""
  fi
}

# Sends MESSAGE as the very first message of TRIES brand-new conversations
# and prints one line per try: the bot reply, which flows/skills started,
# which tools ran, the project.folder_path slot, and any LLM error the server
# logged during that turn. Several tries, because the LLM's choice (route,
# answer directly, or emit a malformed tool call) varies from call to call.
first_message() {
  local name="$1" i sender before reply
  log "\$ curl -X POST http://localhost:$PORT/webhooks/rest/webhook -d '{\"sender\": \"<new id each try>\", \"message\": \"$MESSAGE\"}'   x$TRIES"
  for i in $(seq 1 "$TRIES"); do
    sleep "$COOLDOWN"
    sender="retest-$name-$i-$(date +%s)"
    before=$(wc -l < "$WORK/$name.run.log")
    reply=$(curl -s -X POST "http://localhost:$PORT/webhooks/rest/webhook" \
      -H "Content-Type: application/json" \
      -d "{\"sender\": \"$sender\", \"message\": \"$MESSAGE\"}")
    sleep 2
    curl -s "http://localhost:$PORT/conversations/$sender/tracker" > "$WORK/$name.$i.tracker.json"
    tail -n +"$((before + 1))" "$WORK/$name.run.log" > "$WORK/$name.$i.turn.log"
    python3 - "$i" "$reply" "$WORK/$name.$i.tracker.json" "$WORK/$name.$i.turn.log" <<'PY2' | tee -a "$OUT"
import json, re, sys
i, reply, tracker, turn_log = sys.argv[1:5]
try:
    texts = [m.get("text", "") for m in json.loads(reply)]
except Exception:
    texts = [reply]
text = " / ".join(t.replace("\n", " ") for t in texts)
try:
    t = json.load(open(tracker))
except Exception:
    t = {"events": [], "slots": {}}
flows = [e["flow_id"] for e in t["events"] if e["event"] == "flow_started"]
tools = [e["tool_name"] for e in t["events"] if e["event"] == "mcp_tool_executed"]
folder = (t.get("slots") or {}).get("project.folder_path")
# Every LLM call this turn: what came back (text / tool calls) or the error,
# whatever its type, so a provider failure can't pass for engine behaviour.
calls = []
for line in open(turn_log):
    if '"calm_v2.llm.response"' in line:
        m = re.search(r'"tool_names": (\[[^\]]*\])', line)
        calls.append("tools=" + (m.group(1) if m else "[]")
                     + (" +text" if '"has_text": true' in line else ""))
    elif '"calm_v2.orchestrator.llm_error"' in line:
        m = re.search(r"Original error: ([\w.]+)", line)
        c = re.search(r'\\"code\\":\\"(\w+)\\"', line)
        calls.append("ERROR " + (m.group(1).split(".")[-1] if m else "?")
                     + (f"({c.group(1)})" if c else ""))
print(f"try {i}: flows={flows} tools={tools} folder_path={folder!r}")
print(f"        llm calls: {calls or 'none logged'}")
print(f"        reply: {text[:160]!r}")
PY2
  done
}

section "Environment"
log "date (UTC):    $(date -u '+%Y-%m-%d %H:%M:%S')"
log "machine:       $(uname -sm)"
log "python:        $(python3 --version 2>&1)"
log "rasa-pro:      $(python3 -c 'import importlib.metadata as m; print(m.version("rasa-pro"))')"
log "git commit:    $(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo n/a)"
log "LLM provider:  $LLM_PROVIDER ($(grep -E '^  model:' "$SRC/integrations.yml" | head -1 | sed 's/  model: //') before set_llm_provider.py)"
log "message used:  \"$MESSAGE\" as the first message of a brand-new conversation"
log "NoteVs URL:    $NOTEVS_CALL_URL (unreachable on purpose — tool calls report an error, no real notes touched)"

# --- A: the project as committed (all fixes in place) ------------------------
section "Run A — project as committed (session-start override, inspector off, memory.yml present)"
A="$(make_copy as_committed)"
if ! train "$A" as_committed; then
  log "Training the project as committed failed — stopping here (see output above)."
  exit 1
fi
if start_server "$A" as_committed; then
  first_message as_committed
fi
stop_server

# --- Claim 2: inspector + REST in the same `rasa run` ------------------------
section "Claim 2 — inspector.enabled: true crashes rasa run (control: Run A above, inspector off)"
B="$(make_copy inspector_on)"
python3 - "$B/integrations.yml" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p).read()
s = re.sub(r"(\n  inspector:\n    enabled: )false", r"\1true", s)
open(p, "w").write(s)
PY
log "changed in this copy: channels.inspector.enabled: false -> $(grep -A1 '^  inspector:' "$B/integrations.yml" | tail -1 | sed 's/ *enabled: //')"
cp -R "$A/models" "$B/models" 2>/dev/null || train "$B" inspector_on
if start_server "$B" inspector_on; then
  log "RESULT: server stayed up with inspector enabled"
else
  log "RESULT: server did not stay up with inspector enabled"
fi
stop_server
log "--- log lines mentioning the bind / crash ---"
grep -iE "EADDRINUSE|address already in use|errno 48|errno 98|voice_channel|inspector|server is up and running|Traceback|Error" \
  "$WORK/inspector_on.run.log" | grep -v -i -e "api_key" -e "langfuse" | tail -25 | tee -a "$OUT"

# --- Claim 1: without the session-start override -----------------------------
section "Claim 1 — first message WITHOUT the session-start override (compare with Run A)"
C="$(make_copy no_override)"
rm -rf "$C/skills/default_session_start"
log "changed in this copy: removed skills/default_session_start/ (engine's built-in one is used)"
if train "$C" no_override && start_server "$C" no_override; then
  first_message no_override
fi
stop_server

# --- Claim 3: without memory.yml ---------------------------------------------
section "Claim 3 — WITHOUT memory.yml (Run A trains and sets project.folder_path)"
D="$(make_copy no_memory)"
rm -f "$D/memory.yml"
log "changed in this copy: removed memory.yml"
if train "$D" no_memory && start_server "$D" no_memory; then
  first_message no_memory
fi
stop_server

section "Done"
log "Evidence written to: evidence.txt (full logs, secrets redacted, in retest-logs/ — git-ignored)"
