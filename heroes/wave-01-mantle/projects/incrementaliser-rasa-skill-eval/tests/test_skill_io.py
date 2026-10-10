"""Skill markdown helpers must survive Windows locale encodings."""

from __future__ import annotations

from pathlib import Path

from rasa_skill_eval.skill_io import read_text_utf8, write_text_utf8


def test_read_text_utf8_accepts_cp1252_em_dash(tmp_path: Path) -> None:
    """Byte 0x97 is a CP1252 dash; SkillEvaluator-adjacent writes must not crash."""
    path = tmp_path / "SKILL.md"
    path.write_bytes(b"Help the user \x97 then stop.\n")
    text = read_text_utf8(path)
    assert "then stop" in text


def test_write_text_utf8_roundtrip(tmp_path: Path) -> None:
    """Em dashes stay UTF-8 on disk even when the Windows locale is CP1252."""
    path = tmp_path / "SKILL.md"
    write_text_utf8(path, "Help the user — then stop.\n")
    raw = path.read_bytes()
    assert raw == "Help the user — then stop.\n".encode()
    assert read_text_utf8(path) == "Help the user — then stop.\n"
