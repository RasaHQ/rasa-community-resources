---
name: query_executive_analytics
description: >
  Analyze executive business intelligence including total revenue, order volume,
  average ticket size, multi-store benchmarking across Manhattan, Hell's Kitchen, and Astoria,
  Cost of Goods Sold (COGS), gross margin percentages, and customer lifetime value.
  Activate when the CEO or executive asks for company revenue, sales performance, store comparisons,
  profit margins, COGS, or executive financial reports.
import_tools:
  - fetch_revenue_analytics
  - fetch_store_benchmarks
  - fetch_margin_analytics
  - get_customer_tier_analytics
  - verify_ceo_pin
---

Provide executive financial and operational business intelligence for leadership.

1. **Revenue & Sales Overview**: If the executive asks for total revenue, sales volume, or ticket size, call @tool.fetch_revenue_analytics.
2. **Store Benchmarking**: If the executive asks to compare store performance across Manhattan, Hell's Kitchen, and Astoria, call @tool.fetch_store_benchmarks.
3. **Margins & COGS**: If the executive asks about profit margins, Cost of Goods Sold (COGS), or ingredient cost efficiency, call @tool.fetch_margin_analytics.
4. **Customer Lifetime Value**: If the executive asks about customer tier retention or spend distributions, call @tool.get_customer_tier_analytics.

If any tool reports that CEO authentication is required (auth_required: True), ask the user for their 4-digit Executive Security PIN. When they provide it, call @tool.verify_ceo_pin. Once verified, immediately execute the requested analytics tool to fulfill their request without making them ask again.

When presenting financial figures:
- State total revenue and transaction volume clearly using currency formatting.
- For margins, highlight the overall portfolio gross margin percentage (approximately 81.5%) and compare high-margin categories (Coffee & Espresso at ~86%) with wholesale goods (Bakery at ~64%).
- Keep the executive brief concise, high-impact, and data-backed.
