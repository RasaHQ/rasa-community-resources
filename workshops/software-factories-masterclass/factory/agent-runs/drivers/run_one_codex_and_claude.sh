#!/bin/sh
# usage: run_one.sh <agent: claude|codex> <task-file> <n>
cd /Volumes/ZeoWork/rasa-ops/mantle/agent-runs/mf || exit 2
VENV=/Volumes/ZeoWork/rasa-ops/mantle/venv/bin
AGENT=$1; TASK=$2; N=$3
T=$(basename $TASK .json); NAME=$AGENT-$T-$N
TID=$($VENV/python -c "import json;print(json.load(open('$TASK'))['id'])")
$VENV/python scratch.py $TASK work/$NAME >/dev/null || exit 2
START=$(date +%s)
cd work/$NAME
export PATH=$VENV:$PATH
# (the original line here was a no-op loop over OPENAI_API_KEY and RASA_LICENSE; removed. No key variable was set in the shell:
# each agent used its own stored sign-in, and the factory strips the environment of its child processes anyway.)
if [ "$AGENT" = claude ]; then
  claude -p "Read tasks/$TID.json and carry out the request. Follow CLAUDE.md." --permission-mode acceptEdits --allowedTools Read Edit Write "Bash(python validate.py)" </dev/null > ../$NAME.final.txt 2> ../$NAME.err.txt
else
  codex exec --sandbox workspace-write --skip-git-repo-check "Read tasks/$TID.json and carry out the request. Follow AGENTS.md." > ../$NAME.final.txt 2> ../$NAME.err.txt
fi
RC=$?
END=$(date +%s)
cd ../..
echo "{\"agent\": \"$AGENT\", \"seconds\": $((END-START)), \"agent_exit\": $RC}" > work/$NAME.meta.json
$VENV/python collect.py work/$NAME cand/$NAME review/$NAME --claim work/$NAME.final.txt > work/$NAME.collect.txt 2>&1
$VENV/python factory.py $TASK cand/$NAME runs/$NAME > work/$NAME.factory.txt 2>&1
echo "$NAME exit=$RC secs=$((END-START)) :: $(cat work/$NAME.factory.txt)"
