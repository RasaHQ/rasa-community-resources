#!/usr/bin/env python3
"""Generate one GitHub Codespaces configuration per runnable resource, and the README block that links it.

Every configuration is derived from the resource itself (its pyproject, .env.example and Makefile) and written
by this script, never copied by hand. `--check` reports anything missing or stale and is part of `make validate`.

Usage:
    python3 scripts/generate_codespaces.py            # write configurations and README blocks
    python3 scripts/generate_codespaces.py --check    # fail if any is missing or out of date
    python3 scripts/generate_codespaces.py --list     # print one resource path per line
    python3 scripts/generate_codespaces.py --list-json  # the same as a JSON matrix for CI
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rasa_projects import REPO_ROOT, discover_projects  # noqa: E402

REPO = "RasaHQ/rasa-community-resources"
KNOWN_SECRETS = {
    "NVIDIA_API_KEY": "NVIDIA Build key for this evaluation harness's scoring and model calls",
    "RASA_LICENSE": "Full Rasa Developer Edition license",
    "RASA_PRO_LICENSE": "Full Rasa Developer Edition license",
    "OPENAI_API_KEY": "OpenAI project key used for this resource's model calls",
    "ANTHROPIC_API_KEY": "Anthropic key used for this resource's model calls",
    "SLACK_BOT_TOKEN": "Slack bot token for live Slack tools",
    "SLACK_APP_TOKEN": "Slack app token for the optional Socket Mode listener",
    "DEEPSEEK_API_KEY": "DeepSeek account key for the DevPilot orchestrator",
    "MISTRAL_API_KEY": "Mistral account key for this resource's model calls",
    "GROQ_API_KEY": "Groq account key for this resource's configured model calls",
    "USDA_FDC_API_KEY": "Optional USDA FoodData Central key for a higher lookup quota",
    "GEMINI_API_KEY": "Google Gemini key used for this resource's model calls",
    "LANGFUSE_PUBLIC_KEY": "Langfuse public key for this resource's tracing",
    "LANGFUSE_SECRET_KEY": "Langfuse secret key for this resource's tracing",
    "DEEPGRAM_API_KEY": "Deepgram key for speech recognition and spoken replies",
    "RIME_API_KEY": "Rime key for spoken replies",
    "SPEECHMATICS_API_KEY": "Speechmatics key for speech recognition",
}
# Exact feature version, so a published change to the feature cannot alter a configuration unseen.
SSHD_FEATURE = "ghcr.io/devcontainers/features/sshd:1.1.0"
LICENSE_ALIAS = "RASA_PRO_LICENSE"
DEFAULT_SECRETS = ["RASA_LICENSE", "OPENAI_API_KEY"]
START, END = "<!-- codespaces:start -->", "<!-- codespaces:end -->"
SETUP_ANCHOR = "README.md#run-any-resource-in-a-github-codespace"


def slug(rel: str) -> str:
    return rel.replace("/", "-")


def env_example_keys(path: Path) -> list[str]:
    example = path / ".env.example"
    keys: list[str] = []
    if example.is_file():
        for line in example.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^([A-Z][A-Z0-9_]*)=", line.strip())
            if match:
                keys.append(match.group(1))
    return keys


def make_targets(path: Path) -> set[str]:
    makefile = path / "Makefile"
    text = makefile.read_text(encoding="utf-8") if makefile.is_file() else ""
    return set(re.findall(r"^([A-Za-z][\w-]*):", text, re.M))


def env_example_secrets(path: Path) -> dict[str, bool]:
    """Secret name -> required, read from the section headers in .env.example ("Required" or "Optional")."""
    example = path / ".env.example"
    found: dict[str, bool] = {}
    if not example.is_file():
        return found
    required = True
    for line in example.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text.startswith("#"):
            if re.search(r"\boptional\b", text, re.I):
                required = False
            elif re.search(r"\brequired\b", text, re.I):
                required = True
            continue
        match = re.match(r"^([A-Z][A-Z0-9_]*)=", text)
        if match and match.group(1) in KNOWN_SECRETS:
            found[match.group(1)] = required
    return found


# Resources whose first command comes from their own README rather than a Makefile target.
FIRST = {
    "heroes/wave-01-mantle/projects/incrementaliser-rasa-skill-eval": (
        "uv run --locked --no-sync pytest && uv run --locked --no-sync ruff check src tests scripts",
        "the offline unit suite and lint checks finish. Model scoring and licensed training are separate steps below; no evaluation starts automatically.",
    ),
    "heroes/wave-01-mantle/projects/phlenfyl-notevs-agent": (
        "uv run --locked python -m rasa train && bash ./start.sh",
        "the REST server starts on port 5005. Standalone chat can run without NoteVs; "
        "note operations require an explicit extension-host workspace. Real notes stay on the desktop; do not expose or tunnel the extension endpoint.",
    ),
    "heroes/wave-01-mantle/projects/chandratechblog-hrassistant": (
        "uv run rasa train && uv run rasa inspect",
        'training finishes, then the Inspector starts. In a second terminal, '
        '`bash "$(git rev-parse --show-toplevel)/.devcontainer/resource-base/print-inspector-url.sh"` prints its address.',
    ),
    "tutorials/agent-tool-inventory": ("make check", "a JSON result with `status: match`."),
    "tutorials/rasa-ai-team-casebook": (
        "python3 casebook.py --case contextual-handoff --prove",
        "ten observed fixtures printed; this one needs no license and no network.",
    ),
    "tutorials/refusal-handoff": ("make native-test", "the native controls finish with `OK`."),
    "patterns/evaluation-harness": ("uv run rasa train", "training completes, then follow the README's quick start."),
    "patterns/mcp-confirmation-gate": (
        "uv run --locked python -m unittest discover -s tests -v",
        "the tests finish with `OK`.",
    ),
    "patterns/session-start-personalization": (
        "uv run rasa train && uv run rasa inspect",
        "training completes, then the Inspector starts.",
    ),
}

# Resources whose first command needs no license, key or network: their secrets are only for the later steps.
FIRST_NEEDS_NONE = {
    "tutorials/rasa-ai-team-casebook",
    "heroes/wave-01-mantle/projects/incrementaliser-rasa-skill-eval",
}


def uses_references(path: Path) -> bool:
    """Training builds a references index (embedding calls to the OpenAI account) for these resources."""
    agent = path / "agent.yml"
    if not agent.is_file():
        return False
    return (path / "references").is_dir() or any(
        line.startswith("references:") for line in agent.read_text(encoding="utf-8").splitlines()
    )


# Resources without a pyproject.toml, each with its own launcher.
MANUAL = [
    {
        "path": "examples/mantle-factory-agent",
        "secrets": {"RASA_LICENSE": True, "OPENAI_API_KEY": False},
        "install": "cd examples/mantle-factory-agent && { bash \"$(git rev-parse --show-toplevel)/.devcontainer/resource-base/make-env.sh\" . || echo \"NOTE: .env was not created; the secrets stay in your environment.\"; } && ./demo setup",
        "ready": "test -x project/.venv/bin/python",
        "first": './demo run --expires-at "$(date -u -d \'+8 hours\' +%Y-%m-%dT%H:%M:%SZ)"',
        "see": "the log says it is ready; open forwarded port 8947. The factory needs a no-network sandbox wrapper "
        "and says `NOT_READY` if the Codespace has none.",
        "ports": [8947, 5007],
    },
    {
        "path": "examples/mantle-flight-briefing-openai-agents",
        "secrets": {"RASA_LICENSE": True, "OPENAI_API_KEY": False, "DEEPGRAM_API_KEY": False},
        "install": "cd examples/mantle-flight-briefing-openai-agents && { bash \"$(git rev-parse --show-toplevel)/.devcontainer/resource-base/make-env.sh\" . || echo \"NOTE: .env was not created; the secrets stay in your environment.\"; } && make setup",
        "ready": "make doctor",
        "first": "make run-scripted",
        "see": "the launcher reports ready; open forwarded port 8942 for the card page.",
        "ports": [8942, 5005],
    },
]


def recipe(makefile_text: str, target: str) -> str:
    """The recipe lines of one Makefile target."""
    match = re.search(rf"^{re.escape(target)}:[^\n]*\n((?:\t[^\n]*\n?)*)", makefile_text, re.M)
    return match.group(1) if match else ""


def ports(path: Path) -> tuple[int, list[int]]:
    """(primary port, every port to forward): explicit --port/-p values in the run or inspect recipe, else 5005,
    plus any other port the Makefile documents for a helper service."""
    makefile = path / "Makefile"
    text = makefile.read_text(encoding="utf-8") if makefile.is_file() else ""
    explicit = [int(n) for target in ("inspect", "run") for n in re.findall(r"(?:--port|\s-p)\s+(\d{4,5})\b", recipe(text, target))]
    documented = [int(n) for n in re.findall(r"(?:localhost|127\.0\.0\.1|\s):(\d{4,5})\b", text)]
    primary = explicit[0] if explicit else 5005
    return primary, sorted({primary, *explicit, *documented})


def manifest(project) -> dict:
    """The small per-resource record the template is filled from, derived from the resource's own files."""
    data = tomllib.loads(project.pyproject.read_text(encoding="utf-8"))
    catalog = data.get("tool", {}).get("rasa-catalog", {})
    declared = catalog.get("required-secrets", [])
    license_secret = catalog.get("license-secret", "RASA_LICENSE")
    if license_secret not in {"RASA_LICENSE", LICENSE_ALIAS}:
        raise ValueError(f"{project.rel}: unsupported licence secret name")
    # Secret ownership is independent of the SDK's licence variable name.
    secret_setup = catalog.get("secret-setup", "operator" if license_secret == LICENSE_ALIAS else "personal")
    if secret_setup not in {"personal", "operator"}:
        raise ValueError(f"{project.rel}: unsupported secret setup")
    keys = env_example_keys(project.path)
    secrets = {license_secret: True}
    for name, required in env_example_secrets(project.path).items():
        if name in {"RASA_LICENSE", LICENSE_ALIAS} and name != license_secret:
            continue
        secrets.setdefault(name, required)
    for name in declared:
        if name in KNOWN_SECRETS and (name not in {"RASA_LICENSE", LICENSE_ALIAS} or name == license_secret):
            secrets[name] = True
    if not keys and not declared:
        for name in DEFAULT_SECRETS:
            if name != "RASA_LICENSE":
                secrets.setdefault(name, True)
    targets = make_targets(project.path)
    first_target = "inspect" if "inspect" in targets else "run" if "run" in targets else None
    primary, forward = ports(project.path)
    snapshot = getattr(project, 'snapshot', False)
    if snapshot and first_target == 'inspect':
        # The API's run port need not be the Inspector's port. Use the selected
        # first command's recipe; an unqualified inspect uses the default 5005.
        makefile = (project.path / 'Makefile').read_text()
        inspector_ports = re.findall(r'(?:--port|\s-p)\s+(\d{4,5})\b', recipe(makefile, 'inspect'))
        primary = int(inspector_ports[0]) if inspector_ports else 5005
        forward = sorted({*forward, primary})
    train = "make train && " if "train" in targets and first_target else ""
    if project.rel in FIRST:
        first, see = FIRST[project.rel]
    elif first_target == "inspect":
        helper = '.devcontainer/resource-base/print-inspector-url.sh'
        port_arg = "" if primary == 5005 else f" {primary}"
        first = train + "make inspect"
        see = (
            "training finishes, then the Inspector starts. In a second terminal, "
            f'`bash "$(git rev-parse --show-toplevel)/{helper}"{port_arg}` prints its address.'
            if train
            else "the Inspector starts. In a second terminal, "
            f'`bash "$(git rev-parse --show-toplevel)/{helper}"{port_arg}` prints its address.'
        )
    elif first_target == "run":
        first = train + "make run"
        see = f"{'training finishes, then ' if train else ''}the server starts on port {primary}."
    else:
        first, see = None, None
    first_needs_none = project.rel in FIRST_NEEDS_NONE
    if first_needs_none:
        secrets = {name: False for name in secrets}
    provider_note = ""
    before_first = ""
    remote_env = {}
    if project.rel == 'heroes/wave-01-mantle/projects/traromal-devcopilot':
        provider_note = ("Save a DeepSeek account key as `DEEPSEEK_API_KEY`. "
                         "This Codespace maps it to the project's `OPENAI_API_KEY`.")
        secrets.pop('OPENAI_API_KEY', None)
        secrets['DEEPSEEK_API_KEY'] = True
        remote_env['OPENAI_API_KEY'] = '${containerEnv:DEEPSEEK_API_KEY}'
        secrets.setdefault('SLACK_BOT_TOKEN', False)
        secrets.setdefault('SLACK_APP_TOKEN', False)
        before_first = ('In two other terminals in this folder, run '
                        '`uv run python -m scripts.mcp_demo_serve` and '
                        '`uv run python -m scripts.mcp_slack_serve`. '
                        'Keep both bridges running before starting Rasa. Live Slack features need the optional Slack tokens.')
    if project.rel == 'heroes/wave-01-mantle/projects/phlenfyl-notevs-agent':
        # The source defaults to Groq and supports two optional alternatives.
        secrets['GROQ_API_KEY'] = True
        secrets['OPENAI_API_KEY'] = False
        secrets['ANTHROPIC_API_KEY'] = False
        remote_env[LICENSE_ALIAS] = '${containerEnv:RASA_LICENSE}'
        provider_note = 'Groq is the default provider. OpenAI or Anthropic keys are only needed when you select that provider in the project setup.'
    if project.rel == 'examples/fiserv-banking-hub-11.0.0.2026.4.1':
        # The learner supplies the vendor release file by hand before the first run.
        before_first = ("Download Fiserv's release ZIP and upload it to `vendor-inputs/` in this folder "
                        "(README steps 1 and 3); without it `make run` stops with a plain message.")
        see = ("`Vendor definitions: found and hash-verified`, then `Rasa server is up and running`; "
               "only then open the printed Inspector link.")
    if snapshot and 'backend' in targets:
        forward = sorted(set(forward) | {int(n) for n in re.findall(
            r'--port\s+(\d{4,5})\b', recipe((project.path / 'Makefile').read_text(), 'backend'))})
        before_first = 'In another terminal in this folder, run `make backend` and keep it running for the analysis tools.'

    ready = ('python3 "$(git rev-parse --show-toplevel)/scripts/check_project.py" '
             + project.rel + ' --skip-sync --use-project-pin') if snapshot else None
    if project.rel in {
        'heroes/wave-01-mantle/projects/malar-saravanan-nourishher-voice',
        'heroes/wave-01-mantle/projects/cycywanyeki20-stammy',
        'heroes/wave-01-mantle/projects/phlenfyl-notevs-agent',
    }:
        # These deterministic tool suites make no provider calls.
        ready += ' && uv run --locked --no-sync python -m unittest discover -s tests -v'
    if project.rel == 'heroes/wave-01-mantle/projects/incrementaliser-rasa-skill-eval':
        ready += ' && uv run --locked --no-sync pytest && uv run --locked --no-sync ruff check src tests scripts'
    return {
        "snapshot": snapshot,
        "provider_note": provider_note,
        "before_first": before_first,
        "remote_env": remote_env,
        "path": project.rel,
        "slug": slug(project.rel),
        "first_needs_none": first_needs_none,
        "embeds_references": uses_references(project.path),
        "secrets": secrets,
        "alias_license": license_secret == "RASA_LICENSE" and LICENSE_ALIAS in keys,
        "operator_secrets": secret_setup == "operator",
        "install": 'bash "$(git rev-parse --show-toplevel)/.devcontainer/resource-base/install.sh" ' + project.rel,
        "ready": ready,
        "first": first,
        "see": see,
        "ports": forward,
        "inspect_helper": first_target == "inspect" and project.rel not in FIRST,
    }


