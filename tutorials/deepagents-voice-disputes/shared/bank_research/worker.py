"""JSON stdin/stdout boundary; runtime diagnostics belong on stderr."""
import asyncio
import json
import sys
from bank_research.researcher import investigate

if __name__ == "__main__":
    raw = sys.stdin.buffer.read(16385)
    if len(raw) > 16384:
        raise SystemExit("Case snapshot too large")
    evidence = json.loads(raw)
    print(json.dumps(asyncio.run(investigate(evidence))))
