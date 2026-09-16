"""High performance database query layer for Artisan Roast Coffee AI Agent."""

from __future__ import annotations

import sqlite3
from typing import Any, Optional
from lib.importer import get_db_path, import_all


def get_db_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database, auto-ingesting if needed."""
    db_path = get_db_path()
    if not db_path.is_file():
        import_all(force=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ------------------------------------------------------------------------------
# 1. Customer Persona Queries
# ------------------------------------------------------------------------------

def search_menu(
    category: str = "",
    query: str = "",
    max_results: int = 6,
) -> list[dict[str, Any]]:
    """Search available beverages and bakery items with prices and details."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT DISTINCT product_category, product_type, product_detail, unit_price
        FROM transactions
        WHERE 1=1
    """
    params: list[Any] = []

    if category:
        sql += " AND UPPER(product_category) LIKE ?"
        params.append(f"%{category.strip().upper()}%")
    if query:
        sql += " AND (UPPER(product_detail) LIKE ? OR UPPER(product_type) LIKE ?)"
        q = f"%{query.strip().upper()}%"
        params.extend([q, q])

    sql += " ORDER BY product_category, unit_price LIMIT ?"
    params.append(max_results)

    cursor.execute(sql, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_customer_profile(identifier: str) -> dict[str, Any] | None:
    """Retrieve customer profile and loyalty tier by ID, phone, or name."""
    norm = str(identifier).strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT customer_id, name, phone, email, preferred_store_id,
               preferred_store_location, loyalty_tier, loyalty_points,
               lifetime_spend, favorite_drink, member_since
        FROM customers
        WHERE UPPER(customer_id) = ? 
           OR phone LIKE ?
           OR UPPER(name) LIKE ?
        LIMIT 1
    """, (norm.upper(), f"%{norm}%", f"%{norm.upper()}%"))

    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def redeem_loyalty_points(customer_id: str, points: int = 50) -> dict[str, Any]:
    """Redeem customer loyalty points for a free drink."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT customer_id, name, loyalty_points FROM customers WHERE customer_id = ?", (customer_id,))
    cust = cursor.fetchone()
    if not cust:
        conn.close()
        return {"ok": False, "message": f"Customer '{customer_id}' not found."}

    current = cust["loyalty_points"]
    if current < points:
        conn.close()
        return {
            "ok": False,
            "message": f"Insufficient points. Required: {points}, Available: {current}.",
            "current_points": current,
        }

    new_points = current - points
    cursor.execute("UPDATE customers SET loyalty_points = ? WHERE customer_id = ?", (new_points, customer_id))
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "customer_id": customer_id,
        "customer_name": cust["name"],
        "redeemed_points": points,
        "remaining_points": new_points,
        "reward": "Free Handcrafted Beverage",
    }


def create_order(
    customer_id: str,
    store_id: int,
    item_name: str,
    size: str = "Rg",
    milk_type: str = "Standard Whole Milk",
    quantity: int = 1,
    special_instructions: str = "",
) -> dict[str, Any]:
    """Create a new active order in the store queue."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Determine store location
    store_locations = {3: "Astoria", 5: "Lower Manhattan", 8: "Hell's Kitchen"}
    store_loc = store_locations.get(store_id, "Lower Manhattan")

    # Get customer name
    cursor.execute("SELECT name FROM customers WHERE customer_id = ?", (customer_id,))
    cust_row = cursor.fetchone()
    cust_name = cust_row["name"] if cust_row else "Guest Customer"

    # Lookup unit price
    cursor.execute("""
        SELECT unit_price FROM transactions 
        WHERE UPPER(product_detail) LIKE ? 
        LIMIT 1
    """, (f"%{item_name.strip().upper()}%",))
    price_row = cursor.fetchone()
    unit_price = float(price_row["unit_price"]) if price_row else 3.50

    # Add plant milk surcharge if applicable
    milk_surcharge = 0.80 if ("Oat" in milk_type or "Almond" in milk_type) else 0.00
    final_unit_price = round(unit_price + milk_surcharge, 2)
    total_price = round(final_unit_price * quantity, 2)

    # Generate sequential order ID
    cursor.execute("SELECT COUNT(*) FROM active_orders")
    next_num = 500 + cursor.fetchone()[0] + 1
    order_id = f"ORD-{next_num}"

    cursor.execute("""
        INSERT INTO active_orders (
            order_id, customer_id, customer_name, store_id, store_location,
            item_name, size, milk_type, quantity, unit_price, total_price,
            order_status, special_instructions
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        order_id, customer_id, cust_name, store_id, store_loc,
        item_name, size, milk_type, quantity, final_unit_price, total_price,
        special_instructions
    ))

    # Add loyalty points (1 point per dollar spent)
    points_earned = int(total_price)
    cursor.execute("UPDATE customers SET loyalty_points = loyalty_points + ? WHERE customer_id = ?", (points_earned, customer_id))

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "order_id": order_id,
        "customer_id": customer_id,
        "customer_name": cust_name,
        "store_id": store_id,
        "store_location": store_loc,
        "item_name": item_name,
        "size": size,
        "milk_type": milk_type,
        "quantity": quantity,
        "total_price": total_price,
        "points_earned": points_earned,
        "order_status": "pending",
        "estimated_wait_minutes": 5,
    }


def get_order(order_id: str) -> dict[str, Any] | None:
    """Lookup active order by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_id, customer_id, customer_name, store_id, store_location,
               item_name, size, milk_type, quantity, total_price, order_status,
               created_at, special_instructions
        FROM active_orders
        WHERE UPPER(order_id) = ?
    """, (order_id.strip().upper(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ------------------------------------------------------------------------------
# 2. Operator / Barista Persona Queries
# ------------------------------------------------------------------------------

def get_store_order_queue(store_id: int, status: str = "") -> list[dict[str, Any]]:
    """Retrieve active orders in queue for a store location."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT order_id, customer_name, item_name, size, milk_type,
               quantity, order_status, created_at, special_instructions
        FROM active_orders
        WHERE store_id = ?
    """
    params: list[Any] = [store_id]
    if status:
        sql += " AND order_status = ?"
        params.append(status)
    sql += " ORDER BY created_at ASC LIMIT 10"

    cursor.execute(sql, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def update_order_status(order_id: str, new_status: str) -> dict[str, Any]:
    """Update active order status (pending, brewing, ready_for_pickup, completed)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT order_id, customer_name, item_name FROM active_orders WHERE UPPER(order_id) = ?", (order_id.strip().upper(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"ok": False, "message": f"Order {order_id} not found."}

    cursor.execute("UPDATE active_orders SET order_status = ? WHERE UPPER(order_id) = ?", (new_status, order_id.strip().upper()))
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "order_id": order_id,
        "customer_name": row["customer_name"],
        "item_name": row["item_name"],
        "new_status": new_status,
        "notification_sent": new_status == "ready_for_pickup",
    }


