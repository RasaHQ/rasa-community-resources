"""Run the separate pinned worker; no environment search or dependency install."""
import asyncio
import json
import os
from pathlib import Path


async def investigate(evidence):
    interpreter = os.environ.get("BANK_RESEARCH_PYTHON")
    if not interpreter or not Path(interpreter).is_file() or not os.environ.get("OPENAI_API_KEY"):
        return {"error": "research_not_configured"}
    process = None
    try:
        # Do not pass the Mantle licence, speech keys or customer environment.
        env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "SSL_CERT_FILE", "SSL_CERT_DIR", "OPENAI_API_KEY") if key in os.environ}
        process = await asyncio.create_subprocess_exec(interpreter, "-B", "-m", "bank_research.worker", stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env=env)
        stdout, _ = await asyncio.wait_for(process.communicate(json.dumps(evidence).encode()), timeout=22)
        if process.returncode or len(stdout) > 16384:
            return {"error": "research_unavailable"}
        result = json.loads(stdout)
        if result.get("status") != "research_complete" or not isinstance(result.get("evidence"), dict) or not result["evidence"]:
            return {"error": "research_unavailable"}
        if any(key not in evidence or value != evidence[key] for key, value in result["evidence"].items()):
            return {"error": "research_invalid_evidence"}
        return {"status": "research_complete", "evidence": result["evidence"], "next_step": "Offer staff review; no fraud or refund decision."}
    except asyncio.CancelledError:
        raise
    except Exception:
        return {"error": "research_unavailable"}
    finally:
        if process and process.returncode is None:
            process.kill()  # Only the child created by this invocation.
            await process.wait()
