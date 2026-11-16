"""Delegate table calls to the maintained Google Sheets integration."""
from __future__ import annotations

from .sheets import SheetFailure


class GoogleTables:
    def __init__(self, service, spreadsheet_id: str):
        self.service, self.spreadsheet_id = service, spreadsheet_id

    def read(self, tab):
        ranges = {"Products": "Products!A:D", "Orders": "Orders!A:G"}
        if tab not in ranges:
            raise SheetFailure("Unknown table")
        try:
            result = self.service.get_values(self.spreadsheet_id, ranges[tab])
            if result.success is not True or not isinstance(result.content, dict):
                raise SheetFailure("Sheet read did not complete")
            rows = result.content.get("values", [])
            if type(rows) is not list or any(type(row) is not list for row in rows):
                raise SheetFailure("Sheet rows have an invalid shape")
            return rows
        except Exception:
            raise SheetFailure("SHEET_READ_UNAVAILABLE") from None

    def append(self, tab, row):
        if tab != "Orders" or len(row) != 7:
            raise SheetFailure("Only complete order rows may be appended")
        try:
            result = self.service.append_values(self.spreadsheet_id, "Orders!A:G", [row],
                                                value_input_option="RAW")
            if result.success is not True:
                raise SheetFailure("Sheet append did not complete")
        except Exception:
            raise SheetFailure("SHEET_APPEND_UNCERTAIN") from None
