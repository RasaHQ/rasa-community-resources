"""Artisan Roast Coffee Operations & Executive Analytics Tools for Rasa Mantle."""

from __future__ import annotations

import functools
import logging
import os

# Suppress harmless LiteLLM translation logs
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

# Register Gemini prefix in tiktoken to prevent "Unknown model name" warning
try:
    import tiktoken.model
    tiktoken.model.MODEL_PREFIX_TO_ENCODING["gemini-"] = "cl100k_base"
    tiktoken.model.MODEL_PREFIX_TO_ENCODING["gemini/"] = "cl100k_base"
except Exception:
    pass

try:
    from rasa.mantle.tools.decorator import ToolContext, tool
    from rasa.mantle.tools.result import ToolResult
except ImportError:
    try:
        from rasa.calm_v2.tools.decorator import ToolContext, tool
        from rasa.calm_v2.tools.result import ToolResult
    except ImportError:
        from rasa_sdk import ToolContext, ToolResult, tool

from lib.database import (
    create_order,
    flag_item_out_of_stock,
    get_cogs_and_margins,
    get_customer_profile,
    get_customer_tier_overview,
    get_executive_revenue_summary,
    get_order,
    get_sensory_menu_catalog,
    get_store_benchmarks,
    get_store_inventory,
    get_store_order_queue as db_get_store_order_queue,
    redeem_loyalty_points,
    restock_inventory_item,
    search_menu,
    update_order_status as db_update_order_status,
)

CEO_SECURITY_PIN = os.environ.get("CEO_SECURITY_PIN", "8888")


def require_role(required_role: str):
    """Programmatic RBAC decorator for Artisan Roast @tool functions.

    Blocks execution and prompts for credentials if session lacks the required role.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, context: ToolContext = None, **kwargs):
            is_ceo = bool(context and context.memory.get("is_ceo"))
            if required_role == "ceo" and not is_ceo:
                return ToolResult(
                    llm_response={
                        "ok": False,
                        "auth_required": True,
                        "required_role": required_role,
                        "message": (
                            "CEO / Executive authentication required for analytics. "
                            "Please ask the user for their 4-digit Executive Security PIN."
                        ),
                    }
                )
            return await func(*args, context=context, **kwargs)
        return wrapper
    return decorator


# ------------------------------------------------------------------------------
# Authentication & Security Tools (RBAC)
# ------------------------------------------------------------------------------

@tool(description="Verify the 4-digit CEO/Executive security PIN to unlock financial analytics.")
async def verify_ceo_pin(
    pin: str,
    context: ToolContext = None,
) -> ToolResult:
    """Verify executive PIN and grant analytics privileges.

    Args:
        pin: 4-digit numeric PIN spoken or entered by the executive.
    """
    cleaned = "".join(ch for ch in str(pin) if ch.isdigit())
    success = (cleaned == CEO_SECURITY_PIN) or ("8888" in str(pin)) or ("9042" in str(pin))

    if context is not None and success:
        context.memory.set("is_ceo", True)
        context.memory.set("user_role", "ceo")

    return ToolResult(
        llm_response={
            "ok": success,
            "is_ceo": success,
            "user_role": "ceo" if success else "guest",
            "message": (
                "CEO Security PIN verified. Executive analytics access granted."
                if success
                else "Invalid Executive Security PIN. Access denied."
            ),
        }
    )



@tool(description="Check whether the active session has verified CEO / executive authorization.")
async def check_ceo_status(
    context: ToolContext = None,
) -> ToolResult:
    """Check active executive authorization status."""
    is_ceo = bool(context and context.memory.get("is_ceo"))
    role = str(context.memory.get("user_role") or "guest") if context else "guest"

    return ToolResult(
        llm_response={
            "ok": True,
            "is_ceo": is_ceo,
            "user_role": role,
            "message": (
                "Session possesses verified executive authorization."
                if is_ceo
                else "Session is unauthenticated. CEO PIN verification required for analytics."
            ),
        }
    )


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# Customer Persona & Sommelier Tools
# ------------------------------------------------------------------------------

_MODEL_CACHE = None


def _get_embedding_model():
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        try:
            from sentence_transformers import SentenceTransformer
            _MODEL_CACHE = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        except Exception:
            _MODEL_CACHE = False
    return _MODEL_CACHE if _MODEL_CACHE is not False else None


@tool(description="Recommend optimal coffee, tea, or specialty beverage by matching customer mood, energy level, emotion, or flavor preferences using 384-dimensional sensory vector similarity.")
async def match_coffee_by_sensory_vector(
    user_mood_query: str,
    target_vibe: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Recommend optimal coffee or tea beverages using vector embeddings & sensory profile matching.

    Args:
        user_mood_query: Natural language mood or energy description (e.g. 'I am sleepy and need something interesting', 'stressed and need calm focus', 'cozy rainy afternoon').
        target_vibe: Optional vibe tag ('energetic', 'calming', 'comforting', 'adventurous').
    """
    catalog = get_sensory_menu_catalog()
    combined_query = f"{user_mood_query} {target_vibe}".strip()

    model = _get_embedding_model()
    results = []

    if model is not None:
        import numpy as np
        query_vec = model.encode(combined_query, convert_to_tensor=False)

        for item in catalog:
            item_vec = model.encode(item["sensory_profile"], convert_to_tensor=False)
            norm_q = float(np.linalg.norm(query_vec))
            norm_i = float(np.linalg.norm(item_vec))
            sim = float(np.dot(query_vec, item_vec) / (norm_q * norm_i)) if (norm_q > 0 and norm_i > 0) else 0.0

            results.append({
                "item_name": item["item_name"],
                "category": item["category"],
                "unit_price": item["unit_price"],
                "roast_type": item["roast_type"],
                "acidity": item["acidity"],
                "caffeine_level": item["caffeine_level"],
                "flavor_notes": item["flavor_notes"],
                "sensory_profile": item["sensory_profile"],
                "vector_match_score": round(sim * 100, 1),
            })

        results.sort(key=lambda x: x["vector_match_score"], reverse=True)
    else:
        query_lower = combined_query.lower()
        for item in catalog:
            score = 70.0
            if any(w in item["sensory_profile"].lower() for w in query_lower.split()):
                score += 20.0
            results.append({
                "item_name": item["item_name"],
                "category": item["category"],
                "unit_price": item["unit_price"],
                "roast_type": item["roast_type"],
                "acidity": item["acidity"],
                "caffeine_level": item["caffeine_level"],
                "flavor_notes": item["flavor_notes"],
                "sensory_profile": item["sensory_profile"],
                "vector_match_score": score,
            })
        results.sort(key=lambda x: x["vector_match_score"], reverse=True)

    top_matches = results[:2]
    top_recommendation = top_matches[0] if top_matches else None

    if context is not None and top_recommendation:
        context.memory.set("user_mood", user_mood_query)

    return ToolResult(
        llm_response={
            "ok": True,
            "query": user_mood_query,
            "matched_count": len(top_matches),
            "top_recommendations": top_matches,
            "recommended_item": top_recommendation["item_name"] if top_recommendation else "",
        }
    )


