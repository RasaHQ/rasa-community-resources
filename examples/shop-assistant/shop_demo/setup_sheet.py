"""Create missing demo tabs and seed empty tabs without changing existing cells."""
from __future__ import annotations

import json
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .models import Record
from .table_schema import PRODUCT_COLUMNS, ORDER_COLUMNS, SEED_PRODUCTS
from .sheets import integer


class SheetSettings(Record):
    spreadsheet_id: str = Field(pattern=r"^[A-Za-z0-9_-]{20,120}$")
    token: SecretStr

    @classmethod
    def environment(cls):
        try:
            return cls(spreadsheet_id=os.environ["SHOP_SHEET_ID"], token=SecretStr(os.environ["GOOGLE_TOKEN_JSON"]))
        except Exception:
            raise ValueError("Set SHOP_SHEET_ID and GOOGLE_TOKEN_JSON in Codespace secrets") from None


class Properties(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)
    title: str


class Worksheet(BaseModel):
    model_config = Properties.model_config
    properties: Properties


class Spreadsheet(BaseModel):
    model_config = Properties.model_config
    sheets: list[Worksheet] = Field(default_factory=list)


class NewSheet(Record):
    properties: Properties


class AddSheet(Record):
    addSheet: NewSheet


class Outcome(Record):
    tab: Literal["Products", "Orders"]
    action: Literal["seeded", "preserved"]


def content(result):
    if result.success is not True or not isinstance(result.content, dict):
        raise RuntimeError("Sheet setup did not complete; inspect the Sheet before running it again")
    return result.content


def prepare(service, spreadsheet_id):
    metadata = Spreadsheet.model_validate_json(json.dumps(content(service.get_spreadsheet(spreadsheet_id)), allow_nan=False))
    names = [sheet.properties.title for sheet in metadata.sheets]
    if len(names) != len(set(names)):
        raise ValueError("The Sheet contains duplicate tab names")
    missing = [name for name in ("Products", "Orders") if name not in names]
    if missing:
        requests = [AddSheet(addSheet=NewSheet(properties=Properties(title=name))).model_dump(mode="json") for name in missing]
        content(service.batch_update(spreadsheet_id, requests))
    outcomes = []
    for name, columns in (("Products", PRODUCT_COLUMNS), ("Orders", ORDER_COLUMNS)):
        # Read the whole tab, including cells beyond the demo columns. Even a
        # returned blank/formula-result row counts as existing data.
        rows = content(service.get_values(spreadsheet_id, "'" + name + "'")).get("values", [])
        if type(rows) is not list or any(type(row) is not list for row in rows):
            raise ValueError("The Sheet returned invalid rows")
        if rows:
            outcomes.append(Outcome(tab=name, action="preserved"))
            continue
        initial = [list(columns)]
        if name == "Products":
            initial.extend(list(product.model_dump(by_alias=True).values()) for product in SEED_PRODUCTS)
        # Append preserves existing cells if a person edits between read and
        # write. Setup requires exclusive editing of this dedicated demo Sheet.
        content(service.append_values(spreadsheet_id, "'" + name + "'!A1", initial, value_input_option="RAW"))
        readback = content(service.get_values(spreadsheet_id, "'" + name + "'")).get("values", [])
        if name == "Products" and type(readback) is list:
            normalized = [readback[0]] if readback else []
            for row in readback[1:]:
                if type(row) is not list or len(row) != 4:
                    raise RuntimeError("Setup rows changed; inspect the Sheet")
                normalized.append([row[0], row[1], integer(row[2]), integer(row[3])])
            readback = normalized
        if readback != initial:
            raise RuntimeError("Setup readback changed; inspect the Sheet before running setup again")
        outcomes.append(Outcome(tab=name, action="seeded"))
    return tuple(outcomes)


def main():
    from .google_runtime import google_service
    service = None
    try:
        settings = SheetSettings.environment()
        service = google_service(settings.token)
        for outcome in prepare(service, settings.spreadsheet_id):
            if outcome.action == "preserved":
                print(f"{outcome.tab} already contains data. Left every cell unchanged.")
            elif outcome.tab == "Products":
                print("Products is ready with column names, Notebook and Marker.")
            else:
                print("Orders is ready with column names and no orders.")
        return 0
    except Exception:
        print("Sheet setup stopped. Inspect the Sheet before running setup again; no existing cells were overwritten.")
        return 1
    finally:
        if service is not None:
            connection = getattr(service, "sheets_service", None)
            if connection is not None:
                connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
