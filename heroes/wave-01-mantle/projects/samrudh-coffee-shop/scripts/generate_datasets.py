#!/usr/bin/env python3
"""Generate synthetic Customer Profiles, Raw Material Costs, Recipes/BOM, and Store Inventory."""

from __future__ import annotations

import json
import random
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def generate_raw_materials_and_recipes():
    """Create raw material cost ledger and recipe bill-of-materials (BOM)."""
    raw_materials = [
        {"material_id": "MAT_BEANS_ETHIOPIA", "name": "Ethiopia Yirgacheffe Specialty Beans", "category": "Beans", "unit": "kg", "cost_per_unit": 16.50},
        {"material_id": "MAT_BEANS_COLOMBIA", "name": "Colombian Supremo Specialty Beans", "category": "Beans", "unit": "kg", "cost_per_unit": 14.20},
        {"material_id": "MAT_BEANS_HOUSE", "name": "Artisan Diner House Blend Roasted Beans", "category": "Beans", "unit": "kg", "cost_per_unit": 11.50},
        {"material_id": "MAT_BEANS_DECAF", "name": "Swiss Water Decaf Organic Beans", "category": "Beans", "unit": "kg", "cost_per_unit": 15.00},
        {"material_id": "MAT_MILK_WHOLE", "name": "Farm Fresh Whole Milk", "category": "Dairy", "unit": "gal", "cost_per_unit": 3.80},
        {"material_id": "MAT_MILK_OAT", "name": "Barista Edition Oat Milk", "category": "Plant Milk", "unit": "gal", "cost_per_unit": 5.40},
        {"material_id": "MAT_MILK_ALMOND", "name": "Unsweetened Almond Milk", "category": "Plant Milk", "unit": "gal", "cost_per_unit": 4.90},
        {"material_id": "MAT_TEA_CHAI", "name": "Spiced Masala Chai Concentrate", "category": "Tea", "unit": "liter", "cost_per_unit": 4.50},
        {"material_id": "MAT_TEA_LOOSE", "name": "Organic Loose Leaf Teas (Herbal/Black/Green)", "category": "Tea", "unit": "kg", "cost_per_unit": 22.00},
        {"material_id": "MAT_CHOC_DARK", "name": "Dutch Cocoa & Dark Chocolate Drops", "category": "Chocolate", "unit": "kg", "cost_per_unit": 9.20},
        {"material_id": "MAT_SYRUP_CARAMEL", "name": "Artisan Caramel Syrup", "category": "Flavours", "unit": "bottle_750ml", "cost_per_unit": 7.50},
        {"material_id": "MAT_SYRUP_HAZELNUT", "name": "Roasted Hazelnut Syrup", "category": "Flavours", "unit": "bottle_750ml", "cost_per_unit": 7.50},
        {"material_id": "MAT_SYRUP_VANILLA", "name": "Madagascar Vanilla Syrup", "category": "Flavours", "unit": "bottle_750ml", "cost_per_unit": 8.00},
        {"material_id": "MAT_BAKERY_SCONE", "name": "Handmade Artisan Scone (Wholesale)", "category": "Bakery", "unit": "piece", "cost_per_unit": 1.25},
        {"material_id": "MAT_BAKERY_PASTRY", "name": "Butter Croissant / Danish (Wholesale)", "category": "Bakery", "unit": "piece", "cost_per_unit": 1.40},
        {"material_id": "MAT_BAKERY_BISCOTTI", "name": "Almond Biscotti (Wholesale)", "category": "Bakery", "unit": "piece", "cost_per_unit": 0.95},
        {"material_id": "MAT_PACKAGING_CUP", "name": "Biodegradable Hot Cup + Lid + Sleeve", "category": "Packaging", "unit": "set", "cost_per_unit": 0.22},
    ]

    df_mat = pd.DataFrame(raw_materials)
    mat_csv = DATA_DIR / "raw_materials_costs.csv"
    df_mat.to_csv(mat_csv, index=False)
    print(f"✓ Created {mat_csv.name} ({len(df_mat)} raw ingredients)")

    # Recipes mapping each product category/type to estimated COGS
    recipes = [
        {"product_category": "Coffee", "product_type": "Gourmet brewed coffee", "primary_material": "MAT_BEANS_ETHIOPIA", "cogs_unit_usd": 0.42, "typical_margin_pct": 86.0},
        {"product_category": "Coffee", "product_type": "Drip coffee", "primary_material": "MAT_BEANS_HOUSE", "cogs_unit_usd": 0.28, "typical_margin_pct": 88.5},
        {"product_category": "Coffee", "product_type": "Barista Espresso", "primary_material": "MAT_BEANS_ETHIOPIA", "cogs_unit_usd": 0.65, "typical_margin_pct": 84.7},
        {"product_category": "Tea", "product_type": "Brewed Chai tea", "primary_material": "MAT_TEA_CHAI", "cogs_unit_usd": 0.55, "typical_margin_pct": 81.0},
        {"product_category": "Tea", "product_type": "Brewed herbal tea", "primary_material": "MAT_TEA_LOOSE", "cogs_unit_usd": 0.35, "typical_margin_pct": 87.0},
        {"product_category": "Tea", "product_type": "Brewed Black tea", "primary_material": "MAT_TEA_LOOSE", "cogs_unit_usd": 0.32, "typical_margin_pct": 88.0},
        {"product_category": "Drinking Chocolate", "product_type": "Hot chocolate", "primary_material": "MAT_CHOC_DARK", "cogs_unit_usd": 0.78, "typical_margin_pct": 80.5},
        {"product_category": "Bakery", "product_type": "Scone", "primary_material": "MAT_BAKERY_SCONE", "cogs_unit_usd": 1.25, "typical_margin_pct": 64.0},
        {"product_category": "Bakery", "product_type": "Pastry", "primary_material": "MAT_BAKERY_PASTRY", "cogs_unit_usd": 1.40, "typical_margin_pct": 62.0},
        {"product_category": "Bakery", "product_type": "Biscotti", "primary_material": "MAT_BAKERY_BISCOTTI", "cogs_unit_usd": 0.95, "typical_margin_pct": 71.0},
        {"product_category": "Flavours", "product_type": "Regular syrup", "primary_material": "MAT_SYRUP_CARAMEL", "cogs_unit_usd": 0.12, "typical_margin_pct": 85.0},
        {"product_category": "Flavours", "product_type": "Sugar free syrup", "primary_material": "MAT_SYRUP_VANILLA", "cogs_unit_usd": 0.14, "typical_margin_pct": 82.5},
        {"product_category": "Coffee beans", "product_type": "Gourmet Beans", "primary_material": "MAT_BEANS_ETHIOPIA", "cogs_unit_usd": 7.50, "typical_margin_pct": 65.0},
        {"product_category": "Coffee beans", "product_type": "Organic Beans", "primary_material": "MAT_BEANS_DECAF", "cogs_unit_usd": 8.00, "typical_margin_pct": 71.4},
        {"product_category": "Loose Tea", "product_type": "Herbal tea", "primary_material": "MAT_TEA_LOOSE", "cogs_unit_usd": 2.80, "typical_margin_pct": 68.7},
        {"product_category": "Loose Tea", "product_type": "Chai tea", "primary_material": "MAT_TEA_CHAI", "cogs_unit_usd": 3.00, "typical_margin_pct": 68.4},
        {"product_category": "Packaged Chocolate", "product_type": "Drinking Chocolate", "primary_material": "MAT_CHOC_DARK", "cogs_unit_usd": 2.20, "typical_margin_pct": 65.6},
        {"product_category": "Branded", "product_type": "Housewares", "primary_material": "MAT_PACKAGING_CUP", "cogs_unit_usd": 4.50, "typical_margin_pct": 67.8},
    ]

    df_rec = pd.DataFrame(recipes)
    rec_csv = DATA_DIR / "product_recipes.csv"
    df_rec.to_csv(rec_csv, index=False)
    print(f"✓ Created {rec_csv.name} ({len(df_rec)} recipes)")