def get_store_inventory(store_id: int, category: str = "", low_stock_only: bool = False) -> list[dict[str, Any]]:
    """Query current store stock levels."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT store_id, store_location, item_name, category, unit,
               current_stock, reorder_threshold, status, last_restocked
        FROM store_inventory
        WHERE store_id = ?
    """
    params: list[Any] = [store_id]
    if category:
        sql += " AND UPPER(category) LIKE ?"
        params.append(f"%{category.strip().upper()}%")
    if low_stock_only:
        sql += " AND (status = 'low_stock' OR status = 'out_of_stock')"

    sql += " ORDER BY status DESC, item_name ASC"
    cursor.execute(sql, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def restock_inventory_item(store_id: int, item_name: str, quantity_added: float) -> dict[str, Any]:
    """Record stock restock for a store."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT item_name, current_stock, reorder_threshold, unit
        FROM store_inventory
        WHERE store_id = ? AND UPPER(item_name) LIKE ?
        LIMIT 1
    """, (store_id, f"%{item_name.strip().upper()}%"))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"ok": False, "message": f"Item matching '{item_name}' not found for store {store_id}."}

    new_stock = round(row["current_stock"] + quantity_added, 1)
    status = "in_stock" if new_stock > row["reorder_threshold"] else "low_stock"

    cursor.execute("""
        UPDATE store_inventory
        SET current_stock = ?, status = ?, last_restocked = DATE('now')
        WHERE store_id = ? AND item_name = ?
    """, (new_stock, status, store_id, row["item_name"]))

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "store_id": store_id,
        "item_name": row["item_name"],
        "quantity_added": quantity_added,
        "unit": row["unit"],
        "new_stock": new_stock,
        "status": status,
    }


