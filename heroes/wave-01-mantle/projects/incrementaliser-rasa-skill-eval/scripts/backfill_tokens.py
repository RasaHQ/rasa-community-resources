"""Backfill tokens in tsr runs and results.json using conversational token estimation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rasa_skill_eval.finalize import finalize_report
from rasa_skill_eval.tracker_parse import estimate_conversational_tokens


def backfill_tokens_in_run(run_dir: Path) -> int:
    """Populate tokens from transcripts for all non-skipped TSR runs where tokens is null."""
    results_path = run_dir / "results.json"
    if not results_path.is_file():
        return 0
    payload: dict[str, Any] = json.loads(results_path.read_text(encoding="utf-8"))
    tsr_rows: list[dict[str, Any]] = payload.get("tsr") or []
    updated_count = 0

    for row in tsr_rows:
        if row.get("tokens") is not None:
            continue
        if row.get("skipped"):
            continue
        agent_id = str(row.get("agent_id") or "")
        model_id = str(row.get("model_id") or "")
        arm = str(row.get("arm") or "")
        scenario_id = str(row.get("scenario_id") or "")
        repeat = row.get("repeat", 0)

        transcript_path = (
            run_dir
            / "tsr"
            / "transcripts"
            / agent_id
            / model_id
            / arm
            / f"{scenario_id}__r{repeat}.json"
        )
        if transcript_path.is_file():
            try:
                tdata = json.loads(transcript_path.read_text(encoding="utf-8"))
                inp = str(tdata.get("input") or "")
                out = str(tdata.get("output") or "")
                tok = estimate_conversational_tokens([inp], [out])
                if tok > 0:
                    row["tokens"] = tok
                    updated_count += 1
            except Exception:
                pass

    if updated_count > 0:
        results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # Also update per-arm tsr files
        for agent_dir in (run_dir / "tsr").iterdir():
            if not agent_dir.is_dir() or agent_dir.name in {"transcripts", "observations"}:
                continue
            for model_dir in agent_dir.iterdir():
                if not model_dir.is_dir():
                    continue
                for arm_file in model_dir.glob("*.json"):
                    try:
                        arm_rows = json.loads(arm_file.read_text(encoding="utf-8"))
                        if isinstance(arm_rows, list):
                            for r in arm_rows:
                                if r.get("tokens") is None and not r.get("skipped"):
                                    sc_id = str(r.get("scenario_id") or "")
                                    rep = r.get("repeat", 0)
                                    tp = (
                                        run_dir
                                        / "tsr"
                                        / "transcripts"
                                        / agent_dir.name
                                        / model_dir.name
                                        / arm_file.stem
                                        / f"{sc_id}__r{rep}.json"
                                    )
                                    if tp.is_file():
                                        td = json.loads(tp.read_text(encoding="utf-8"))
                                        tok = estimate_conversational_tokens(
                                            [str(td.get("input") or "")],
                                            [str(td.get("output") or "")],
                                        )
                                        if tok > 0:
                                            r["tokens"] = tok
                            arm_file.write_text(json.dumps(arm_rows, indent=2), encoding="utf-8")
                    except Exception:
                        pass

    return updated_count


def main() -> None:
    """Run token backfill on heroes_eval_20260911_221805 and re-finalize report."""
    run_dir = Path("runs/heroes_eval_20260911_221805")
    updated = backfill_tokens_in_run(run_dir)
    print(f"Backfilled tokens for {updated} TSR rows.")
    finalize_report(run_dir)
    print("Report finalized successfully.")


if __name__ == "__main__":
    main()
