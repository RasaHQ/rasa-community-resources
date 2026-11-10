"""The no-network wrapper the protected checks run candidate code under.

A wrapper is trusted only after it is proven by behavior, never by its name. A timeout is never
counted as a block; only a refused or failed connection is:
  1. an unwrapped child CAN connect to a listener we hold (so the probe works),
  2. a wrapped child still runs Python and says so, and
  3. a wrapped child CANNOT connect to the same listener.
If no wrapper passes all three, `first_blocking()` returns None and every caller
must refuse to judge (NOT_READY, exit 2). A missing wrapper never means ACCEPT.

macOS uses sandbox-exec. Linux tries unshare (as root, then with a user
namespace, then through sudo with the privilege dropped again) and bubblewrap.
"""
import os
import shutil
import socket
import subprocess
import sys

PROFILE = "(version 1)(allow default)(deny network*)"
_QUIET = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "PYTHONDONTWRITEBYTECODE": "1"}
_ALIVE = "import sys\nprint('ISOLATION-RAN')\nsys.exit(0)\n"
_PROBE = ("import socket,sys\n"
          "try:\n socket.create_connection(('127.0.0.1',%d),timeout=2)\n"
          "except socket.timeout:\n print('ISOLATION-TIMEOUT'); sys.exit(2)\n"
          "except OSError:\n print('ISOLATION-BLOCKED'); sys.exit(0)\n"
          "print('ISOLATION-CONNECTED'); sys.exit(1)\n")


def candidates():
    """Wrappers worth trying, each a command prefix. None is trusted until `blocks()` passes."""
    found = []
    exec_mac = shutil.which("sandbox-exec")
    if exec_mac:
        found.append([exec_mac, "-p", PROFILE])
    if sys.platform.startswith("linux"):
        unshare = shutil.which("unshare")
        if unshare:
            found.append([unshare, "--net", "--"])
            found.append([unshare, "--user", "--map-root-user", "--net", "--"])
            sudo, setpriv = shutil.which("sudo"), shutil.which("setpriv")
            if sudo and setpriv:
                found.append([sudo, "-n", unshare, "--net", "--", setpriv, "--reuid", str(os.getuid()),
                              "--regid", str(os.getgid()), "--clear-groups", "env", "-i",
                              "PATH=/usr/bin:/bin", "HOME=/nonexistent", "PYTHONDONTWRITEBYTECODE=1"])
        bwrap = shutil.which("bwrap")
        if bwrap:
            found.append([bwrap, "--unshare-net", "--dev-bind", "/", "/"])
    return found


def blocks(prefix):
    """True only if `prefix` runs Python and stops it reaching a loopback listener we hold."""
    listener = socket.socket()
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        probe = _PROBE % listener.getsockname()[1]
        control = subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True, timeout=20, env=_QUIET)
        if control.returncode != 1 or "ISOLATION-CONNECTED" not in control.stdout:
            return False  # the probe cannot see a connection even with no wrapper, so it proves nothing
        # Drain the positive control before testing isolation. A connected socket left queued can fill the
        # listener backlog and make a pass-through wrapper time out, falsely appearing to enforce isolation.
        listener.settimeout(2)
        connection, _ = listener.accept()
        connection.close()
        alive = subprocess.run([*prefix, sys.executable, "-I", "-c", _ALIVE], capture_output=True, text=True, timeout=20, env=_QUIET)
        if alive.returncode != 0 or "ISOLATION-RAN" not in alive.stdout:
            return False  # the wrapper did not run Python, so it cannot have blocked anything
        wrapped = subprocess.run([*prefix, sys.executable, "-I", "-c", probe], capture_output=True, text=True, timeout=20, env=_QUIET)
        return wrapped.returncode == 0 and "ISOLATION-BLOCKED" in wrapped.stdout
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        listener.close()


def first_blocking():
    """The first proven wrapper as a command prefix, or None. Never returns an unproven wrapper."""
    for prefix in candidates():
        if blocks(prefix):
            return prefix
    return None
