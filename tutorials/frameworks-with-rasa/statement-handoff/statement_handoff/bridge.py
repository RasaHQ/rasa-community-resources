"""Send only an application-selected run and input to the isolated worker."""
import asyncio
import json
import os
from pathlib import Path


async def call_worker(request):
    interpreter = os.environ.get("STATEMENT_WORKER_PYTHON")
    state_directory = os.environ.get("STATEMENT_STATE_DIR")
    if not interpreter or not Path(interpreter).is_file() or not state_directory:
        return {"error": "worker_not_configured"}
    # The worker has no model: do not pass licence, speech or LLM credentials.
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT") if key in os.environ}
    env["STATEMENT_STATE_DIR"] = state_directory
    process = None
    try:
        process = await asyncio.create_subprocess_exec(interpreter, "-B", "-m", "statement_worker.worker",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env)
        output, _ = await asyncio.wait_for(process.communicate(json.dumps(request).encode()), 10)
        if process.returncode or len(output) > 8192:
            return {"error": "worker_unavailable"}
        result = json.loads(output)
        return result if isinstance(result, dict) else {"error": "worker_invalid_result"}
    except asyncio.CancelledError:
        raise
    except Exception:
        return {"error": "worker_unavailable"}
    finally:
        if process and process.returncode is None:
            process.kill()  # Only the child created by this call.
            await process.wait()
