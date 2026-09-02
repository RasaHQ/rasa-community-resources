#!/usr/bin/env python3
"""Prove the transport swap: same instructions, different transport.

    make mcp-prove

No licence, no API key, no HubSpot account, no network beyond loopback. It
starts both mock servers itself, so there is nothing to run in another terminal.

Six checks, and each one fails loudly rather than warning:

  1. SKILL PROSE IS BYTE-IDENTICAL. The REST skill.md and the MCP skill.md
     differ only inside the YAML frontmatter. Every changed line is an
     `import_tools:` line. If a single line of instruction prose differs, this
     fails — that is the claim the whole tutorial rests on.
  2. `parse_mcp_servers` accepts the MCP integrations.yml and yields the server
     id the skills import.
  3. `try_parse_mcp_tool_import` parses each `mcp/<server>:<tool>` reference,
     and `get_bare_tool_name` returns the name the LLM will see.
  4. Every imported server id is actually configured. This is the check that
     turns a typo into an error instead of a silent missing tool.
  5. The MCP server really exposes the three imported tool names — over a real
     MCP session, the same `list_tools` call `MCPRuntime.prepare` makes.
  6. Calling `find_contact_by_email` over MCP returns the same customer the
     REST tool returns. Same fact, different wire.

Written to fail first. Break the swap — rename the server under `mcp_servers:`,
or a tool name in an `import_tools:` line, or edit a line of skill prose — and
the matching check goes red.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import socket
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

GREEN, RED, DIM, RESET = (
    ("\033[92m", "\033[91m", "\033[2m", "\033[0m")
    if sys.stdout.isatty()
    else ("", "", "", "")
)

MCP_HOST, MCP_PORT = "127.0.0.1", 8931
CRM_HOST, CRM_PORT = "127.0.0.1", 8787
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"

SKILLS = {
    "identify_customer": "find_contact_by_email",
    "check_tickets": "list_open_tickets",
    "log_interaction": "add_timeline_note",
}
SERVER_ID = "hubspot_crm"

_failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    print(f"  {mark} {label:<44} {detail}")
    if not ok:
        _failures.append(label)
    return ok


def _read(path: str) -> str:
    with open(os.path.join(_ROOT, path), encoding="utf-8") as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# 1. The claim: instructions survive the transport.
# ---------------------------------------------------------------------------
def prove_prose_unchanged() -> None:
    """Every difference between the REST and MCP skills is an import line."""
    print(f"\n{DIM}  1. skill instructions are unchanged by the swap{RESET}")
    import difflib

    for skill in sorted(SKILLS):
        rest = _read(f"skills/{skill}/skill.md").splitlines()
        mcp = _read(f"mcp_variant/skills/{skill}/skill.md").splitlines()

        changed = [
            line[1:].strip()
            for line in difflib.unified_diff(rest, mcp, n=0, lineterm="")
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        ]
        # Every changed line must be an import declaration: either the
        # `import_tools:` key itself or one of its list entries.
        offending = [
            line
            for line in changed
            if line != "import_tools:" and not line.startswith("- ")
        ]
        check(
            f"{skill}: only import_tools differs",
            not offending,
            f"{DIM}{len(changed)} changed line(s){RESET}"
            if not offending
            else f"{RED}prose changed: {offending}{RESET}",
        )

        # And the body below the frontmatter must be identical, byte for byte.
        rest_body = _read(f"skills/{skill}/skill.md").split("---\n", 2)[-1]
        mcp_body = _read(f"mcp_variant/skills/{skill}/skill.md").split("---\n", 2)[-1]
        check(
            f"{skill}: instruction body byte-identical",
            rest_body == mcp_body,
            f"{DIM}{len(rest_body)} bytes{RESET}"
            if rest_body == mcp_body
            else f"{RED}bodies differ{RESET}",
        )


# ---------------------------------------------------------------------------
# 2-4. Static configuration: what the engine checks at model load.
# ---------------------------------------------------------------------------
def prove_static_config() -> set[str]:
    """Parse integrations.yml and the import references the way Mantle does."""
    from rasa.mantle.config.mcp import parse_mcp_servers
    from rasa.mantle.tools.mcp_import_spec import (
        get_bare_tool_name,
        try_parse_mcp_tool_import,
    )
    from rasa.shared.utils.yaml import read_yaml_file

    print(f"\n{DIM}  2. integrations.yml parses as MCP server configuration{RESET}")
    raw = read_yaml_file(
        os.path.join(_ROOT, "mcp_variant/integrations.yml"), expand_env_vars=False
    )
    settings = parse_mcp_servers(raw.get("mcp_servers") or [])
    configured = set(settings.servers)
    check(
        "parse_mcp_servers accepts the file",
        configured == {SERVER_ID},
        f"{DIM}servers: {sorted(configured)}{RESET}",
    )
    # Look the server up defensively: when the id has been renamed, check 2
    # has already gone red and the remaining checks should still report rather
    # than disappear behind a traceback.
    configured_server = settings.servers.get(SERVER_ID)
    check(
        "server url is loopback http",
        configured_server is not None and configured_server.url == MCP_URL,
        f"{DIM}{configured_server.url}{RESET}"
        if configured_server is not None
        else f"{RED}no server named {SERVER_ID!r}{RESET}",
    )

    print(f"\n{DIM}  3. each skill's import parses as mcp/<server>:<tool>{RESET}")
    imported: set[str] = set()
    for skill, tool in sorted(SKILLS.items()):
        text = _read(f"mcp_variant/skills/{skill}/skill.md")
        reference = f"mcp/{SERVER_ID}:{tool}"
        declared = reference in text
        parsed = try_parse_mcp_tool_import(reference)
        bare = get_bare_tool_name(reference)
        imported.add(parsed.server_id)
        check(
            f"{skill} imports {tool}",
            declared and parsed.tool_name == tool and bare == tool,
            f"{DIM}server={parsed.server_id} llm sees '{bare}'{RESET}"
            if declared
            else f"{RED}reference not found in skill.md{RESET}",
        )

    print(f"\n{DIM}  4. every imported server is configured{RESET}")
    missing = imported - configured
    check(
        "no skill imports an unconfigured server",
        not missing,
        f"{DIM}{sorted(imported)} ⊆ {sorted(configured)}{RESET}"
        if not missing
        else f"{RED}missing from integrations.yml: {sorted(missing)}{RESET}",
    )
    return configured


# ---------------------------------------------------------------------------
# 5-6. The live half: a real MCP session against the bundled server.
# ---------------------------------------------------------------------------
async def prove_live_mcp() -> None:
    """List and call tools over MCP, exactly as MCPRuntime.prepare does."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    print(f"\n{DIM}  5. the MCP server exposes the imported tools{RESET}")
    async with streamablehttp_client(MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            listed = await session.list_tools()
            remote = {tool.name for tool in listed.tools}
            for skill, tool in sorted(SKILLS.items()):
                check(
                    f"server exposes {tool}",
                    tool in remote,
                    f"{DIM}imported by {skill}{RESET}"
                    if tool in remote
                    else f"{RED}not offered by the server{RESET}",
                )

            print(f"\n{DIM}  6. a tool call over MCP returns the CRM fact{RESET}")
            result = await session.call_tool(
                "find_contact_by_email", {"email": "dana.okafor@example.com"}
            )
            # structuredContent must be populated, not None. Mantle only gets a
            # flat object when the tool publishes an outputSchema; without one
            # it falls back to dumping content blocks and the skill prose that
            # branches on `ok` / `error` stops matching what the model sees.
            # This assertion is here because the first version of the server
            # returned bare dicts and failed exactly this way.
            check(
                "result is structured, not text blocks",
                result.structuredContent is not None,
                f"{DIM}outputSchema published{RESET}"
                if result.structuredContent is not None
                else f"{RED}structuredContent is None — tool has no outputSchema{RESET}",
            )
            payload = result.structuredContent or {}
            check(
                "find_contact_by_email over MCP",
                payload.get("ok") is True and payload.get("name") == "Dana Okafor",
                f"{DIM}{payload.get('name')} at {payload.get('company')}{RESET}",
            )

            # The absent/broken distinction the REST tutorial teaches survives
            # too: a CRM that answers "nobody matches" is not a CRM that is down.
            absent = await session.call_tool(
                "find_contact_by_email", {"email": "nobody@example.com"}
            )
            absent_payload = absent.structuredContent or {}
            check(
                "absent contact is not an error",
                absent_payload.get("error") == "contact_not_found",
                f"{DIM}error={absent_payload.get('error')}{RESET}",
            )


# ---------------------------------------------------------------------------
# Server plumbing: start both mocks, wait for the ports, tear them down.
# ---------------------------------------------------------------------------
def _wait_for_port(host: str, port: int, timeout: float = 25.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with contextlib.suppress(OSError):
            with socket.create_connection((host, port), timeout=0.5):
                return True
        time.sleep(0.15)
    return False


@contextlib.contextmanager
def _servers():
    """Run the mock CRM and the MCP server for the duration of the proof."""
    env = dict(os.environ)
    env.setdefault("HUBSPOT_BASE_URL", f"http://{CRM_HOST}:{CRM_PORT}")
    env.setdefault("HUBSPOT_ACCESS_TOKEN", "mock-token")
    procs = []
    try:
        for script, host, port in (
            ("scripts/mock_hubspot.py", CRM_HOST, CRM_PORT),
            ("scripts/mcp_crm_server.py", MCP_HOST, MCP_PORT),
        ):
            procs.append(
                subprocess.Popen(
                    [sys.executable, os.path.join(_ROOT, script)],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
            if not _wait_for_port(host, port):
                raise SystemExit(f"{RED}  {script} did not come up on {port}{RESET}")
        yield
    finally:
        for proc in procs:
            proc.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=5)


def main() -> int:
    print()
    print("  Proving: the same three skills keep their instructions while")
    print("  tools/crm.py is replaced by import_tools: mcp/<server>:<tool>.")
    print(f"{DIM}  No licence, no API key, no HubSpot account, loopback only.{RESET}")

    prove_prose_unchanged()
    prove_static_config()
    with _servers():
        asyncio.run(prove_live_mcp())

    print()
    if _failures:
        print(f"{RED}  {len(_failures)} check(s) failed:{RESET}")
        for label in _failures:
            print(f"{RED}    - {label}{RESET}")
        print()
        return 1
    print(f"{GREEN}  The transport changed. The instructions did not.{RESET}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
