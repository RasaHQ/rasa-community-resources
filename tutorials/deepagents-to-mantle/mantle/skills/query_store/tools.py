"""Thin Mantle bindings: business queries live in shared.database."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from shared import database
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult


@tool(description="List the exact names of available database tables.")
async def sql_db_list_tables(context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=database.list_tables())


@tool(description="Read CREATE TABLE definitions for comma-separated exact table names.")
async def sql_db_schema(table_names: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=database.schema(table_names))


@tool(description="Compile SQL to check syntax; this does not prove the query answers the question.")
async def sql_db_query_checker(query: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=database.check_query(query))


@tool(description="Run one read-only SELECT and return at most 100 rows, or an explicit error.")
async def sql_db_query(query: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=database.query(query))
