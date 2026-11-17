"""Retain an owned child's bounded transcript through shutdown timeout."""
import asyncio
import os
from pathlib import Path
import signal
import tempfile


async def require_process_exit(command, *, cwd, marker='AGENT_CLOSE_COMPLETE', ready_seconds=60, exit_seconds=5):
    with tempfile.TemporaryDirectory() as directory:
        log = Path(directory) / 'child.log'
        with log.open('wb') as output:
            child = await asyncio.create_subprocess_exec(*command, cwd=cwd,
                stdout=output, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
            def transcript():
                with log.open('rb') as stream:
                    body = stream.read(1024 * 1024 + 1)
                if len(body) > 1024 * 1024:
                    raise AssertionError('Child transcript exceeded its bound')
                return body.decode(errors='replace')
            failure = None
            try:
                async with asyncio.timeout(ready_seconds):
                    while marker not in transcript().splitlines():
                        if child.returncode is not None:
                            raise AssertionError('Child exited before close marker: ' + transcript())
                        await asyncio.sleep(0.05)
                try:
                    async with asyncio.timeout(exit_seconds):
                        await child.wait()
                except TimeoutError:
                    failure = 'Child did not exit within the bound after close. '
            except TimeoutError:
                failure = 'Child did not reach the close marker within the bound. '
            finally:
                if child.returncode is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    await child.wait()
            # Read AFTER cleanup as well: a timeout cannot discard a pending
            # pipe read or the child's last faulthandler diagnostic.
            text = transcript()
            if failure is not None:
                raise AssertionError(failure + text)
            return child.returncode, text
