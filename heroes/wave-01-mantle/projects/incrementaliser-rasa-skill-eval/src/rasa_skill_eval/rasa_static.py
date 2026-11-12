"""Native Mantle inventory and checks NVIDIA SkillEvaluator cannot score."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from rasa_skill_eval.models import (
    Finding,
    FindingClass,
    FindingSeverity,
    MantleInventory,
    ToolConstraintInfo,
)
from rasa_skill_eval.skill_io import MANTLE_EXTRA_KEYS, find_skill_file, split_frontmatter

IRREVERSIBLE_TOOLS: frozenset[str] = frozenset(
    {
        "block_card",
        "process_transfer",
        "schedule_transfer",
        "order_replacement_card",
        "remove_payee",
        "process_payment",
    }
)

IF_RE = re.compile(r"^if:\s*(.+)$", re.MULTILINE)
BLOCK_RE = re.compile(r":::ordered_block\s+id=([A-Za-z0-9_]+)")
SKILL_REF_RE = re.compile(r"@skill\.([A-Za-z0-9_]+)")
MEMORY_REF_RE = re.compile(r"@memory\.([A-Za-z0-9_.]+)")
SESSION_PROSE_RE = re.compile(r"(?<!`)\bsession\.[a-zA-Z0-9_.]+")
MEMORY_SET_RE = re.compile(r"""memory\.set\(\s*['"]([^'"]+)['"]""")
IDENTITY_TOOLS: frozenset[str] = frozenset(
    {"load_customer_profile", "get_customer_profile"}
)
ONE_QUESTION_RE = re.compile(r"one .{0,40}question", re.IGNORECASE)


def _parse_tool_constraints(raw: Any) -> list[ToolConstraintInfo]:
    """Normalize ``tool_constraints`` YAML into typed records."""
    items: list[ToolConstraintInfo] = []
    if not isinstance(raw, list):
        return items
    for entry in raw:
        if not isinstance(entry, dict) or len(entry) != 1:
            continue
        name, opts = next(iter(entry.items()))
        if not isinstance(opts, dict):
            opts = {}
        confirmation = opts.get("requires_confirmation") or {}
        enabled = False
        if isinstance(confirmation, dict):
            enabled = bool(confirmation.get("enabled"))
        elif confirmation is True:
            enabled = True
        items.append(
            ToolConstraintInfo(
                tool_name=str(name),
                requires=str(opts["requires"]) if opts.get("requires") is not None else None,
                requires_confirmation=enabled,
                on_success=str(opts["on_success"]) if opts.get("on_success") else None,
                on_failure=str(opts["on_failure"]) if opts.get("on_failure") else None,
            )
        )
    return items


def _import_tools(frontmatter: dict[str, Any]) -> list[str]:
    """Return imported project-root tool names."""
    raw = frontmatter.get("import_tools") or []
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw]


def parse_project_memory(memory_yml: Path) -> tuple[list[str], list[str]]:
    """Return field names and llm-settable field names from project memory.yml."""
    if not memory_yml.is_file():
        return [], []
    raw = yaml.safe_load(memory_yml.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return [], []
    fields: list[str] = []
    llm_settable: list[str] = []

    def walk(prefix: str, spec: Any) -> None:
        if not isinstance(spec, dict):
            return
        if "type" in spec:
            fields.append(prefix)
            if spec.get("llm_settable") is True:
                llm_settable.append(prefix)
            return
        for key, nested in spec.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            walk(name, nested)

    walk("", raw)
    return fields, llm_settable


def parse_agent_voice(agent_yml: Path) -> tuple[bool, bool]:
    """Return voice_enabled and one_question_rule from agent.yml."""
    if not agent_yml.is_file():
        return False, False
    raw = yaml.safe_load(agent_yml.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return False, False
    agent = raw.get("agent") if isinstance(raw.get("agent"), dict) else {}
    voice = agent.get("voice") if isinstance(agent.get("voice"), dict) else {}
    enabled = bool(voice.get("enabled"))
    persona = str(agent.get("persona") or "")
    rules = raw.get("rules") if isinstance(raw.get("rules"), list) else []
    blob = persona + "\n" + "\n".join(str(item) for item in rules)
    return enabled, bool(ONE_QUESTION_RE.search(blob))


def _memory_set_keys(skill_dir: Path) -> list[str]:
    """Collect memory.set(...) keys from skill-local Python tools."""
    keys: list[str] = []
    files: list[Path] = []
    if (skill_dir / "tools.py").is_file():
        files.append(skill_dir / "tools.py")
    tools_dir = skill_dir / "tools"
    if tools_dir.is_dir():
        files.extend(sorted(tools_dir.glob("*.py")))
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        keys.extend(MEMORY_SET_RE.findall(text))
    return keys


def inventory_skill(skill_dir: Path, project_root: Path | None = None) -> MantleInventory:
    """Parse a Mantle skill folder and run Mantle-only static checks."""
    skill_file = find_skill_file(skill_dir)
    if skill_file is None:
        raise FileNotFoundError(f"No skill.md in {skill_dir}")
    text = skill_file.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    skill_id = skill_dir.name
    display = str(frontmatter.get("name") or skill_id)
    description = str(frontmatter.get("description") or "").strip()
    extra = sorted(k for k in frontmatter if k in MANTLE_EXTRA_KEYS)
    constraints = _parse_tool_constraints(frontmatter.get("tool_constraints"))
    confirmed = {c.tool_name for c in constraints if c.requires_confirmation}
    irreversible_missing = sorted(
        name
        for name in IRREVERSIBLE_TOOLS
        if name in {c.tool_name for c in constraints} and name not in confirmed
    )
    import_tools = _import_tools(frontmatter)
    if_conditions = [m.strip() for m in IF_RE.findall(body)]
    ordered_ids = BLOCK_RE.findall(body)
    skill_refs = SKILL_REF_RE.findall(body)
    memory_refs = MEMORY_REF_RE.findall(body)
    project_fields: list[str] = []
    llm_settable: list[str] = []
    voice_enabled = False
    voice_one_question = False
    if project_root is not None:
        project_fields, llm_settable = parse_project_memory(project_root / "memory.yml")
        voice_enabled, voice_one_question = parse_agent_voice(project_root / "agent.yml")

    inv = MantleInventory(
        skill_id=skill_id,
        display_name=display,
        description=description,
        source_path=str(skill_dir),
        extra_frontmatter_keys=extra,
        import_tools=import_tools,
        tool_constraints=constraints,
        if_conditions=if_conditions,
        ordered_block_ids=ordered_ids,
        skill_refs=skill_refs,
        memory_refs=memory_refs,
        has_local_tools=(skill_dir / "tools.py").is_file()
        or (skill_dir / "tools").is_dir(),
        has_memory_yml=(skill_dir / "memory.yml").is_file(),
        has_responses_yml=(skill_dir / "responses.yml").is_file(),
        has_references=(skill_dir / "references").is_dir(),
        body_line_count=len(body.splitlines()),
        irreversible_without_confirmation=irreversible_missing,
        project_memory_fields=project_fields,
        llm_settable_project_fields=llm_settable,
        voice_enabled=voice_enabled,
        voice_one_question=voice_one_question,
        frontmatter=frontmatter,
        body=body,
    )
    inv.findings = _findings(inv, project_root)
    return inv


def _findings(inv: MantleInventory, project_root: Path | None) -> list[Finding]:
    """Build Mantle-native findings for one skill."""
    out: list[Finding] = []
    sid = inv.skill_id

    def add(
        code: str,
        message: str,
        severity: FindingSeverity,
        finding_class: FindingClass,
    ) -> None:
        out.append(
            Finding(
                code=code,
                message=message,
                severity=severity,
                finding_class=finding_class,
                skill_id=sid,
            )
        )

    if not inv.description:
        add(
            "description.missing",
            "Skill has no description; Mantle routes on this field.",
            FindingSeverity.HIGH,
            FindingClass.PORTABLE_AUTHORING,
        )
    lower_desc = inv.description.lower()
    if inv.description and "when" not in lower_desc and "activate" not in lower_desc:
        add(
            "description.triggers",
            "Description does not say when to activate. "
            "NVIDIA discoverability uses this field too.",
            FindingSeverity.LOW,
            FindingClass.PORTABLE_AUTHORING,
        )

    for tool_name in inv.irreversible_without_confirmation:
        add(
            "confirmation.missing",
            f"Irreversible tool {tool_name} has no requires_confirmation.",
            FindingSeverity.HIGH,
            FindingClass.MANTLE_ONLY,
        )

    if project_root is not None:
        tools_dir = project_root / "tools"
        skill_dir = Path(inv.source_path)
        haystacks: list[Path] = []
        if tools_dir.is_dir():
            haystacks.extend(sorted(tools_dir.glob("*.py")))
        if (skill_dir / "tools.py").is_file():
            haystacks.append(skill_dir / "tools.py")
        local_tools = skill_dir / "tools"
        if local_tools.is_dir():
            haystacks.extend(sorted(local_tools.glob("*.py")))
        for name in inv.import_tools:
            if name.startswith("mcp/"):
                continue
            declared = any(
                name in path.read_text(encoding="utf-8", errors="ignore")
                for path in haystacks
            )
            if haystacks and not declared:
                add(
                    "import_tools.unresolved",
                    f"import_tools lists {name} but it was not found under tools.",
                    FindingSeverity.MEDIUM,
                    FindingClass.MANTLE_ONLY,
                )
        skills_root = project_root / "skills"
        for ref in inv.skill_refs:
            if skills_root.is_dir() and not (skills_root / ref).is_dir():
                add(
                    "composition.missing_target",
                    f"@skill.{ref} has no matching skills/{ref}/ folder.",
                    FindingSeverity.HIGH,
                    FindingClass.MANTLE_ONLY,
                )

    if SESSION_PROSE_RE.search(inv.body) and "@memory." not in inv.body:
        # Bare session.* in free prose fails rasa train; if: lines are OK.
        prose_lines = []
        for line in inv.body.splitlines():
            stripped = line.strip()
            if stripped.startswith("if:") or stripped.startswith("#"):
                continue
            if "session." in line:
                prose_lines.append(line)
        prose = "\n".join(prose_lines)
        if prose and "complete_when:" not in prose:
            add(
                "memory.session_in_prose",
                "Body mentions session.* outside if: conditions; "
                "use @memory tokens in prose.",
                FindingSeverity.LOW,
                FindingClass.MANTLE_ONLY,
            )

    if inv.extra_frontmatter_keys:
        add(
            "spec.extra_frontmatter",
            "Mantle extra keys "
            + ", ".join(inv.extra_frontmatter_keys)
            + " are invalid Agent Skills frontmatter. "
            "Native files are expected to fail NVIDIA schema.",
            FindingSeverity.INFO,
            FindingClass.SPEC_MISMATCH,
        )

    is_session_start = inv.skill_id == "default_session_start"
    routing = inv.frontmatter.get("routing")
    if isinstance(routing, dict) and routing.get("engine_managed"):
        is_session_start = True

    if is_session_start:
        for field in inv.llm_settable_project_fields:
            add(
                "memory.project_llm_settable",
                f"Project memory field {field} is llm_settable; "
                "identity must be written by a tool, not the LLM.",
                FindingSeverity.HIGH,
                FindingClass.MANTLE_ONLY,
            )
        if inv.voice_enabled and not inv.voice_one_question:
            add(
                "voice.one_question",
                "Voice is enabled but agent.yml does not tell the model "
                "to ask only one clarifying question at a time.",
                FindingSeverity.MEDIUM,
                FindingClass.MANTLE_ONLY,
            )
        skill_dir = Path(inv.source_path)
        for key in _memory_set_keys(skill_dir):
            if key.startswith("project."):
                add(
                    "memory.session_start_project_prefix",
                    f"Session-start tool writes {key}. Mantle wants a bare key "
                    "such as customer_name, not project.customer_name.",
                    FindingSeverity.HIGH,
                    FindingClass.MANTLE_ONLY,
                )
    elif project_root is not None:
        reused = [name for name in inv.import_tools if name in IDENTITY_TOOLS]
        reused += [name for name in IDENTITY_TOOLS if name in inv.body]
        if reused and not any(ref.startswith("project.") for ref in inv.memory_refs):
            add(
                "memory.identity_relookup",
                "Downstream skill looks up identity via "
                + ", ".join(sorted(set(reused)))
                + " instead of reading @memory.project.* set at session start.",
                FindingSeverity.MEDIUM,
                FindingClass.MANTLE_ONLY,
            )
    return out
