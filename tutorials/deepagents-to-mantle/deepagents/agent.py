"""Run a Deep Agents chat over the shared, read-only Chinook tools."""
import argparse
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared import database
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.profiles import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


@tool
async def sql_db_list_tables() -> dict:
    """List the exact names of available database tables."""
    return database.list_tables()


@tool
async def sql_db_schema(table_names: str) -> dict:
    """Read CREATE TABLE definitions for comma-separated exact table names."""
    return database.schema(table_names)


@tool
async def sql_db_query_checker(query: str) -> dict:
    """Compile SQL to check syntax; this does not prove the query answers the question."""
    return database.check_query(query)


@tool
async def sql_db_query(query: str) -> dict:
    """Run one read-only SELECT and return at most 100 rows, or an explicit error."""
    return database.query(query)


def create_agent():
    model = ChatOpenAI(model="gpt-5.5-2026-04-23", reasoning_effort="low", max_retries=0)
    register_harness_profile(
        "openai:gpt-5.5-2026-04-23",
        HarnessProfile(
            excluded_tools=frozenset({"execute"}),
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    return create_deep_agent(
        model=model,
        tools=[sql_db_list_tables, sql_db_schema, sql_db_query_checker, sql_db_query],
        system_prompt=(ROOT / "shared/instructions.txt").read_text(),
        skills=["/skills/"],
        backend=FilesystemBackend(root_dir=str(Path(__file__).parent / "workspace"), virtual_mode=True),
        subagents=[],
    )


if __name__ == "__main__":
    import asyncio
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    args = parser.parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY explicitly; no dotenv search is performed")
    async def run():
        result = await create_agent().ainvoke({"messages": [{"role": "user", "content": args.question}]}, {"recursion_limit": 40})
        print(result["messages"][-1].content)
    asyncio.run(run())
