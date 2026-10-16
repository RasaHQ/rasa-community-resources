"""List native bindings and gate settings for a narrow, trusted Mantle project.

This uses the pinned SDK's loader. Loading a project executes its Python
imports; this module does not sandbox those imports or authorise tools.
"""
from pathlib import Path
import hashlib
import importlib.metadata
import inspect
import json


def source_file_for(function, root):
    try:
        name = inspect.getsourcefile(inspect.unwrap(function))
    except TypeError:
        name = None
    if name is None:
        raise ValueError("A loaded tool has no inspectable Python source file")
    source = Path(name).resolve()
    try:
        relative = source.relative_to(root)
    except ValueError:
        raise ValueError("A loaded tool is defined outside the project") from None
    return source, relative


def inventory(root):
    from rasa.mantle.skills.catalog import load_skill_catalog
    from rasa.mantle.skills.conditions import is_confirmation_gate_active
    from rasa.mantle.skills.skill import OrderedBlock, format_ordered_block_target_id
    from rasa.mantle.tools.loader import load_tools_for_skill_catalog
    from rasa.mantle.llm.tool_schemas import visible_custom_tool_names

    root = Path(root).resolve()
    version = importlib.metadata.version("rasa-pro")
    if version != "3.21.0.dev5":
        raise ValueError("This example requires the qualified 3.21.0.dev5 interfaces")

    catalog = load_skill_catalog(root)
    for skill in catalog.skills.values():
        if any(ref.startswith("mcp/") for ref in skill.import_tool_names):
            raise ValueError("MCP tools need a separate inventory adapter")
        if skill.is_default or skill.engine_managed:
            raise ValueError("Bundled engine skills are outside this fixture scope")
        if skill.precondition or skill.disabled or skill.hidden:
            raise ValueError("Routing conditions require explicit state coverage")

        all_gates = list(skill.tools)
        for block in skill.body:
            if isinstance(block, OrderedBlock):
                all_gates.extend(block.tools)
        if any(gate.requires is not None for gate in all_gates):
            raise ValueError("Memory-dependent availability requires explicit state coverage")

    bindings = load_tools_for_skill_catalog(catalog, root / "skills")
    rows = []
    unresolved = []
    for skill_id, skill in sorted(catalog.skills.items()):
        functions = bindings[skill_id]
        missing = catalog.declared_tool_names(skill_id) - set(functions)
        unresolved.extend(
            {"skill": skill_id, "tool": name} for name in sorted(missing)
        )
        targets = [""] + [
            format_ordered_block_target_id(skill_id, block.block_id)
            for block in skill.body
            if isinstance(block, OrderedBlock)
        ]
        for target in targets:
            gates = {
                gate.name: gate
                for gate in catalog.resolve_tool_gates(skill_id, target)
            }
            visible = visible_custom_tool_names(
                catalog, skill_id, target, functions, {}
            )
            for name, function in sorted(functions.items()):
                source, relative = source_file_for(function, root)
                engine_gate = catalog.effective_tool_gate(skill_id, target, name)
                model_gate = gates.get(name)
                rows.append({
                    "skill": skill_id,
                    "target": target or "(prose)",
                    "tool": name,
                    "source": relative.as_posix(),
                    "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "modelVisibleInEmptyMemory": name in visible,
                    "modelConfirmationSetting": is_confirmation_gate_active(
                        model_gate.requires_confirmation if model_gate else None
                    ),
                    "engineConfirmationSetting": is_confirmation_gate_active(
                        engine_gate.requires_confirmation if engine_gate else None
                    ),
                })
    return {
        "schema": 1,
        "rasaVersion": version,
        "rows": rows,
        "unresolved": unresolved,
    }


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def check(expected, actual):
    if actual["unresolved"]:
        raise ValueError("Inventory declares tools without loaded Python bindings")
    if canonical(expected) != canonical(actual):
        raise ValueError("Inventory differs from its reviewed snapshot")
