"""Private, persistent state for the local example."""
import os
from pathlib import Path
import sqlite3
import stat


def open_state(path: Path):
    path = path.absolute()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = path.parent.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.getuid()
            or stat.S_IMODE(directory.st_mode) & 0o077):
        raise PermissionError("Use a private state directory")
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(descriptor)
    info = path.stat(follow_symlinks=False)
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise PermissionError("Use a private regular state file")
    database = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=2)
    database.execute("PRAGMA synchronous=FULL")
    return database
