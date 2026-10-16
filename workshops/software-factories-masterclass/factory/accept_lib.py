"""Helpers the protected acceptance suites share. Runs against the REAL Mantle engine, offline.

Nothing here calls a model, a license server or the network. It imports the engine's own skill compiler,
its project validation and its agent-config parser, so a check is a statement about what Mantle will load.
The factory copies this file next to the acceptance suite, outside the candidate's reach.
"""
import ast
import logging
import os
from pathlib import Path

import structlog
import yaml

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))

from rasa.mantle.config.agent_spec import agent_spec_from_config  # noqa: E402
from rasa.mantle.skills.markdown_skill_compiler import compile_markdown_skill  # noqa: E402
from rasa.mantle.validation import collect_project_findings  # noqa: E402

PROJECT = Path(os.environ["MANTLE_PROJECT"])


def findings():
    """Everything the engine's own authoring checks object to. Empty means Mantle would load it."""
    return [(f.code, f.message) for f in collect_project_findings(PROJECT)]


def skill(skill_id):
    return compile_markdown_skill(PROJECT / "skills" / skill_id / "skill.md")


def skill_text(skill_id):
    return (PROJECT / "skills" / skill_id / "skill.md").read_text()


def gate(skill_id, tool_name):
    """The compiled confirmation gate for one tool, or None when the engine compiled it away."""
    for tool in skill(skill_id).tools:
        if tool.name == tool_name:
            return tool.requires_confirmation
    return None


def declared_tools(skill_id):
    """Functions in the skill's tools.py that carry the @tool decorator, with their parameter names."""
    tree = ast.parse((PROJECT / "skills" / skill_id / "tools.py").read_text())
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and any("tool" in ast.unparse(d) for d in node.decorator_list):
            found[node.name] = [a.arg for a in node.args.args]
    return found


def agent_rules():
    """The rules Mantle will actually put in the prompt, parsed by its own agent-config reader."""
    return list(agent_spec_from_config(yaml.safe_load((PROJECT / "agent.yml").read_text())).rules)


def persona():
    return agent_spec_from_config(yaml.safe_load((PROJECT / "agent.yml").read_text())).persona
