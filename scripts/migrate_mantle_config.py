"""Move the legacy model-group selector to the Rasa 3.22 agent configuration.

Only the scalar form used by the maintained catalogue is rewritten. Unknown or
conflicting mappings require a reviewed repair, rather than a guessed selector.
"""
import argparse
from pathlib import Path
import re


BLOCK = re.compile(r"(?m)^llm:[ \t]*(?:#[^\n]*)?\n(?:[ \t]+[^\n]*\n|\n)*")
GROUP = re.compile(r"  model_group:[ \t]*(['\"]?)([A-Za-z0-9_.-]+)\1[ \t]*(?:#[^\n]*)?")


def migrate(project, *, dry_run=False):
    project = Path(project)
    agent_path = project / 'agent.yml'
    integrations_path = project / 'integrations.yml'
    if not agent_path.exists() or not integrations_path.exists():
        return []
    changes = {}
    selected = None
    paths = sorted(set(project.glob('integrations*.yml')) |
                   set(project.glob('integrations*.yml.in')))
    for path in paths:
        text = path.read_text()
        blocks = list(BLOCK.finditer(text))
        if not blocks:
            if re.search(r'(?m)^llm:', text):
                raise ValueError(f'{path}: unsupported inline llm mapping; review it before migration')
            continue
        if len(blocks) != 1:
            raise ValueError(f'{path}: duplicate llm selectors')
        block = blocks[0]
        values = [line for line in block.group().splitlines()[1:]
                  if line.strip() and not line.lstrip().startswith('#')]
        match = GROUP.fullmatch(values[0]) if len(values) == 1 else None
        if not match:
            raise ValueError(f'{path}: llm must contain only a literal model_group; review other settings')
        group = match.group(2)
        if selected is not None and group != selected:
            raise ValueError(f'{path}: alternate model group {group} needs its own reviewed agent configuration')
        selected = group
        changes[path] = text[:block.start()] + text[block.end():]
    if selected is None:
        return []
    agent = agent_path.read_text()
    existing = re.search(r'(?m)^orchestrator:[ \t]*\n(?:[ \t]+[^\n]*\n|\n)*', agent)
    if existing:
        groups = [GROUP.fullmatch(line) for line in existing.group().splitlines()[1:]]
        groups = [match.group(2) for match in groups if match]
        if not groups:
            start = existing.start() + len(existing.group().splitlines(keepends=True)[0])
            changes[agent_path] = agent[:start] + f'  model_group: {selected}\n' + agent[start:]
        elif groups != [selected]:
            raise ValueError(f'{agent_path}: existing orchestrator conflicts with legacy model group')
    elif re.search(r'(?m)^orchestrator:', agent):
        raise ValueError(f'{agent_path}: unsupported inline orchestrator; review it before migration')
    else:
        changes[agent_path] = agent.rstrip() + f'\n\norchestrator:\n  model_group: {selected}\n'
    if not dry_run:
        for path, text in changes.items():
            path.write_text(text)
    return [str(path.relative_to(project)) for path in changes]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    for name in migrate(args.project, dry_run=args.dry_run):
        print(name)