def generate_customer_profiles():
    """Create 100 realistic customer profiles with loyalty tiers and points."""
    first_names = [
        "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "William", "Sophia", "Lucas", "Isabella",
        "Mason", "Mia", "Ethan", "Charlotte", "Oliver", "Amelia", "Aiden", "Harper", "Elijah", "Evelyn",
        "Alexander", "Abigail", "Daniel", "Emily", "Henry", "Elizabeth", "Matthew", "Mila", "Jackson", "Ella",
        "Sebastian", "Avery", "David", "Sofia", "Carter", "Camila", "Wyatt", "Aria", "Jayden", "Scarlett",
        "John", "Victoria", "Owen", "Madison", "Dylan", "Luna", "Luke", "Grace", "Gabriel", "Chloe"
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson"
    ]

    favorite_drinks = [
        "Ethiopia Rg", "Spicy Eye Opener Chai Lg", "Our Old Time Diner Blend Sm", "Dark chocolate Lg",
        "Barista Espresso", "Morning Sunrise Chai", "Oatmeal Scone", "Carmel syrup Latte"
    ]

    stores = [
        {"id": 3, "location": "Astoria"},
        {"id": 5, "location": "Lower Manhattan"},
        {"id": 8, "location": "Hell's Kitchen"},
    ]

    random.seed(42)
    profiles = []

    # Dedicated test persona customers for deterministic testing
    profiles.append({
        "customer_id": "CUST-1001",
        "name": "Sarah Jenkins",
        "phone": "+1-212-555-0144",
        "email": "sarah.jenkins@example.com",
        "preferred_store_id": 5,
        "preferred_store_location": "Lower Manhattan",
        "loyalty_tier": "Gold",
        "loyalty_points": 145,
        "lifetime_spend": 820.50,
        "favorite_drink": "Ethiopia Rg",
        "member_since": "2022-04-15"
    })
    profiles.append({
        "customer_id": "CUST-1002",
        "name": "Marcus Vance",
        "phone": "+1-718-555-0199",
        "email": "marcus.vance@example.com",
        "preferred_store_id": 3,
        "preferred_store_location": "Astoria",
        "loyalty_tier": "Silver",
        "loyalty_points": 35,
        "lifetime_spend": 240.00,
        "favorite_drink": "Spicy Eye Opener Chai Lg",
        "member_since": "2023-01-10"
    })
    profiles.append({
        "customer_id": "CUST-1003",
        "name": "Elena Rostova",
        "phone": "+1-212-555-0182",
        "email": "elena.r@example.com",
        "preferred_store_id": 8,
        "preferred_store_location": "Hell's Kitchen",
        "loyalty_tier": "Regular",
        "loyalty_points": 12,
        "lifetime_spend": 68.00,
        "favorite_drink": "Dark chocolate Lg",
        "member_since": "2023-05-02"
    })

    for i in range(1004, 1101):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        store = random.choice(stores)
        tier = random.choices(["Regular", "Silver", "Gold"], weights=[0.60, 0.28, 0.12])[0]

        if tier == "Gold":
            points = random.randint(100, 350)
            spend = round(random.uniform(500, 1500), 2)
        elif tier == "Silver":
            points = random.randint(30, 95)
            spend = round(random.uniform(150, 480), 2)
        else:
            points = random.randint(0, 29)
            spend = round(random.uniform(15, 140), 2)

        profiles.append({
            "customer_id": f"CUST-{i}",
            "name": f"{fn} {ln}",
            "phone": f"+1-212-555-{random.randint(1000, 9999)}",
            "email": f"{fn.lower()}.{ln.lower()}@example.com",
            "preferred_store_id": store["id"],
            "preferred_store_location": store["location"],
            "loyalty_tier": tier,
            "loyalty_points": points,
            "lifetime_spend": spend,
            "favorite_drink": random.choice(favorite_drinks),
            "member_since": f"2023-0{random.randint(1, 6)}-{random.randint(10, 28)}"
        })

    cust_json = DATA_DIR / "customer_profiles.json"
    with open(cust_json, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)
    print(f"✓ Created {cust_json.name} ({len(profiles)} customer accounts)")


