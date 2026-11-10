#!/bin/sh
# Run Claude Code through the Mantle factory: 3 tasks x ROUNDS rounds, one attempt each, nothing edited by hand.
# Needs: uv, claude (signed in), network for the first uv sync. Run it in a plain terminal, NOT inside another Claude Code session.
# usage: sh run_claude_experiment.sh /path/to/mantle-factory.zip [ROUNDS=3]
# Output: <workdir>/mantle-factory/runs/<agent>-<task>-<n>/{decision.json,meta.json}, and a summary at the end.
set -u
ZIP=$1; ROUNDS=${2:-3}
WORK=${WORKDIR:-$(mktemp -d)}
echo "workdir: $WORK"
cd "$WORK" && unzip -q "$ZIP" && cd mantle-factory || exit 2
uv sync --frozen || exit 2
VENV=$PWD/.venv/bin
CLAUDE_VERSION=$(claude --version 2>&1 | head -1)
mkdir -p cand review
n=1
while [ $n -le $ROUNDS ]; do
  for T in a1-block-card a2-rule-digits a3-rule-confirm; do
    TASK=tasks/$T.json; NAME=claude-$T-$n
    TID=$($VENV/python -c "import json;print(json.load(open('$TASK'))['id'])")
    $VENV/python scratch.py $TASK work/$NAME >/dev/null || exit 2
    START=$(date +%s)
    ( cd work/$NAME && PATH=$VENV:$PATH claude -p "Read tasks/$TID.json and carry out the request. Follow CLAUDE.md." \
        --permission-mode acceptEdits --allowedTools Read Edit Write "Bash(python validate.py)" \
        </dev/null > ../$NAME.final.txt 2> ../$NAME.err.txt )
    RC=$?; END=$(date +%s)
    $VENV/python collect.py work/$NAME cand/$NAME review/$NAME --claim work/$NAME.final.txt > work/$NAME.collect.txt 2>&1
    if [ -d cand/$NAME ]; then $VENV/python factory.py $TASK cand/$NAME runs/$NAME > work/$NAME.factory.txt 2>&1
    else mkdir -p runs/$NAME; echo "agent made no change" > work/$NAME.factory.txt; fi
    printf '{"agent": "claude-code %s", "seconds": %s, "agent_exit": %s}\n' "$CLAUDE_VERSION" $((END-START)) $RC > runs/$NAME/meta.json
    echo "$NAME exit=$RC secs=$((END-START)) :: $(cat work/$NAME.factory.txt)"
  done
  n=$((n+1))
done
echo "--- report"; $VENV/python measure.py report runs
echo "Send back: the whole runs/ and review/ folders, and work/*.final.txt, work/*.err.txt."
