"""Synthetic table provider for the actual MCP protocol check."""
from datetime import datetime, timezone
from pathlib import Path
import os

from shop_demo.operations import create_shop_server
from shop_demo.shop import Shop
from test_shop import MemoryTables

shop = Shop(MemoryTables(), journal=Path(os.environ["SHOP_TEST_STATE"]) / "shop.sqlite3",
            currency="MXN", clock=lambda: datetime.now(timezone.utc))
try:
    create_shop_server(shop).run()
finally:
    shop.close()
