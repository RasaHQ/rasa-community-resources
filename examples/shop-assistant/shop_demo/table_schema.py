"""Spreadsheet columns and initial rows, defined by Pydantic models."""
from pydantic import Field

from .models import Record


class ProductRow(Record):
    code: str = Field(alias="Code")
    product: str = Field(alias="Product")
    price_cents: int = Field(alias="PriceCents", ge=0)
    stock: int = Field(alias="Stock", ge=0)


class OrderRow(Record):
    number: str = Field(alias="OrderNumber")
    quote_json: str = Field(alias="QuoteJson")
    total_cents: int = Field(alias="TotalCents", ge=0)
    currency: str = Field(alias="Currency")
    status: str = Field(alias="Status")
    created_utc: str = Field(alias="CreatedUTC")
    request_key: str = Field(alias="RequestKey")


PRODUCT_COLUMNS = tuple(field.alias for field in ProductRow.model_fields.values())
ORDER_COLUMNS = tuple(field.alias for field in OrderRow.model_fields.values())
SEED_PRODUCTS = (
    ProductRow(Code="NOTEBOOK", Product="Notebook", PriceCents=12900, Stock=12),
    ProductRow(Code="MARKER", Product="Marker", PriceCents=4500, Stock=8),
)
