#!/usr/bin/env python3
"""Show demo customer profiles, store inventory, menu items, and CEO metrics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.database import (
    get_customer_profile,
    get_store_inventory,
    search_menu,
    get_executive_revenue_summary,
    get_store_benchmarks,
    get_cogs_and_margins,
)


def main():
    print("=" * 70)
    print("☕ Artisan Roast Coffee Co. — Demo Data & Analytics Preview")
    print("=" * 70)

    print("\n1. SAMPLE CUSTOMER PROFILES (Persona 1: Customer):")
    for cid in ["CUST-1001", "CUST-1002", "CUST-1003"]:
        cust = get_customer_profile(cid)
        if cust:
            print(f"  • {cust['name']} ({cust['customer_id']}) | Tier: {cust['loyalty_tier']} | Points: {cust['loyalty_points']} | Store: {cust['preferred_store_location']} | Fav: {cust['favorite_drink']}")

    print("\n2. SAMPLE MENU ITEMS:")
    items = search_menu(query="coffee", max_results=4)
    for itm in items:
        print(f"  • {itm['product_detail']} ({itm['product_type']}) - ${itm['unit_price']:.2f}")

    print("\n3. STORE INVENTORY & LOW-STOCK ALERTS (Persona 2: Operator):")
    for sid, loc in [(3, "Astoria"), (5, "Lower Manhattan"), (8, "Hell's Kitchen")]:
        low = get_store_inventory(sid, low_stock_only=True)
        print(f"  Store {sid} ({loc}): {len(low)} items low/out of stock")
        for itm in low[:2]:
            print(f"    - [ALERT] {itm['item_name']}: {itm['current_stock']} {itm['unit']} (reorder below {itm['reorder_threshold']})")

    print("\n4. EXECUTIVE FINANCIAL ANALYTICS (Persona 3: CEO - RBAC Gated):")
    rev = get_executive_revenue_summary()
    print(f"  • Total Revenue: ${rev['total_revenue']:,.2f} | Transactions: {rev['total_transactions']:,} | Avg Ticket: ${rev['avg_ticket_size']:.2f}")

    margins = get_cogs_and_margins()
    print(f"  • Portfolio Gross Margin: {margins['portfolio_gross_margin_pct']}% | Total Gross Profit: ${margins['portfolio_gross_profit']:,.2f}")

    print("\n5. MULTI-STORE BENCHMARK COMPARISON:")
    for b in get_store_benchmarks():
        print(f"  • Store {b['store_id']} ({b['store_location']}): ${b['total_revenue']:,.2f} ({b['total_orders']:,} orders, ${b['avg_ticket_size']:.2f} avg ticket)")
    print("=" * 70)


if __name__ == "__main__":
    main()
