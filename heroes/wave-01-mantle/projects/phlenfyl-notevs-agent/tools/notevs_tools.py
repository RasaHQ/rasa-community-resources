"""Shared Mantle tools for the NoteVs agent.

Thin async wrappers around the NoteVs VS Code extension's local HTTP server's
plain REST endpoint (POST /call — see extension/src/mcpServer.ts). That
endpoint already implements all 10 tool handlers and is reused as-is by the
classic-CALM build (via /mcp JSON-RPC) and the Claude Code/Cursor stdio
bridge (mcpBridge.ts) — /call is the simplest of the three transports, a
same-machine JSON POST with no MCP session negotiation needed, so that's
what these wrappers use.

folderPath IS now sent (2026-08-18, reversing the note below): with several
VS Code windows open at once, each running its own agent, mcpServer.ts's
fixed port (37492) means only one window's HTTP server ever actually wins
the bind — every window's tool calls land on that one winner regardless of
which window's chat sent them. Omitting folderPath let resolveFolderPath()
fall back to *that* winner's own vscode.workspace.workspaceFolders[0],
so every window silently saw whichever project happened to own the port —
confirmed live as an agent returning a completely different project's note
titles. resolveFolderPath already prefers an explicit args.folderPath over
that fallback, so sending it here fixes correctness regardless of which
physical server instance answers, without needing to touch the port at
all. NOTEVS_FOLDER_PATH is set per-window by agentProcess.ts from that
window's own getFolderPath() at spawn time.
[Historical note, no longer current: "folderPath is deliberately never
sent... Mantle tools have no equivalent of the classic engine's flow-level
cwd to forward anyway." — true that Mantle doesn't thread it through the
conversation, but the process's own env var doesn't need to be threaded
through anything; it's static for that window's whole session.]
"""

from __future__ import annotations

import os

import httpx

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

NOTEVS_CALL_URL = os.environ.get("NOTEVS_CALL_URL", "http://localhost:37492/call")
NOTEVS_FOLDER_PATH = os.environ.get("NOTEVS_FOLDER_PATH")


async def _call(tool_name: str, args: dict, context: ToolContext | None = None) -> ToolResult:
    if NOTEVS_FOLDER_PATH and "folderPath" not in args:
        args = {**args, "folderPath": NOTEVS_FOLDER_PATH}
    # Also mirror it into real declared project memory (see memory.yml) so
    # it's visible in `rasa inspect` and usable by scoped instructions
    # elsewhere, on top of the args-injection above (which is what actually
    # makes each HTTP call correct — this mirroring is a pure add-on, not a
    # dependency, so a bad/undeclared write must never break the real call).
    if context is not None and NOTEVS_FOLDER_PATH:
        try:
            context.memory.set("folder_path", NOTEVS_FOLDER_PATH)
        except Exception:
            pass
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(NOTEVS_CALL_URL, json={"tool": tool_name, "args": args})
    except httpx.HTTPError as exc:
        return ToolResult(llm_response={"ok": False, "error": f"notevs_extension_unreachable: {exc}"})

    try:
        body = resp.json()
    except ValueError:
        return ToolResult(llm_response={"ok": False, "error": f"non_json_response: {resp.text[:200]}"})

    if resp.status_code != 200:
        return ToolResult(llm_response={"ok": False, "error": body.get("error", body)})
    return ToolResult(llm_response=body.get("result"))


@tool(description="List all notes in the current project, most recently updated first (pinned notes first).")
async def list_notes(context: ToolContext = None) -> ToolResult:
    return await _call("notevs_list_notes", {}, context)


@tool(description="Get a single note's full content, tags, and annotations by its id.")
async def get_note(id: str, context: ToolContext = None) -> ToolResult:
    return await _call("notevs_get_note", {"id": id}, context)


@tool(description="Search notes by keyword across title, content, tags, and annotation comments.")
async def search_notes(query: str, context: ToolContext = None) -> ToolResult:
    return await _call("notevs_search_notes", {"query": query}, context)


@tool(description="Create a new note with a title and optional content.")
async def create_note(title: str, content: str = "", context: ToolContext = None) -> ToolResult:
    return await _call("notevs_create_note", {"title": title, "content": content}, context)


@tool(description="Update an existing note's title and/or content by id.")
async def save_note(id: str, title: str | None = None, content: str | None = None, context: ToolContext = None) -> ToolResult:
    args: dict = {"id": id}
    if title is not None:
        args["title"] = title
    if content is not None:
        args["content"] = content
    return await _call("notevs_save_note", args, context)


@tool(description="Permanently delete a note by id. Destructive — only call after the user has explicitly confirmed.")
async def delete_note(id: str, context: ToolContext = None) -> ToolResult:
    return await _call("notevs_delete_note", {"id": id}, context)


@tool(description="Attach a code annotation (file path + line range + comment) to an existing note.")
async def add_annotation(
    note_id: str,
    file_path: str,
    line_start: int,
    line_end: int,
    comment: str = "",
    context: ToolContext = None,
) -> ToolResult:
    return await _call(
        "notevs_add_annotation",
        {
            "noteId": note_id,
            "filePath": file_path,
            "lineStart": line_start,
            "lineEnd": line_end,
            "comment": comment,
        },
        context,
    )


@tool(description="Export a note to the user's connected Notion workspace. External side effect — only call after explicit confirmation.")
async def export_to_notion(id: str, context: ToolContext = None) -> ToolResult:
    return await _call("notevs_export_to_notion", {"id": id}, context)


@tool(description="Export a note to the user's connected Obsidian vault. External side effect — only call after explicit confirmation.")
async def export_to_obsidian(id: str, context: ToolContext = None) -> ToolResult:
    return await _call("notevs_export_to_obsidian", {"id": id}, context)


@tool(description="Create a reminder/task for a note, due on a given date (YYYY-MM-DD), via the user's connected Todoist or Google Tasks. External side effect — only call after explicit confirmation.")
async def create_reminder(id: str, due_date: str, context: ToolContext = None) -> ToolResult:
    # Named create_reminder, not set_reminder: Mantle's tool loader treats
    # `set_` as a reserved prefix (own to its memory-setter tools) and
    # silently drops any shared @tool with that prefix — confirmed via a
    # real `rasa train` run, which emitted
    # calm_v2.tool_loader.shared_tool.reserved_prefix for "set_reminder"
    # and then failed validation because the skill's import_tools/
    # tool_constraints reference to it couldn't resolve to anything.
    return await _call("notevs_set_reminder", {"id": id, "dueDate": due_date}, context)
