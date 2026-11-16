"""The shop's private stdio MCP child; Google credentials stay in memory."""
from datetime import datetime, timezone
import os
from pathlib import Path

from .integration_tables import GoogleTables
from .operations import create_shop_server
from .shop import Shop
from .google_runtime import google_service
from pydantic import SecretStr


def main():
    service = google_service(SecretStr(os.environ["GOOGLE_TOKEN_JSON"]))
    shop = Shop(GoogleTables(service, os.environ["SHOP_SHEET_ID"]),
        journal=Path(os.environ["SHOP_STATE_DIR"]) / "shop.sqlite3", currency="MXN",
        clock=lambda: datetime.now(timezone.utc))
    try:
        create_shop_server(shop).run()
    finally:
        shop.close()
        connection = getattr(service, "sheets_service", None)
        if connection is not None and hasattr(connection, "close"):
            connection.close()


if __name__ == "__main__":
    # Provider tracebacks may include credentials or spreadsheet values.
    try:
        main()
    except Exception:
        import sys
        print("Shop server stopped; inspect the private operation journal.", file=sys.stderr)
        raise SystemExit(1) from None
