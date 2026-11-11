# Fixture Data & Public Dataset Citation

All personal identities, customer account records, phone numbers, email addresses, and store inventory records contained within this directory are **entirely fictional and invented** for demonstration, evaluation, and educational purposes.

- **Sales Transactions (`Coffee Shop Sales.xlsx`)**: Eighteen wholly synthetic sales for three demo stores and three demo products over 1–2 September 2026. The workbook is generated only from constants in `scripts/generate_demo_sales.py`, without reading any external dataset. It contains no Kaggle rows, real sales or customer records. The `Transactions` sheet retains the eleven columns the existing importer consumes.
- **Customer Profiles (`customer_profiles.json`)**: All customer names, IDs (`CUST-1001` through `CUST-1100`), phone numbers (`555-01XX`), and reserved email addresses (`*@example.com`) are synthetic fixtures generated for testing loyalty tier logic.
- **Raw Materials & Recipes (`raw_materials_costs.csv`, `product_recipes.csv`)**: Invented bill-of-materials and ingredient unit costs used to demonstrate Cost-of-Goods-Sold (COGS) and gross margin calculations.
- **Store Inventory (`store_inventory.json`)**: Mock stock balance levels across simulated store locations.

No real-world personally identifiable information (PII), customer data, or proprietary commercial secrets are present.

## Reproduce the sales fixture

From this project directory, run:

```sh
python scripts/generate_demo_sales.py
uv run --locked python -m unittest discover -s tests -p 'test_synthetic_sales.py'
```

The generator uses only the Python standard library and fixed ZIP metadata.
Regeneration must reproduce the committed workbook bytes. The consumer test
imports it into a temporary SQLite database and checks menu lookup and revenue:
18 transactions, 81 demo dollars total, 27 per store. These are invented test
values, not business measurements. The existing database is left untouched.

The replacement resolves the earlier workbook's missing reuse licence; no
licence for that third-party workbook is asserted. Samrudha Kelkar remains
credited for the coffee-shop project. Earlier evaluation reports predate this
fixture and pin change; their results do not qualify the replacement.
