"""Ingestion engine to load coffee shop transactions, customers, recipes, and inventory into SQLite."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
import pandas as pd


def find_project_root() -> Path:
    env_root = os.environ.get("PROJECT_ROOT")
    if env_root and Path(env_root).is_dir():
        return Path(env_root).resolve()
    cwd = Path.cwd().resolve()
    if (cwd / "data" / "Coffee Shop Sales.xlsx").is_file() or (cwd / "agent.yml").is_file():
        return cwd
    for parent in Path(__file__).resolve().parents:
        if (parent / "agent.yml").is_file() or (parent / "data" / "Coffee Shop Sales.xlsx").is_file():
            return parent
    return Path(__file__).resolve().parent.parent


def get_excel_path() -> Path:
    return find_project_root() / "data" / "Coffee Shop Sales.xlsx"


def get_db_path() -> Path:
    return find_project_root() / "data" / "coffeeshop.db"


def import_all(force: bool = False) -> None:
    """Ingest transactions Excel and auxiliary datasets into SQLite."""
    root = find_project_root()
    data_dir = root / "data"
    excel_path = get_excel_path()
    db_path = get_db_path()

    if not excel_path.is_file():
        raise FileNotFoundError(f"Source Excel not found at {excel_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check if transactions already loaded
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
    table_exists = cursor.fetchone()
    if table_exists and not force:
        cursor.execute("SELECT COUNT(*) FROM transactions")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"✓ SQLite database already populated with {count:,} transactions.")
            conn.close()
            return

    print(f"📦 Ingesting transactions from {excel_path.name} into {db_path.name}...")

    # 1. Transactions
    df_tx = pd.read_excel(excel_path, sheet_name="Transactions")
    df_tx["transaction_date"] = pd.to_datetime(df_tx["transaction_date"]).dt.strftime("%Y-%m-%d")
    df_tx["transaction_time"] = df_tx["transaction_time"].astype(str)
    df_tx["transaction_id"] = df_tx["transaction_id"].astype(str)
    df_tx["product_id"] = df_tx["product_id"].astype(str)
    df_tx["line_total"] = (df_tx["transaction_qty"] * df_tx["unit_price"]).round(2)
    df_tx.to_sql("transactions", conn, if_exists="replace", index=False)
    print(f"  ✓ Ingested {len(df_tx):,} records into 'transactions' table")

    # 2. Customers
    cust_path = data_dir / "customer_profiles.json"
    if cust_path.is_file():
        with open(cust_path, "r", encoding="utf-8") as f:
            cust_data = json.load(f)
        df_cust = pd.DataFrame(cust_data)
        df_cust.to_sql("customers", conn, if_exists="replace", index=False)
        print(f"  ✓ Ingested {len(df_cust):,} records into 'customers' table")

    # 3. Raw Materials Costs
    mat_path = data_dir / "raw_materials_costs.csv"
    if mat_path.is_file():
        df_mat = pd.read_csv(mat_path)
        df_mat.to_sql("raw_materials", conn, if_exists="replace", index=False)
        print(f"  ✓ Ingested {len(df_mat):,} records into 'raw_materials' table")

    # 4. Product Recipes / BOM
    rec_path = data_dir / "product_recipes.csv"
    if rec_path.is_file():
        df_rec = pd.read_csv(rec_path)
        df_rec.to_sql("product_recipes", conn, if_exists="replace", index=False)
        print(f"  ✓ Ingested {len(df_rec):,} records into 'product_recipes' table")

    # 5. Store Inventory
    inv_path = data_dir / "store_inventory.json"
    if inv_path.is_file():
        with open(inv_path, "r", encoding="utf-8") as f:
            inv_data = json.load(f)
        df_inv = pd.DataFrame(inv_data)
        df_inv.to_sql("store_inventory", conn, if_exists="replace", index=False)
        print(f"  ✓ Ingested {len(df_inv):,} records into 'store_inventory' table")

    # 6. Active Orders (Runtime table for customer order placement & barista queue)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT,
            customer_name TEXT,
            store_id INTEGER,
            store_location TEXT,
            item_name TEXT,
            size TEXT,
            milk_type TEXT,
            quantity INTEGER,
            unit_price REAL,
            total_price REAL,
            order_status TEXT, -- 'pending', 'brewing', 'ready_for_pickup', 'completed'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            special_instructions TEXT
        )
    """)

    # Pre-seed 3 active orders for barista queue testing
    cursor.execute("SELECT COUNT(*) FROM active_orders")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO active_orders (order_id, customer_id, customer_name, store_id, store_location, item_name, size, milk_type, quantity, unit_price, total_price, order_status, special_instructions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ("ORD-501", "CUST-1001", "Sarah Jenkins", 5, "Lower Manhattan", "Ethiopia Rg", "Rg", "Oat Milk", 1, 3.00, 3.80, "pending", "Extra hot"),
            ("ORD-502", "CUST-1002", "Marcus Vance", 3, "Astoria", "Spicy Eye Opener Chai Lg", "Lg", "Whole Milk", 1, 3.10, 3.10, "brewing", "No water, double spice"),
            ("ORD-503", "CUST-1003", "Elena Rostova", 8, "Hell's Kitchen", "Dark chocolate Lg", "Lg", "Almond Milk", 2, 4.50, 9.80, "pending", "Light whip"),
        ])
        print("  ✓ Seeded 3 active orders into 'active_orders' queue")

    # Create Indexes for lightning fast execution
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(transaction_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_store ON transactions(store_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_cat ON transactions(product_category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_type ON transactions(product_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cust_id ON customers(customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cust_phone ON customers(phone);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_store ON store_inventory(store_id, item_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_store ON active_orders(store_id, order_status);")

    conn.commit()
    conn.close()
    print("✨ Successfully ingested all tables and built performance indexes in coffeeshop.db.")


if __name__ == "__main__":
    import_all(force=True)