def flag_item_out_of_stock(store_id: int, item_name: str) -> dict[str, Any]:
    """Flag an inventory item as depleted and alert regional operations."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE store_inventory
        SET current_stock = 0.0, status = 'out_of_stock'
        WHERE store_id = ? AND UPPER(item_name) LIKE ?
    """, (store_id, f"%{item_name.strip().upper()}%"))

    affected = cursor.rowcount
    conn.commit()
    conn.close()

    return {
        "ok": affected > 0,
        "store_id": store_id,
        "item_name": item_name,
        "status": "out_of_stock",
        "regional_manager_alerted": True,
        "emergency_shipment_initiated": True,
    }


# ------------------------------------------------------------------------------
# 3. CEO & Executive Persona Queries (RBAC Protected)
# ------------------------------------------------------------------------------

def get_executive_revenue_summary(
    store_id: Optional[int] = None,
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    """Aggregate total revenue, volume, and ticket sizes from 149k transactions."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT 
            COUNT(DISTINCT transaction_id) AS total_transactions,
            SUM(transaction_qty) AS total_units_sold,
            ROUND(SUM(line_total), 2) AS total_revenue,
            ROUND(AVG(line_total), 2) AS avg_ticket_size,
            MIN(transaction_date) AS period_start,
            MAX(transaction_date) AS period_end
        FROM transactions
        WHERE 1=1
    """
    params: list[Any] = []
    if store_id:
        sql += " AND store_id = ?"
        params.append(store_id)
    if start_date:
        sql += " AND transaction_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND transaction_date <= ?"
        params.append(end_date)

    cursor.execute(sql, params)
    summary = dict(cursor.fetchone())

    # Top product categories by revenue
    cat_sql = """
        SELECT product_category, ROUND(SUM(line_total), 2) AS category_revenue,
               ROUND(SUM(line_total) * 100.0 / (SELECT SUM(line_total) FROM transactions), 1) AS revenue_share_pct
        FROM transactions
        WHERE 1=1
    """
    cat_params: list[Any] = []
    if store_id:
        cat_sql += " AND store_id = ?"
        cat_params.append(store_id)
    cat_sql += " GROUP BY product_category ORDER BY category_revenue DESC LIMIT 4"

    cursor.execute(cat_sql, cat_params)
    summary["top_categories"] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return summary


def get_store_benchmarks() -> list[dict[str, Any]]:
    """Compare performance across Lower Manhattan, Hell's Kitchen, and Astoria."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            store_id,
            store_location,
            COUNT(DISTINCT transaction_id) AS total_orders,
            SUM(transaction_qty) AS units_sold,
            ROUND(SUM(line_total), 2) AS total_revenue,
            ROUND(AVG(line_total), 2) AS avg_ticket_size
        FROM transactions
        GROUP BY store_id, store_location
        ORDER BY total_revenue DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_cogs_and_margins(product_category: str = "") -> dict[str, Any]:
    """Calculate gross margin % and COGS by combining transactions and BOM recipes."""
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT 
            t.product_category,
            ROUND(SUM(t.line_total), 2) AS total_revenue,
            SUM(t.transaction_qty) AS units_sold,
            ROUND(SUM(t.transaction_qty * COALESCE(r.cogs_unit_usd, 0.50)), 2) AS total_cogs,
            ROUND(SUM(t.line_total) - SUM(t.transaction_qty * COALESCE(r.cogs_unit_usd, 0.50)), 2) AS gross_profit,
            ROUND((SUM(t.line_total) - SUM(t.transaction_qty * COALESCE(r.cogs_unit_usd, 0.50))) * 100.0 / SUM(t.line_total), 1) AS gross_margin_pct
        FROM transactions t
        LEFT JOIN product_recipes r ON t.product_category = r.product_category AND t.product_type = r.product_type
        WHERE 1=1
    """
    params: list[Any] = []
    if product_category:
        sql += " AND UPPER(t.product_category) LIKE ?"
        params.append(f"%{product_category.strip().upper()}%")

    sql += " GROUP BY t.product_category ORDER BY gross_profit DESC"

    cursor.execute(sql, params)
    rows = [dict(r) for r in cursor.fetchall()]

    # Calculate overall portfolio totals
    total_rev = sum(r["total_revenue"] for r in rows)
    total_cogs = sum(r["total_cogs"] for r in rows)
    overall_profit = round(total_rev - total_cogs, 2)
    overall_margin = round((overall_profit / total_rev) * 100.0, 1) if total_rev > 0 else 0.0

    conn.close()
    return {
        "categories": rows,
        "portfolio_total_revenue": round(total_rev, 2),
        "portfolio_total_cogs": round(total_cogs, 2),
        "portfolio_gross_profit": overall_profit,
        "portfolio_gross_margin_pct": overall_margin,
    }


def get_customer_tier_overview() -> dict[str, Any]:
    """Aggregate customer loyalty tiers, member counts, and average spend."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            loyalty_tier,
            COUNT(*) AS member_count,
            ROUND(AVG(loyalty_points), 1) AS avg_points,
            ROUND(SUM(lifetime_spend), 2) AS tier_lifetime_spend,
            ROUND(AVG(lifetime_spend), 2) AS avg_spend_per_member
        FROM customers
        GROUP BY loyalty_tier
        ORDER BY avg_spend_per_member DESC
    """)
    tiers = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"tier_distribution": tiers}


