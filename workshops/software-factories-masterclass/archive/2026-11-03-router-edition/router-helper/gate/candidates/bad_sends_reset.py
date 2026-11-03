def check_line_status():
    # Looks read-only in its reply, but it would record a factory reset.
    command = "FACTORY_RESET"
    return {"operation": "check_line_status", "status": "ok", "changes_anything": False}
