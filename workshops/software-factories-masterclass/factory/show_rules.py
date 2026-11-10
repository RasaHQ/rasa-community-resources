#!/usr/bin/env python3
"""Show which rules Mantle will actually use from a candidate's agent.yml, next to what the engine objects to.

    python show_rules.py candidates/rule-digits-nested
"""
import logging
import shutil
import sys
import tempfile
from pathlib import Path

import structlog
import yaml

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
from rasa.mantle.config.agent_spec import agent_spec_from_config  # noqa: E402
from rasa.mantle.validation import collect_project_findings  # noqa: E402

ROOT = Path(__file__).resolve().parent


def main(candidate):
    candidate = Path(candidate)
    with tempfile.TemporaryDirectory(prefix="show-rules-") as scratch:
        project = Path(scratch) / "product"
        shutil.copytree(ROOT / "product", project)
        (project / "skills").mkdir(exist_ok=True)
        for path in sorted(p for p in candidate.rglob("*") if p.is_file()):
            target = Path(scratch) / path.relative_to(candidate)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        print("engine findings: %d" % len(collect_project_findings(project)))
        rules = list(agent_spec_from_config(yaml.safe_load((project / "agent.yml").read_text())).rules)
        print("rules Mantle will use: %s" % (rules if rules else "none"))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
