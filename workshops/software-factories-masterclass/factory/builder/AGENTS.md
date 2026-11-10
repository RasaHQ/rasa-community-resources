# Instructions for the builder

You are changing a Rasa Mantle agent project in `product/`. One task at a time: read it in `tasks/`, change only what it asks.

## Rules

- Edit or create files only under the paths the task lists in `allowed_paths`. Touch nothing else.
- There is a protected check you cannot see. Do not look for it, and do not try to recreate it.
- Run `python validate.py` before you finish. It asks Mantle's own authoring checks whether the project loads. It cannot tell you whether the change does what the task says. That is for you to be sure of.
- Add tests under `product/tests/` only when the task allows `product/tests/`.
- When you finish, say what you changed and what you checked. Plain statements. A person will compare them with the files.

## Mantle in four lines

- A skill is `product/skills/<id>/skill.md`: YAML frontmatter between `---` lines, then instructions in prose.
- A skill's tools are `async` functions decorated with `@tool` in `product/skills/<id>/tools.py`.
- Reply text lives in `product/responses.yml` under `responses:`.
- Agent-wide `rules:` go at the TOP LEVEL of `product/agent.yml`, next to `agent:`, not inside it.