def manual_manifest(item: dict) -> dict:
    entry = dict(item)
    entry["slug"] = slug(item["path"])
    entry["alias_license"] = False
    entry["inspect_helper"] = False
    return entry


def config(entry: dict) -> str:
    ready = 'bash "$(git rev-parse --show-toplevel)/.devcontainer/resource-base/ready.sh" ' + entry["path"]
    if entry["ready"]:
        ready += " " + json.dumps(entry["ready"])
    install = entry["install"]
    if entry["path"] in {m["path"] for m in MANUAL}:
        install = 'cd "$(git rev-parse --show-toplevel)" && ' + install
    body = {
        "name": "Rasa resource: " + entry["path"],
        "build": {"dockerfile": "../resource-base/Dockerfile"},
        "features": {
            SSHD_FEATURE: {},
        },
        "workspaceFolder": "/workspaces/${localWorkspaceFolderBasename}/" + entry["path"],
        "hostRequirements": {"cpus": 4, "memory": "8gb", "storage": "32gb"},
        "forwardPorts": entry["ports"],
        "portsAttributes": {str(port): {"onAutoForward": "silent"} for port in entry["ports"]},
        "secrets": {
            name: {"description": ("Required. " if required else "Optional. ") + KNOWN_SECRETS[name]}
            for name, required in entry["secrets"].items()
        },
        "onCreateCommand": install,
        "postCreateCommand": ready,
    }
    remote_env = dict(entry.get("remote_env", {}))
    if entry["alias_license"]:
        # Holds for non-interactive shells, tasks and launch configurations, unlike a line in ~/.bashrc.
        remote_env[LICENSE_ALIAS] = "${containerEnv:RASA_LICENSE}"
    if remote_env:
        body["remoteEnv"] = remote_env
    return json.dumps(body, indent=2) + "\n"


