"""Stage one independently reviewed A6 candidate; never apply or restart a service.

This is a fixed receiving contract for the recorded candidate below, not an
arbitrary Python plugin loader. Candidate tests are retained as opaque evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

SOURCE_HEAD = '587450680c17b3f64b21e123ae6ef45d4fee910a'
CANDIDATE_DIGEST = 'ee6fafca627dcb6a07a7f7def556c2887f3c73dcf667684d38b45316f15031c1'
TASK_SHA256 = '0c1a22a2560a750695b6e55830ce1fb2646fef4e85d8c2d56755a4a1cd7bfd99'
ACCEPTANCE_SHA256 = 'ca3d48216cd9ba4061b46a02dc0594e2f612ec27c6e946e99581bfbe68c7efd4'
CHILD_SHA256 = '277cfb159ee6ce8e71496e6ce74574f0a77303a160e09d9e8e5e3320b5b55c37'
MARKET_SHA256 = 'c3cabc1b5a9ddeadb522f3c45387e7d7afa960454c330e80b0b07422283172b4'
FILES = ('product/briefing/market_card.py', 'product/tests/test_market_card.py')
SCHEMA = 'rasa.factory-staging/v1'
EVIDENCE_FILES = ('native.json', 'console.json', 'verification/decision.json', 'task/a6-market-watchlist.json')
EVIDENCE_BASIS = 'self_attested_records_not_authenticated'


class ReceiverRefused(ValueError):
    """A coded refusal; no raw source data or filesystem exception text."""


def _read(root_fd, relative):
    descriptor = os.dup(root_fd)
    try:
        parts = relative.split('/')
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        with os.fdopen(file_fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ReceiverRefused('regular_unlinked_evidence_required')
            data = stream.read(65537)
        if len(data) > 65536:
            raise ReceiverRefused('evidence_size_limit')
        return data
    finally:
        os.close(descriptor)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiverRefused('duplicate_evidence_key')
        result[key] = value
    return result


def _decode(data):
    value = json.loads(data, object_pairs_hook=_unique)
    if not isinstance(value, dict):
        raise ReceiverRefused('evidence_object_required')
    return value


def _json(root_fd, relative):
    return _decode(_read(root_fd, relative))


def _files(root_fd, prefix):
    """Enumerate the closed candidate tree without following links or special files."""
    allowed_dirs = {prefix, prefix + '/product', prefix + '/product/briefing', prefix + '/product/tests'}
    found = set()
    if not stat.S_ISDIR(os.stat(prefix, dir_fd=root_fd, follow_symlinks=False).st_mode):
        raise ReceiverRefused('candidate_directory_required')
    for directory, folders, files, directory_fd in os.fwalk(prefix, dir_fd=root_fd, follow_symlinks=False):
        if directory not in allowed_dirs:
            raise ReceiverRefused('candidate_paths_mismatch')
        for name in folders:
            if (directory + '/' + name not in allowed_dirs or
                    not stat.S_ISDIR(os.stat(name, dir_fd=directory_fd, follow_symlinks=False).st_mode)):
                raise ReceiverRefused('candidate_paths_mismatch')
        for name in files:
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            relative = (Path(directory) / name).relative_to(prefix).as_posix()
            if relative not in FILES or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ReceiverRefused('candidate_paths_mismatch')
            found.add(relative)
    if found != set(FILES):
        raise ReceiverRefused('candidate_paths_mismatch')
    contents = {name: _read(root_fd, prefix + '/' + name) for name in FILES}
    digest = hashlib.sha256()
    for name in sorted(contents):
        digest.update(name.encode() + b'\0' + contents[name] + b'\0')
    if (digest.hexdigest() != CANDIDATE_DIGEST or
            hashlib.sha256(contents[FILES[0]]).hexdigest() != MARKET_SHA256):
        raise ReceiverRefused('accepted_candidate_mismatch')
    return contents


def stage_accepted_run(run_directory, new_receiving_directory, *, source_head, target_head):
    """Copy reviewed bytes into NEW evidence, binding explicit owner-supplied heads.

    source_head is the required owner-declared acquisition driver revision;
    it predates this receiving hook and is not observed from a running process.
    target_head is likewise the owner's declared receiving source revision.
    Evidence hashes identify the parsed bytes, not their authenticated origin.
    The original run is opened read-only. Nothing claims APPLIED_RESTARTED.
    """
    if source_head != SOURCE_HEAD or not isinstance(target_head, str) or not re.fullmatch(r'[0-9a-f]{40}', target_head):
        raise ReceiverRefused('source_or_target_head_invalid')
    source = Path(run_directory)
    target = Path(new_receiving_directory)
    if (target.exists() or target.is_symlink() or source.is_symlink() or
            target.resolve().is_relative_to(source.resolve())):
        raise ReceiverRefused('new_separate_receiving_directory_required')
    try:
        root_fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            evidence = {name: _read(root_fd, name) for name in EVIDENCE_FILES}
            native = _decode(evidence['native.json'])
            console = _decode(evidence['console.json'])
            decision = _decode(evidence['verification/decision.json'])
            task = evidence['task/a6-market-watchlist.json']
            if (native.get('status') != 'completed' or native.get('ok') is not True or
                    console.get('mode') != 'LIVE_NATIVE' or console.get('state') != 'ACCEPT'):
                raise ReceiverRefused('completed_native_accept_required')
            if (hashlib.sha256(task).hexdigest() != TASK_SHA256 or console.get('task_sha256') != TASK_SHA256 or
                    decision.get('task') != 'A6-market-watchlist' or decision.get('decision') != 'ACCEPT' or
                    decision.get('candidate_digest') != CANDIDATE_DIGEST or
                    decision.get('acceptance_sha256') != ACCEPTANCE_SHA256 or
                    decision.get('support_sha256') != {'a6_child.py': CHILD_SHA256} or
                    decision.get('files_supplied') != list(FILES)):
                raise ReceiverRefused('protected_task_or_decision_mismatch')
            checks = decision.get('checks')
            protected = [c for c in checks if isinstance(c, dict) and c.get('name') == 'protected acceptance'] if isinstance(checks, list) else []
            if len(protected) != 1 or protected[0].get('passed') is not True:
                raise ReceiverRefused('protected_acceptance_required')
            contents = _files(root_fd, 'candidate')
        finally:
            os.close(root_fd)
        receipt = {'schema': SCHEMA, 'status': 'STAGED', 'source_head': source_head,
                   'target_head': target_head, 'task_sha256': TASK_SHA256,
                   'candidate_digest': CANDIDATE_DIGEST,
                   'evidence_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in evidence.items()},
                   'evidence_basis': EVIDENCE_BASIS,
                   'files': {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()},
                   'product_acceptance': 'NOT_RUN'}
        target.mkdir(mode=0o700)
        for name, data in contents.items():
            path = target / 'candidate' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as output:
                output.write(data)
        with (target / 'staging.json').open('x') as output:
            output.write(json.dumps(receipt, indent=2) + '\n')
        return receipt
    except ReceiverRefused:
        raise
    except (OSError, ValueError, TypeError, RecursionError):
        raise ReceiverRefused('staging_evidence_unavailable') from None


def make_receiver_hook(new_receiving_directory, *, source_head, target_head):
    """Trusted driver callback; staging alone deliberately remains NOT_RECORDED."""
    new_receiving_directory = Path(new_receiving_directory).absolute()
    reference = str(new_receiving_directory / 'staging.json')
    if re.fullmatch(r'[A-Za-z0-9_./:@+ -]{1,512}', reference) is None:
        raise ReceiverRefused('integration_receipt_reference_invalid')
    def receive(run_directory):
        stage_accepted_run(run_directory, new_receiving_directory,
                           source_head=source_head, target_head=target_head)
        return {'schema': 'rasa.factory-integration/v1', 'status': 'NOT_RECORDED',
                'candidate_digest': CANDIDATE_DIGEST, 'baseline_head': None,
                'integrated_head': None, 'receipt_ref': reference,
                'reason_code': 'candidate_staged'}
    return receive


def load_accepted_market(receiving_directory):
    """Load only fixed, independently reviewed bytes; never execute candidate tests."""
    try:
        root_fd = os.open(receiving_directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            receipt = _json(root_fd, 'staging.json')
            contents = _files(root_fd, 'candidate')
        finally:
            os.close(root_fd)
        expected_files = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
        hashes = receipt.get('evidence_sha256')
        if (set(receipt) != {'schema', 'status', 'source_head', 'target_head', 'task_sha256',
                             'candidate_digest', 'files', 'product_acceptance', 'evidence_sha256', 'evidence_basis'} or
                receipt.get('schema') != SCHEMA or receipt.get('status') != 'STAGED' or
                receipt.get('source_head') != SOURCE_HEAD or receipt.get('task_sha256') != TASK_SHA256 or
                receipt.get('candidate_digest') != CANDIDATE_DIGEST or receipt.get('files') != expected_files or
                receipt.get('evidence_basis') != EVIDENCE_BASIS or
                not isinstance(hashes, dict) or set(hashes) != set(EVIDENCE_FILES) or
                hashes.get('task/a6-market-watchlist.json') != TASK_SHA256 or
                any(not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None
                    for value in hashes.values()) or
                not isinstance(receipt.get('target_head'), str) or
                not re.fullmatch(r'[0-9a-f]{40}', receipt['target_head']) or
                receipt.get('product_acceptance') != 'NOT_RUN'):
            raise ReceiverRefused('staging_receipt_mismatch')
        namespace = {'__name__': 'reviewed_factory_market'}
        # Hash and execute the SAME bytes: no second import/path lookup race.
        exec(compile(contents[FILES[0]], 'reviewed-factory-market', 'exec'), namespace)
        return namespace['market_card']
    except ReceiverRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise ReceiverRefused('staged_market_unavailable') from None
