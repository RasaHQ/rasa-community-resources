"""Fetch pinned community corpora and the writing-for-agents skill."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from rasa_skill_eval import PROJECT_ROOT
from rasa_skill_eval.config import AppConfig, CorpusEntry


def _run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a git command and raise if it fails."""
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip() or proc.stdout}"
        )
    return proc


def _rmtree(path: Path) -> None:
    """Remove a directory tree, clearing read-only bits left by git on Windows."""
    if not path.exists():
        return

    def _clear_and_retry(func: Any, target: str, exc: BaseException) -> None:
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear_and_retry)
    else:
        shutil.rmtree(
            path,
            onerror=lambda func, target, _err: _clear_and_retry(func, target, _err[1]),
        )


def _write_pin(pins_dir: Path, name: str, repo: str, sha: str, dest: str) -> None:
    """Record the fetched commit for a corpus name."""
    pins_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    (pins_dir / f"{name}.sha").write_text(
        f"name: {name}\nrepo: {repo}\ncommit: {sha}\ndest: {dest}\nfetched_at: {stamp}\n",
        encoding="utf-8",
    )


def fetch_entry(entry: CorpusEntry, dest: Path, work_root: Path) -> str:
    """Sparse-clone ``entry.repo`` and copy ``sparse_path`` to ``dest``. Return SHA."""
    work_root.mkdir(parents=True, exist_ok=True)
    clone_dir = work_root / "_clone"
    _rmtree(clone_dir)
    clone_args = ["clone", "--depth", "1", "--filter=blob:none"]
    if entry.sparse_path:
        clone_args.append("--sparse")
    clone_args.extend([entry.repo, str(clone_dir)])
    _run_git(clone_args)
    if entry.sparse_path:
        _run_git(["sparse-checkout", "set", entry.sparse_path], cwd=clone_dir)
    sha = _run_git(["rev-parse", "HEAD"], cwd=clone_dir).stdout.strip()
    source = clone_dir / entry.sparse_path if entry.sparse_path else clone_dir
    if not source.exists():
        raise FileNotFoundError(f"Sparse path missing after clone: {source}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _rmtree(dest)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(".git"))
    _rmtree(clone_dir)
    logger.info("Fetched {} @ {} -> {}", entry.repo, sha[:12], dest)
    return sha


def try_install_mantle_coding_skills(dest: Path) -> str | None:
    """Deprecated no-op. Coding-agent corpora are out of scope for this harness."""
    del dest
    return None


def fetch_all(config: AppConfig) -> dict[str, str]:
    """Fetch every corpus listed in config.yaml. Returns name -> SHA."""
    pins_dir = PROJECT_ROOT / "corpus" / "pins"
    work_root = PROJECT_ROOT / "corpus" / "_work"
    shas: dict[str, str] = {}
    for name, entry in config.corpora.items():
        dest = PROJECT_ROOT / entry.dest
        sha = fetch_entry(entry, dest, work_root / name)
        shas[name] = sha
        _write_pin(pins_dir, name, entry.repo, sha, entry.dest)
    # Project-local copy of the improver skill for Cursor.
    if "writing_for_agents" in config.corpora:
        improver_src = PROJECT_ROOT / config.corpora["writing_for_agents"].dest
        improver_dst = PROJECT_ROOT / config.paths.writing_for_agents_dir
        if improver_src.is_dir():
            improver_dst.parent.mkdir(parents=True, exist_ok=True)
            _rmtree(improver_dst)
            shutil.copytree(improver_src, improver_dst)
            logger.info("Vendored writing-for-agents to {}", improver_dst)
    unslop_src = PROJECT_ROOT / config.paths.unslop_dir
    unslop_dst = PROJECT_ROOT / ".cursor" / "skills" / "unslop"
    if unslop_src.is_dir():
        unslop_dst.parent.mkdir(parents=True, exist_ok=True)
        _rmtree(unslop_dst)
        shutil.copytree(unslop_src, unslop_dst)
        logger.info("Vendored unslop to {}", unslop_dst)
    _rmtree(work_root)
    return shas