def launch_url(entry: dict) -> str:
    return (
        f"https://codespaces.new/{REPO}?ref=main"
        f"&devcontainer_path=.devcontainer/{entry['slug']}/devcontainer.json"
    )


def readme_block(entry: dict, depth: int) -> str:
    # These banking demos require a learner-supplied contract before startup.
    # This changes README guidance only, never the devcontainer or its commands.
    name = entry["path"].split("/")[-1]
    if entry["path"] in {
        "examples/jack-henry-silverlake", "examples/jack-henry-symitar",
        "examples/fiserv-premier", "examples/fiserv-premier-11.0.0-prm",
    }:
        inputs = ("run `make download` and wait for `Saved and checked`" if name == "jack-henry-silverlake"
                  else "upload the four definitions into `vendor-inputs/`" if name == "jack-henry-symitar"
                  else "upload the unopened Premier ZIP into `vendor-inputs/`")
        return "\n".join([
            START,
            f"[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)]({launch_url(entry)})",
            "",
            "- **Before starting:** save `RASA_LICENSE`, `OPENAI_API_KEY`, and `DEEPGRAM_API_KEY` as personal Codespaces secrets. [Get the keys](https://rasa.community/keys/) and follow [the walkthrough](#walkthrough).",
            "- **Use this badge:** it selects this example's development environment.",
            f"- **After the setup log says `READY`:** {inputs}, then run `make run`.",
            "- **Open the assistant:** wait for `Rasa server is up and running`, then follow the printed Inspector link. The server uses port `5005`.",
            END,
        ])
    required = [f"`{n}`" for n, req in entry["secrets"].items() if req]
    optional = [f"`{n}`" for n, req in entry["secrets"].items() if not req]
    if entry.get("first_needs_none"):
        need = ("nothing for the first command, which needs no license and no network. Later steps use the free Rasa "
                "Developer Edition license and the keys named: " + ", ".join(optional))
    else:
        need = "the free Rasa Developer Edition license and the keys it names: required " + ", ".join(required)
        if optional:
            need += "; optional " + ", ".join(optional) + (
                " (see the project's setup requirements below)" if entry.get('snapshot')
                else " (the resource runs without them)")
    first = entry["first"]
    if first:
        first_line = f"`{first}`. The terminal opens in this folder, and the creation log ends with `READY`."
        if entry.get("embeds_references"):
            first_line += (" Training may make provider calls to index this resource's reference documents; see the setup requirements below."
                           if entry.get('snapshot') else " Training uses your OpenAI key (a small embedding call) to index this resource's reference documents.")
        see = entry["see"]
    else:
        first_line = "follow the steps below; the creation log ends with `READY`."
        see = "`READY` at the end of the creation log."
    snapshot_note = ("This cohort snapshot installs its own locked Rasa version; it does not track catalog upgrades.\n\n"
                     if entry.get('snapshot') else "")
    if entry.get('provider_note'):
        snapshot_note += entry['provider_note'] + "\n\n"
    return "\n".join(
        [
            START,
            f"[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)]({launch_url(entry)})",
            "",
            snapshot_note + f"- **You need:** {need}, "
            + ("configured by the operator as repository or organisation Codespaces secrets "
               if entry.get("operator_secrets") else "saved once as personal Codespaces secrets ") +
            f"([how]({'../' * depth}{SETUP_ANCHOR})). Use this button rather than the Codespaces picker, "
            "so you get this resource's setup.",
            *((["- **Before the first command:** " + entry['before_first']]) if entry.get('before_first') else []),
            f"- **First command:** {first_line}",
            f"- **You should see:** {see}",
            END,
        ]
    )


