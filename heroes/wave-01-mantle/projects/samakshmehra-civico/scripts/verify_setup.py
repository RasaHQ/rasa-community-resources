#!/usr/bin/env python3
"""Pre-flight check. Everything that can be wrong before the first call."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
problems: list[str] = []


def check(label: str, ok: bool, detail: str = "", fatal: bool = True) -> bool:
    mark = f"{GREEN}✓{RESET}" if ok else (f"{RED}✗{RESET}" if fatal else f"{YELLOW}!{RESET}")
    print(f"  {mark} {label}" + (f"  {detail}" if detail else ""))
    if not ok and fatal:
        problems.append(label)
    return ok


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    print("\nKeys")
    for var, why in [("RASA_LICENSE", "Rasa Pro licence"),
                     ("OPENAI_API_KEY", "routing + conversation"),
                     ("DEEPGRAM_API_KEY", "speech in and out")]:
        value = os.getenv(var, "")
        check(f"{var:18} ({why})", bool(value.strip()),
              "" if value.strip() else "not set in .env")

    print("\nProject files")
    for name in ["agent.yml", "memory.yml", "integrations.yml", "endpoints.yml",
                 "responses.yml"]:
        check(name, (ROOT / name).exists())

    print("\nSkills")
    skills = sorted(p.parent.name for p in ROOT.glob("skills/*/skill.md"))
    check(f"{len(skills)} skills found", len(skills) >= 8, ", ".join(skills))

    print("\nDemo data")
    for name in ["wards.json", "routing.json", "escalation.json",
                 "citizens.json", "complaints.json"]:
        path = ROOT / "data" / name
        ok = path.exists()
        if ok:
            try:
                json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                ok, name = False, f"{name} — {exc}"
        check(name, ok)

    print("\nWard lookup")
    try:
        from lib import directory
        for spoken, expected in [("Vaishali", "Vaishali"),
                                 ("Vishali two zero one zero one two", "Vaishali"),
                                 ("indrapuram", "Indirapuram"),
                                 ("201005", "Sahibabad / Shalimar Garden / Rajendra Nagar")]:
            matches = directory.find_ward(spoken)["matches"]
            got = matches[0]["label"] if matches else "(nothing)"
            check(f'"{spoken}"', got == expected, f"→ {got}")
        check('"outside our lane" finds nothing',
              directory.find_ward("outside our lane")["matches"] == [])
    except Exception as exc:  # noqa: BLE001
        check("directory loads", False, str(exc))

    print("\nComplaint store")
    try:
        from lib import store
        store.connect()
        overdue = [c for c in store.complaints_for_phone("9876543210") if c["is_overdue"]]
        ontime = [c for c in store.complaints_for_phone("9876543210")
                  if c["is_open"] and not c["is_overdue"]]
        check("database seeds", True, str(store.db_path().name))
        check("an overdue complaint exists (escalation demo)", bool(overdue),
              overdue[0]["complaint_id"] if overdue else "")
        check("an on-time complaint exists", bool(ontime),
              ontime[0]["complaint_id"] if ontime else "")
    except Exception as exc:  # noqa: BLE001
        check("store loads", False, str(exc))

    print("\nModel")
    models = sorted((ROOT / "models").glob("*.tar.gz")) if (ROOT / "models").exists() else []
    check("a trained model exists", bool(models),
          models[-1].name if models else "run: make train", fatal=False)

    if problems:
        print(f"\n{RED}✗ {len(problems)} problem(s):{RESET}")
        for p in problems:
            print(f"    {p}")
        print()
        return 1
    print(f"\n{GREEN}✓ all checks passed{RESET}  —  next: make train && make inspect\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
