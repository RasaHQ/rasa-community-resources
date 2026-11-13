# SPDX-License-Identifier: MIT
"""Local stopped-fixture initialization/reset. Never imported as a model tool."""
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from demo_data import MAX_SEED,REFERENCE_SEED
from journal import Journal
from mock_server import FixtureState

INSTANCE='fictional-symitar-v1'


def _sync(folder):
    fd=os.open(folder,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def _write_new(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(data,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    _sync(path.parent)


def _activate(root,name,audit=None,seed=REFERENCE_SEED):
    directory=root/name;directory.mkdir(mode=0o700)
    with Journal(directory/'journal',INSTANCE,initialize=True) as journal:
        # The demo data seed is chosen here, once per fictional exercise, and
        # stored with the mock state; the manifest keeps a copy for start-up.
        state=FixtureState(directory/'mock.sqlite3',journal.epoch,initialize=True,seed=seed)
        state.close()
        record={'mode':'fictional','instance':INSTANCE,'directory':name,'epoch':journal.epoch,'audit':audit,'seed':seed}
    temporary=root/('current-'+uuid.uuid4().hex+'.json')
    _write_new(temporary,record)
    os.replace(temporary,root/'current.json');_sync(root)
    return record


def current(root,*,initialize=False,seed=REFERENCE_SEED):
    root=Path(root).absolute()
    if root!=root.resolve():raise ValueError('unsafe_fixture_path')
    if not root.exists():
        if not initialize:raise ValueError('fixture_missing')
        root.mkdir(mode=0o700);_sync(root.parent)
        return _activate(root,uuid.uuid4().hex,seed=seed)
    path=root/'current.json'
    if path.is_symlink():raise ValueError('unsafe_fixture_manifest')
    record=json.loads(path.read_text())
    if record.get('mode')!='fictional' or record.get('instance')!=INSTANCE or not re.fullmatch('[0-9a-f]{32}',record.get('directory','')):
        raise ValueError('invalid_fixture_manifest')
    # Manifests from before seeds existed are the reference data (seed 0).
    stored=record.setdefault('seed',REFERENCE_SEED)
    if type(stored) is not int or not 0<=stored<=MAX_SEED:raise ValueError('invalid_fixture_manifest')
    directory=root/record['directory']
    if directory!=directory.resolve():raise ValueError('unsafe_fixture_directory')
    return record


def reset(root,*,acknowledge,reason,seed=REFERENCE_SEED):
    if acknowledge is not True or not isinstance(reason,str) or not 1<=len(reason.strip())<=256 or any(ord(c)<32 for c in reason):
        raise ValueError('acknowledgement_and_reason_required')
    root=Path(root).absolute();record=current(root)
    directory=root/record['directory'];locks=[]
    try:
        # Same lock order as startup; do not open SQLite or recover/mutate old
        # bytes before recording hashes. A live host or mock refuses the reset.
        for path in (directory/'journal/writer.lock',directory/'mock.sqlite3.lease'):
            fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW);locks.append(fd)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        originals={}
        for path in (directory/'journal/journal.sqlite3',directory/'mock.sqlite3',root/'current.json'):
            if path.is_symlink() or not path.is_file():raise ValueError('original_fixture_bytes_required')
            originals[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
        name=uuid.uuid4().hex;audit_name='reset-'+name+'.json'
        _write_new(root/audit_name,{'action':'begin_new_fictional_epoch','at':datetime.now(timezone.utc).isoformat(),
            'operator_uid':os.getuid(),'reason':reason.strip(),'old_directory':record['directory'],
            'old_epoch':record['epoch'],'new_directory':name,'original_sha256':originals,
            'old_seed':record['seed'],'new_seed':seed})
        # The old databases/epochs remain in place. This is not reconciliation,
        # clearing a hold in place, or permission to resend an old operation.
        return _activate(root,name,audit_name,seed)
    finally:
        for fd in reversed(locks):os.close(fd)
