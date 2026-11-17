"""Describe the current local lock owner without storing credentials."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat

import fcntl
from pydantic import BaseModel, ConfigDict, Field


class Activity(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, hide_input_in_errors=True)
    kind: str = Field(pattern=r'^assistant$')
    configuration: str = Field(pattern=r'^[0-9a-f]{64}$')


def configuration_key(token, chat):
    return hashlib.sha256((token + '\0' + str(chat)).encode()).hexdigest()


def private_file(path, flags):
    descriptor = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    info = os.fstat(descriptor)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        os.close(descriptor)
        raise PermissionError('Use private local activity files')
    return descriptor


@contextmanager
def assistant_activity(directory, token, chat):
    """Called only after the launcher holds the shop lock; cleanup before unlock."""
    path = Path(directory) / 'activity.json'
    descriptor = private_file(path, os.O_WRONLY | os.O_CREAT)
    try:
        os.ftruncate(descriptor, 0)
        record = Activity(kind='assistant', configuration=configuration_key(token, chat))
        os.write(descriptor, record.model_dump_json().encode())
        os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor)
        path.unlink(missing_ok=True)


def clear_activity(directory):
    """Discovery owns the same lock and cannot leave a stale assistant label."""
    path = Path(directory) / 'activity.json'
    try:
        descriptor = private_file(path, os.O_RDONLY)
    except FileNotFoundError:
        return
    os.close(descriptor)
    path.unlink()


def local_activity(directory, token, chat):
    """Observe only existing private state; never create it or acquire ownership."""
    directory = Path(directory)
    try:
        info = directory.stat(follow_symlinks=False)
    except FileNotFoundError:
        return 'stopped'
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise PermissionError('Private state required')
    try:
        descriptor = private_file(directory / 'run.sqlite3', os.O_RDONLY)
    except FileNotFoundError:
        return 'stopped'
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            return 'stopped'
        try:
            owner = private_file(directory / 'activity.json', os.O_RDONLY)
        except FileNotFoundError:
            return 'unknown'
        try:
            record = Activity.model_validate_json(os.read(owner, 4097))
        finally:
            os.close(owner)
        # Recheck after reading: the assistant may have stopped in between.
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 'running' if record.configuration == configuration_key(token, chat) else 'different'
        else:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            return 'stopped'
    finally:
        os.close(descriptor)