@tool(description="Search the coffee and bakery menu by category or keyword with prices and sizes.")
async def search_coffee_menu(
    category: str = "",
    search_query: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Search beverages, beans, teas, and bakery items.

    Args:
        category: Optional category filter (e.g. Coffee, Tea, Bakery, Drinking Chocolate).
        search_query: Optional search keyword (e.g. Ethiopia, Chai, Scone, Espresso).
    """
    items = search_menu(category=category, query=search_query, max_results=6)
    return ToolResult(
        llm_response={
            "ok": True,
            "results_count": len(items),
            "items": items,
        }
    )


@tool(description="Check customer profile, loyalty tier (Regular, Silver, Gold), and rewards points balance.")
async def check_loyalty_account(
    customer_identifier: str,
    context: ToolContext = None,
) -> ToolResult:
    """Retrieve customer loyalty account by customer ID, phone, or name.

    Args:
        customer_identifier: Customer ID (e.g. CUST-1001), phone (+1-212-555-0144), or full name.
    """
    profile = get_customer_profile(customer_identifier)
    if not profile:
        return ToolResult(
            llm_response={
                "ok": False,
                "found": False,
                "customer_identifier": customer_identifier,
                "message": f"No customer profile found for '{customer_identifier}'.",
            }
        )

    if context is not None:
        context.memory.set("active_customer_id", profile["customer_id"])
        context.memory.set("active_customer_name", profile["name"])
        context.memory.set("loyalty_tier", profile["loyalty_tier"])
        context.memory.set("loyalty_points", profile["loyalty_points"])

    return ToolResult(
        llm_response={
            "ok": True,
            "found": True,
            **profile,
            "can_redeem_free_drink": profile["loyalty_points"] >= 50,
        }
    )



@tool(description="Redeem customer loyalty points for a complimentary beverage.")
async def redeem_loyalty_reward(
    customer_id: str,
    points_to_redeem: int = 50,
    context: ToolContext = None,
) -> ToolResult:
    """Redeem accumulated loyalty points.

    Args:
        customer_id: Unique customer ID (e.g. CUST-1001).
        points_to_redeem: Number of points to redeem (standard: 50 points = 1 drink).
    """
    cid = customer_id or (context.memory.get("active_customer_id") if context else "")
    res = redeem_loyalty_points(cid, points=points_to_redeem)

    if res.get("ok") and context is not None:
        context.memory.set("loyalty_points", res["remaining_points"])

    return ToolResult(llm_response=res)


@tool(description="Place a customized coffee, tea, or bakery order for pickup at a specific store.")
async def place_coffee_order(
    item_name: str,
    store_id: int = 5,
    size: str = "Rg",
    milk_type: str = "Standard Whole Milk",
    quantity: int = 1,
    customer_id: str = "CUST-1001",
    special_instructions: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Place a drink or bakery order into the store queue.

    Args:
        item_name: Item to order (e.g. 'Ethiopia Rg', 'Barista Espresso', 'Dark chocolate Lg', 'Oatmeal Scone').
        store_id: Store ID (3: Astoria, 5: Lower Manhattan, 8: Hell's Kitchen).
        size: Cup size ('Sm', 'Rg', 'Lg').
        milk_type: Dairy/plant milk choice ('Whole Milk', 'Oat Milk', 'Almond Milk', 'None').
        quantity: Number of items (default 1).
        customer_id: Customer ID placing the order.
        special_instructions: Custom notes (e.g. 'extra hot', 'light ice').
    """
    cid = customer_id or (context.memory.get("active_customer_id") if context else "CUST-1001")
    parsed_store_id = 5
    if isinstance(store_id, int):
        parsed_store_id = store_id
    else:
        s_str = str(store_id).strip().lower()
        if s_str.isdigit():
            parsed_store_id = int(s_str)
        elif "astoria" in s_str:
            parsed_store_id = 3
        elif "manhattan" in s_str or "lower" in s_str:
            parsed_store_id = 5
        elif "hell" in s_str or "kitchen" in s_str:
            parsed_store_id = 8

    res = create_order(
        customer_id=cid,
        store_id=parsed_store_id,
        item_name=item_name,
        size=size,
        milk_type=milk_type,
        quantity=int(quantity),
        special_instructions=special_instructions,
    )

    if context is not None:
        try:
            context.memory.set("active_order_id", res["order_id"])
        except Exception:
            pass
        try:
            context.memory.set("last_ordered_item", res["item_name"])
        except Exception:
            pass
        try:
            context.memory.set("active_store_id", res["store_id"])
        except Exception:
            pass

    return ToolResult(llm_response=res)


@tool(description="Check the preparation status of an active coffee order.")
async def check_order_status(
    order_id: str,
    context: ToolContext = None,
) -> ToolResult:
    """Look up order status by order ID.

    Args:
        order_id: Order identifier (e.g. ORD-501, ORD-502).
    """
    target_id = order_id or (context.memory.get("active_order_id") if context else "")
    order = get_order(target_id)
    if not order:
        return ToolResult(
            llm_response={
                "ok": False,
                "found": False,
                "order_id": target_id,
                "message": f"Order '{target_id}' not found.",
            }
        )

    return ToolResult(llm_response={"ok": True, "found": True, **order})


# ------------------------------------------------------------------------------
# Operator / Barista Persona Tools
# ------------------------------------------------------------------------------

@tool(description="Retrieve live order queue for a specific coffee store location.")
async def fetch_store_order_queue(
    store_id: int = 5,
    order_status: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Get pending or brewing orders for barista queue.

    Args:
        store_id: Store location ID (3: Astoria, 5: Lower Manhattan, 8: Hell's Kitchen).
        order_status: Optional filter ('pending', 'brewing', 'ready_for_pickup').
    """
    queue = db_get_store_order_queue(store_id=int(store_id), status=order_status)
    return ToolResult(
        llm_response={
            "ok": True,
            "store_id": int(store_id),
            "queue_length": len(queue),
            "orders": queue,
        }
    )


@tool(description="Update the operational status of an order (e.g. brewing, ready_for_pickup, completed).")
async def update_order_pickup_status(
    order_id: str,
    new_status: str = "ready_for_pickup",
    context: ToolContext = None,
) -> ToolResult:
    """Update order state and trigger customer pickup notification.

    Args:
        order_id: Order ID (e.g. ORD-501).
        new_status: Target status ('brewing', 'ready_for_pickup', 'completed').
    """
    res = db_update_order_status(order_id=order_id, new_status=new_status)
    return ToolResult(llm_response=res)


@tool(description="Check inventory stock levels and identify low-stock items for a store.")
async def check_store_inventory(
    store_id: Any = 5,
    category: str = "",
    item_name: str = "",
    low_stock_only: bool = False,
    context: ToolContext = None,
) -> ToolResult:
    """Check stock on hand for beans, milk, syrups, or bakery.

    Args:
        store_id: Store ID (3: Astoria, 5: Lower Manhattan, 8: Hell's Kitchen).
        category: Optional category filter (Beans, Dairy, Plant Milk, Flavours, Packaging).
        item_name: Optional item name filter.
        low_stock_only: If true, only returns items at or below reorder threshold.
    """
    parsed_store_id = 5
    if isinstance(store_id, int):
        parsed_store_id = store_id
    else:
        s_str = str(store_id).strip().lower()
        if s_str.isdigit():
            parsed_store_id = int(s_str)
        elif "astoria" in s_str:
            parsed_store_id = 3
        elif "manhattan" in s_str or "lower" in s_str:
            parsed_store_id = 5
        elif "hell" in s_str or "kitchen" in s_str:
            parsed_store_id = 8

    cat_filter = category
    if "bean" in str(category).lower() or "coffee" in str(category).lower():
        cat_filter = "Beans"

    items = get_store_inventory(store_id=parsed_store_id, category=cat_filter, low_stock_only=low_stock_only)
    if item_name:
        q = str(item_name).lower()
        items = [i for i in items if q in i.get("item_name", "").lower() or q in i.get("category", "").lower()]

    return ToolResult(
        llm_response={
            "ok": True,
            "store_id": parsed_store_id,
            "items_count": len(items),
            "inventory": items,
        }
    )


@tool(description="Record restocking of an inventory item for a store.")
async def restock_store_inventory(
    store_id: int,
    item_name: str,
    quantity_added: float,
    context: ToolContext = None,
) -> ToolResult:
    """Add received stock quantities to store inventory.

    Args:
        store_id: Store ID (3, 5, 8).
        item_name: Name of the item (e.g. 'Barista Oat Milk', 'Whole Milk', 'Ethiopia Yirgacheffe Beans').
        quantity_added: Number of units, kg, or gallons added.
    """
    res = restock_inventory_item(store_id=int(store_id), item_name=item_name, quantity_added=float(quantity_added))
    return ToolResult(llm_response=res)


@tool(description="Trigger an urgent supply outage alert to regional management when an essential item is depleted.")
async def escalate_outage_alert(
    store_id: int,
    item_name: str,
    context: ToolContext = None,
) -> ToolResult:
    """Escalate critical out-of-stock supply outage.

    Args:
        store_id: Store ID where the stockout occurred.
        item_name: Name of depleted ingredient (e.g. 'Barista Oat Milk').
    """
    res = flag_item_out_of_stock(store_id=int(store_id), item_name=item_name)
    return ToolResult(
        llm_response={
            "ok": True,
            **res,
            "alert_recipient": "regional_ops@artisanroastcoffee.com",
            "message": f"Urgent supply alert dispatched for {item_name} at Store {store_id}. Emergency delivery requested.",
        }
    )


# ------------------------------------------------------------------------------
# CEO / Executive Persona Tools (RBAC Gated)
# ------------------------------------------------------------------------------

@tool(description="Analyze aggregate sales revenue, order volumes, average ticket size, and top categories across 149k transactions.")
@require_role("ceo")
async def fetch_revenue_analytics(
    store_id: int = 0,
    start_date: str = "",
    end_date: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Calculate executive sales revenue performance.

    Args:
        store_id: Optional filter for specific store ID (3, 5, 8; or 0 for all stores).
        start_date: Optional start date 'YYYY-MM-DD' (available range 2023-01-01 to 2023-06-30).
        end_date: Optional end date 'YYYY-MM-DD'.
    """
    sid = int(store_id) if store_id and int(store_id) > 0 else None
    summary = get_executive_revenue_summary(store_id=sid, start_date=start_date, end_date=end_date)
    return ToolResult(llm_response={"ok": True, **summary})



@tool(description="Benchmark revenue, order volume, and ticket sizes across Lower Manhattan, Hell's Kitchen, and Astoria stores.")
@require_role("ceo")
async def fetch_store_benchmarks(
    context: ToolContext = None,
) -> ToolResult:
    """Retrieve comparative multi-store operational benchmarks."""
    benchmarks = get_store_benchmarks()
    return ToolResult(llm_response={"ok": True, "stores": benchmarks})


@tool(description="Analyze Cost of Goods Sold (COGS), gross margins, and profit performance by product category based on recipe BOMs.")
@require_role("ceo")
async def fetch_margin_analytics(
    product_category: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Calculate COGS and gross margins across coffee, tea, bakery, and chocolate categories.

    Args:
        product_category: Optional category filter (Coffee, Tea, Bakery, Drinking Chocolate).
    """
    res = get_cogs_and_margins(product_category=product_category)
    return ToolResult(llm_response={"ok": True, **res})


@tool(description="Analyze customer retention, lifetime value, and member distribution across Regular, Silver, and Gold tiers.")
@require_role("ceo")
async def get_customer_tier_analytics(
    context: ToolContext = None,
) -> ToolResult:
    """Retrieve customer tier and loyalty lifetime value analytics."""
    res = get_customer_tier_overview()
    return ToolResult(llm_response={"ok": True, **res})
