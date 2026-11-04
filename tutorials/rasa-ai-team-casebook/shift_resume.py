"""Crash after absence intake: compare whole-request replay with stage replay."""
import json
import sqlite3
import tempfile
from pathlib import Path


class Interrupted(Exception):
    pass


def connect(path):
    db = sqlite3.connect(path)
    db.execute('''CREATE TABLE IF NOT EXISTS intake (
      request_id TEXT PRIMARY KEY, employee TEXT NOT NULL, shift TEXT NOT NULL,
      replacement TEXT NOT NULL, qualified INTEGER NOT NULL,
      swap_state TEXT NOT NULL CHECK(swap_state IN ('pending','approved','denied')))''')
    db.commit()
    return db


def submit(path, request, employee, shift, replacement, qualified, *, resume, interrupt=False):
    if type(qualified) is not bool or not all(isinstance(x,str) and x for x in (request,employee,shift,replacement)):
        raise ValueError('Explicit fixture fields required')
    db = connect(path)
    try:
        # Serialize lookup/insert, retaining the optional-work obligation with intake.
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT employee,shift,replacement,qualified,swap_state FROM intake WHERE request_id=?',(request,)).fetchone()
        replay = row is not None
        if row and row[:4] != (employee,shift,replacement,int(qualified)):
            raise ValueError('Request identity belongs to different facts')
        if not row:
            db.execute('INSERT INTO intake VALUES (?,?,?,?,?,?)',
                       (request,employee,shift,replacement,int(qualified),'pending'))
        db.commit()
        if replay and not resume:
            # Conventional request deduplication prevents duplicate intake but strands work.
            return 'already_recorded'
        if interrupt:
            raise Interrupted('Intake committed; optional swap not attempted')
        with db:
            db.execute("UPDATE intake SET swap_state=? WHERE request_id=? AND swap_state='pending'",
                       ('approved' if qualified else 'denied',request))
        return db.execute('SELECT swap_state FROM intake WHERE request_id=?',(request,)).fetchone()[0]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def stored(path):
    db=connect(path)
    try:return db.execute('SELECT * FROM intake ORDER BY request_id').fetchall()
    finally:db.close()


def demo():
    result={}
    with tempfile.TemporaryDirectory() as directory:
        for resume in [False,True]:
            path=Path(directory)/('staged.db' if resume else 'request.db')
            args=(path,'a1','employee-1','night-1','employee-2',False)
            try:submit(*args,resume=resume,interrupt=True)
            except Interrupted:pass
            before=stored(path)
            response=submit(*args,resume=resume)
            result['stage_replay' if resume else 'request_replay']={
                'after_crash':before,'retry_response':response,'after_retry':stored(path)}
    return result


if __name__=='__main__':print(json.dumps(demo(),indent=2,sort_keys=True))
