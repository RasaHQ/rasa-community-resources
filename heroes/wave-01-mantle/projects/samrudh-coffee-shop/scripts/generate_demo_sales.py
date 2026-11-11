#!/usr/bin/env python3
"""Build a reproducible fictional Transactions workbook, without external data."""
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

HEADERS = (
    "transaction_id", "transaction_date", "transaction_time", "transaction_qty",
    "store_id", "store_location", "product_id", "unit_price",
    "product_category", "product_type", "product_detail",
)


def write_workbook(destination: Path) -> None:
    """Write eighteen invented sales; fixed ZIP metadata makes bytes repeatable."""
    stores = ((3, "Astoria"), (5, "Lower Manhattan"), (8, "Hell's Kitchen"))
    products = (
        (9001, 3.00, "Coffee", "Gourmet brewed coffee", "Demo Ethiopian coffee Rg"),
        (9002, 4.00, "Tea", "Brewed Chai tea", "Demo chai Rg"),
        (9003, 2.00, "Bakery", "Scone", "Demo scone"),
    )
    rows = [HEADERS]
    for day in range(2):
        for store_id, location in stores:
            for index, product in enumerate(products):
                rows.append((
                    f"DEMO-{len(rows):03}", f"2026-09-{day + 1:02}",
                    f"{9 + index:02}:00:00", 1 + (day + index) % 2,
                    store_id, location, *product,
                ))

    xml_rows = []
    for number, row in enumerate(rows, 1):
        cells = []
        for column, value in enumerate(row):
            address = f"{chr(65 + column)}{number}"
            if isinstance(value, (int, float)):
                cell = f'<c r="{address}"><v>{value}</v></c>'
            else:
                cell = (f'<c r="{address}" t="inlineStr"><is><t>'
                        f'{escape(value)}</t></is></c>')
            cells.append(cell)
        xml_rows.append(f'<row r="{number}">{"".join(cells)}</row>')

    parts = {
        "[Content_Types].xml": (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        ),
        "_rels/.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        ),
        "xl/workbook.xml": (
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Transactions" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        ),
        "xl/worksheets/sheet1.xml": (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
        ),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w") as archive:
        for name, text in parts.items():
            entry = ZipInfo(name, date_time=(2026, 9, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o600 << 16
            archive.writestr(entry, text.encode("utf-8"))


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "data" / "Coffee Shop Sales.xlsx"
    write_workbook(output)
    print(f"Wrote eighteen wholly synthetic transactions to {output}")