def with_block(text: str, block: str) -> str:
    if START in text and END in text:
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
        return before + block + after
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("# "):
            return "".join(lines[: index + 1]) + "\n" + block + "\n" + "".join(lines[index + 1 :])
    raise ValueError("README has no top-level heading")


def projects():
    """Maintained and frozen runnable resources share Codespaces discovery only."""
    return discover_projects('catalog') + discover_projects('snapshots')


# The workshop's own configuration is kept by hand (it is not generated), so it is listed separately.
WORKSHOP = {"path": "workshops/software-factories-masterclass", "slug": "travel-factory"}


def launch_matrix() -> list[dict]:
    """Every resource with an Open in GitHub Codespaces button, as {path, slug}."""
    paths = [project.rel for project in projects()] + [item["path"] for item in MANUAL]
    return [{"path": path, "slug": slug(path)} for path in paths] + [dict(WORKSHOP)]


def plan() -> list[tuple[Path, str]]:
    changes: list[tuple[Path, str]] = []
    entries = [manifest(project) for project in projects()] + [manual_manifest(m) for m in MANUAL]
    for entry in entries:
        changes.append((REPO_ROOT / ".devcontainer" / entry["slug"] / "devcontainer.json", config(entry)))
        readme = REPO_ROOT / entry["path"] / "README.md"
        depth = len(Path(entry["path"]).parts)
        changes.append((readme, with_block(readme.read_text(encoding="utf-8"), readme_block(entry, depth))))
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--list-json", action="store_true", help="print the resources as a JSON matrix for CI")
    args = parser.parse_args()
    if args.list_json:
        print(json.dumps(launch_matrix()))
        return 0
    if args.list:
        for project in projects():
            print(project.rel)
        for item in MANUAL:
            print(item["path"])
        return 0
    stale = []
    for path, content in plan():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != content:
            stale.append(path.relative_to(REPO_ROOT).as_posix())
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
    if args.check:
        if stale:
            print("Codespaces configurations or README blocks are missing or out of date:", file=sys.stderr)
            for name in stale:
                print("  " + name, file=sys.stderr)
            print("Run: python3 scripts/generate_codespaces.py", file=sys.stderr)
            return 1
        print("Codespaces configurations and README blocks are current.")
        return 0
    print(f"Wrote {len(stale)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