def generate_store_inventory():
    """Create multi-store stock levels for Astoria, Lower Manhattan, and Hell's Kitchen."""
    stores = [
        {"store_id": 3, "store_location": "Astoria"},
        {"store_id": 5, "store_location": "Lower Manhattan"},
        {"store_id": 8, "store_location": "Hell's Kitchen"},
    ]

    base_items = [
        {"item_name": "Ethiopia Yirgacheffe Beans", "category": "Beans", "unit": "kg", "threshold": 10.0, "normal_qty": 35.0},
        {"item_name": "Colombian Supremo Beans", "category": "Beans", "unit": "kg", "threshold": 10.0, "normal_qty": 40.0},
        {"item_name": "Artisan Diner House Blend", "category": "Beans", "unit": "kg", "threshold": 15.0, "normal_qty": 60.0},
        {"item_name": "Decaf Organic Beans", "category": "Beans", "unit": "kg", "threshold": 5.0, "normal_qty": 18.0},
        {"item_name": "Whole Milk", "category": "Dairy", "unit": "gal", "threshold": 8.0, "normal_qty": 25.0},
        {"item_name": "Barista Oat Milk", "category": "Plant Milk", "unit": "gal", "threshold": 6.0, "normal_qty": 20.0},
        {"item_name": "Almond Milk", "category": "Plant Milk", "unit": "gal", "threshold": 5.0, "normal_qty": 15.0},
        {"item_name": "Masala Chai Concentrate", "category": "Tea", "unit": "liter", "threshold": 6.0, "normal_qty": 22.0},
        {"item_name": "Dark Chocolate Drops", "category": "Chocolate", "unit": "kg", "threshold": 5.0, "normal_qty": 16.0},
        {"item_name": "Caramel Syrup", "category": "Flavours", "unit": "bottle", "threshold": 3.0, "normal_qty": 10.0},
        {"item_name": "Hazelnut Syrup", "category": "Flavours", "unit": "bottle", "threshold": 3.0, "normal_qty": 10.0},
        {"item_name": "Madagascar Vanilla Syrup", "category": "Flavours", "unit": "bottle", "threshold": 3.0, "normal_qty": 12.0},
        {"item_name": "Oatmeal Scones", "category": "Bakery", "unit": "units", "threshold": 8.0, "normal_qty": 24.0},
        {"item_name": "Butter Croissants", "category": "Bakery", "unit": "units", "threshold": 8.0, "normal_qty": 30.0},
        {"item_name": "Hot Cups & Lids (12oz/16oz)", "category": "Packaging", "unit": "sleeves", "threshold": 10.0, "normal_qty": 50.0},
    ]

    inventory = []
    for store in stores:
        for itm in base_items:
            # Seed some realistic low-stock variations for operator persona testing
            if store["store_id"] == 8 and "Oat Milk" in itm["item_name"]:
                # Hell's Kitchen low on Oat Milk
                curr = 2.0
            elif store["store_id"] == 5 and "Caramel Syrup" in itm["item_name"]:
                # Manhattan low on caramel
                curr = 1.0
            elif store["store_id"] == 3 and "Ethiopia" in itm["item_name"]:
                # Astoria low on Ethiopia
                curr = 4.5
            else:
                curr = round(itm["normal_qty"] * random.uniform(0.7, 1.2), 1)

            status = "out_of_stock" if curr <= 0 else ("low_stock" if curr <= itm["threshold"] else "in_stock")

            inventory.append({
                "store_id": store["store_id"],
                "store_location": store["store_location"],
                "item_name": itm["item_name"],
                "category": itm["category"],
                "unit": itm["unit"],
                "current_stock": curr,
                "reorder_threshold": itm["threshold"],
                "status": status,
                "last_restocked": "2023-06-28"
            })

    inv_json = DATA_DIR / "store_inventory.json"
    with open(inv_json, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2)
    print(f"✓ Created {inv_json.name} ({len(inventory)} inventory entries across 3 stores)")


if __name__ == "__main__":
    generate_raw_materials_and_recipes()
    generate_customer_profiles()
    generate_store_inventory()
    print("✨ All synthetic datasets generated successfully.")
