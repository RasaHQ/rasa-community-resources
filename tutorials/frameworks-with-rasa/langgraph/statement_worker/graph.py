"""The graph keeps its own checkpoints. No model, network or financial writes."""
import os
import re
from typing import TypedDict

os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

ROWS = {
    "demo-a": [
        {"id": "S-101", "month": "2026-09", "category": "travel", "pence": 14900},
        {"id": "S-102", "month": "2026-10", "category": "travel", "pence": 2500},
        {"id": "S-103", "month": "2026-10", "category": "travel", "pence": 700},
        {"id": "S-104", "month": "2026-10", "category": "groceries", "pence": 4100},
    ],
    "demo-b": [
        {"id": "S-201", "month": "2026-10", "category": "travel", "pence": 9100},
    ],
}


def valid_month(value):
    return isinstance(value, str) and bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value))


class State(TypedDict, total=False):
    run_id: str
    demo_owner: str
    month: str
    status: str
    rows: list[dict]
    report: dict


def load_rows(state):
    # This is the retained graph's read step; it runs before the pause.
    return {"rows": ROWS[state["demo_owner"]]}


def ask_month(state):
    month = interrupt({
        "status": "needs_month", "question": "Which month, for example 2026-10?",
        "run_id": state["run_id"], "demo_owner": state["demo_owner"],
    })
    if not valid_month(month):
        raise ValueError("Invalid month")
    return {"month": month}


def total_travel(state):
    rows = [r for r in state["rows"] if r["month"] == state["month"] and r["category"] == "travel"]
    return {"status": "complete", "report": {
        "month": state["month"], "currency": "GBP", "pence": sum(r["pence"] for r in rows),
        "row_ids": [r["id"] for r in rows],
    }}


def build_graph(checkpointer):
    graph = StateGraph(State)
    graph.add_node("load_rows", load_rows)
    graph.add_node("ask_month", ask_month)
    graph.add_node("total_travel", total_travel)
    graph.add_edge(START, "load_rows")
    graph.add_edge("load_rows", "ask_month")
    graph.add_edge("ask_month", "total_travel")
    graph.add_edge("total_travel", END)
    return graph.compile(checkpointer=checkpointer)