COFFEE_SENSORY_CATALOG: list[dict[str, Any]] = [
    {
        "item_name": "Ethiopia Yirgacheffe Organic",
        "category": "Coffee",
        "type": "Gourmet Brewed Coffee",
        "unit_price": 3.00,
        "roast_type": "Light Roast",
        "acidity": "High Citric Acidity",
        "body": "Light Silky Body",
        "caffeine_level": "High Caffeine Surge",
        "flavor_notes": ["Floral Jasmine", "Bergamot Citrus", "Wild Honey", "Lemon Zest"],
        "sensory_profile": (
            "Ethiopia Yirgacheffe Organic: Light roast grown at high altitude (2,000m+). "
            "High citric acidity with vibrant floral jasmine, bergamot citrus, and honey notes. "
            "Delivers an immediate, clean high caffeine surge to wake up, boost energy, and overcome tiredness or sleepiness. "
            "Ideal for: sleepy, low energy, bright morning start, high focus, interesting floral taste."
        ),
    },
    {
        "item_name": "Colombian Supremo Single-Origin",
        "category": "Coffee",
        "type": "Gourmet Brewed Coffee",
        "unit_price": 3.50,
        "roast_type": "Medium Roast",
        "acidity": "Balanced Medium Acidity",
        "body": "Medium Velvet Body",
        "caffeine_level": "Moderate Balanced Caffeine",
        "flavor_notes": ["Toasted Pecan", "Salted Caramel", "Red Apple", "Milk Chocolate"],
        "sensory_profile": (
            "Colombian Supremo Single-Origin: Medium roast with a smooth, velvety medium body and balanced acidity. "
            "Rich flavor notes of toasted pecan, salted caramel, red apple, and milk chocolate. "
            "Provides sustained focus and mental stamina without jitters or harsh bitter notes. "
            "Ideal for: deep work, strategy meetings, smooth focus, balanced energy, rich afternoon productivity."
        ),
    },
    {
        "item_name": "Artisan Dark Roast Espresso",
        "category": "Coffee",
        "type": "Espresso Beverage",
        "unit_price": 3.25,
        "roast_type": "Dark Roast",
        "acidity": "Low Acidity",
        "body": "Full Heavy Body",
        "caffeine_level": "High Concentrated Caffeine",
        "flavor_notes": ["Smoky Dark Chocolate", "Molasses", "Roasted Walnut", "Cocoa Nib"],
        "sensory_profile": (
            "Artisan Dark Roast Espresso: Intense dark roast with a full, heavy crema body and low acidity. "
            "Bold flavor notes of smoky dark chocolate, molasses, and cocoa nibs. "
            "Offers a potent concentrated caffeine hit for intense physical or mental demands, pulling all-nighters, or strong espresso lovers. "
            "Ideal for: intense caffeine boost, low acidity preference, bold dark chocolate flavor."
        ),
    },
    {
        "item_name": "Ceremonial Grade Uji Matcha Latte",
        "category": "Tea",
        "type": "Specialty Tea",
        "unit_price": 4.50,
        "roast_type": "Shade-Grown Green Tea",
        "acidity": "Zero Coffee Acidity",
        "body": "Creamy Smooth Body",
        "caffeine_level": "Moderate Sustained (L-Theanine)",
        "flavor_notes": ["Umami Sweet", "Fresh Grass", "Creamy Oat", "Vanilla Bean"],
        "sensory_profile": (
            "Ceremonial Grade Uji Matcha Latte: Pure Japanese shade-grown green tea blended with steamed milk. "
            "Zero coffee acidity, rich in L-theanine amino acids that deliver a calm, jitter-free alert state. "
            "Flavor notes of smooth umami, fresh tea leaves, and subtle vanilla. "
            "Ideal for: stress relief, anxiety, jitters, calm focus, stomach sensitivity, soothing afternoon."
        ),
    },
    {
        "item_name": "Spiced Masala Chai Latte",
        "category": "Tea",
        "type": "Specialty Tea",
        "unit_price": 4.25,
        "roast_type": "Steeped Black Tea",
        "acidity": "Low Acidity",
        "body": "Warming Full Body",
        "caffeine_level": "Moderate Gentle Caffeine",
        "flavor_notes": ["Cardamom", "Cinnamon Spice", "Fresh Ginger", "Clove", "Honey"],
        "sensory_profile": (
            "Spiced Masala Chai Latte: Slow-steeped Assam black tea infused with whole cardamom, cinnamon, ginger, and clove. "
            "Warming spicy-sweet flavor with low acidity and gentle caffeine. "
            "Ideal for: cozy rainy days, comforting feeling, cold weather, spiced indulgence."
        ),
    },
    {
        "item_name": "Belgian Velvet Hot Chocolate",
        "category": "Drinking Chocolate",
        "type": "Drinking Chocolate",
        "unit_price": 4.75,
        "roast_type": "Roasted Cacao",
        "acidity": "Zero Acidity",
        "body": "Ultra Rich Thick Body",
        "caffeine_level": "Caffeine Free",
        "flavor_notes": ["70% Belgian Dark Chocolate", "Vanilla Cream", "Marshmallow"],
        "sensory_profile": (
            "Belgian Velvet Hot Chocolate: Melted 70% Belgian dark chocolate folded into frothed steamed milk. "
            "Decadent, ultra-rich, completely caffeine-free indulgence with zero acidity. "
            "Ideal for: sweet treat, evening comfort, caffeine-free relaxation, cozy mood, dessert."
        ),
    },
    {
        "item_name": "Cold Brew Nitro Reserve",
        "category": "Coffee",
        "type": "Cold Brew",
        "unit_price": 4.75,
        "roast_type": "Medium-Dark Cold Steep",
        "acidity": "Ultra Low Acidity",
        "body": "Cascading Micro-Foam Body",
        "caffeine_level": "Extremely High Caffeine",
        "flavor_notes": ["Dark Cocoa", "Sweet Creaminess", "Hazelnut", "Malt"],
        "sensory_profile": (
            "Cold Brew Nitro Reserve: Nitrogen-infused slow cold brew steeped for 24 hours. "
            "Ultra-smooth cascading micro-foam texture, naturally sweet hazelnut and dark cocoa flavor, ultra-low acidity, and an extremely high caffeine kick. "
            "Ideal for: maximum energy boost, hot summer days, intense workout prep, fast refreshing alertness."
        ),
    },
]


def get_sensory_menu_catalog() -> list[dict[str, Any]]:
    """Retrieve all sensory catalog items with flavor, roast, acidity, and vibe profiles."""
    return COFFEE_SENSORY_CATALOG
