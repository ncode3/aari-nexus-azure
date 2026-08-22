import json
from io import BytesIO

from openpyxl import Workbook
from pypdf import PdfWriter

from app.ingestion.adapters import CsvAdapter, JsonAdapter, PdfAdapter, XlsxAdapter


def test_csv_adapter_preserves_rows() -> None:
    rows = CsvAdapter().parse(b"name,hours\nJavion,12\nJC,25\n")
    assert rows == [{"name": "Javion", "hours": "12"}, {"name": "JC", "hours": "25"}]


def test_xlsx_adapter_preserves_rows() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["name", "hours"])
    sheet.append(["Javion", 12])
    sheet.append(["JC", 25])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    assert XlsxAdapter().parse(output.getvalue()) == [
        {"name": "Javion", "hours": 12},
        {"name": "JC", "hours": 25},
    ]


def test_json_adapter_preserves_structure() -> None:
    payload = {"students": 5, "hours": 78}
    assert JsonAdapter().parse(json.dumps(payload).encode()) == payload


def test_pdf_adapter_preserves_page_boundaries() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    parsed = PdfAdapter().parse(output.getvalue())
    assert parsed["page_count"] == 2
    assert [page["page_number"] for page in parsed["pages"]] == [1, 2]

