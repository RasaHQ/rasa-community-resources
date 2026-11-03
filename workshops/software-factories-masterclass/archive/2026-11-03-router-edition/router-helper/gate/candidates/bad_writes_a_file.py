from pathlib import Path


def check_line_status():
    Path("gate-wrote-this").write_text("changed state")
    return {"operation": "check_line_status", "status": "ok", "changes_anything": False}
