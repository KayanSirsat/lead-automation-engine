import os
from typing import Any

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Lazy globals — initialized on first use, not at import time.
# This prevents crashes when the module is imported before .env is loaded
# (e.g. during FastAPI startup or unit tests).
_service: Any = None
_sheets: Any = None


def _get_sheets():
    """Returns the Sheets API client, initializing it on first call."""
    global _service, _sheets
    if _sheets is not None:
        return _sheets

    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")

    if not credentials_path or not sheet_id:
        raise RuntimeError(
            "Missing GOOGLE_CREDENTIALS_PATH or GOOGLE_SHEET_ID in environment variables."
        )

    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    _service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    _sheets = _service.spreadsheets()
    return _sheets


def _sheet_id() -> str:
    sid = os.getenv("GOOGLE_SHEET_ID")
    if not sid:
        raise RuntimeError("GOOGLE_SHEET_ID not set.")
    return sid


def get_sheet_data(sheet_name: str) -> list[dict]:
    try:
        result = _get_sheets().values().get(
            spreadsheetId=_sheet_id(),
            range=sheet_name,
        ).execute()
    except Exception as exc:
        raise RuntimeError(f"Failed to read sheet '{sheet_name}': {exc}") from exc

    rows = result.get("values", [])
    if not rows:
        return []

    headers = rows[0]
    return [
        dict(zip(headers, row + [""] * (len(headers) - len(row))))
        for row in rows[1:]
    ]


def get_lead_by_id(sheet_name: str, lead_id: str) -> dict | None:
    rows = get_sheet_data(sheet_name)
    return next((row for row in rows if row.get("Lead ID") == lead_id), None)


def get_field(row: dict, field_name: str) -> str:
    value = row.get(field_name)
    return value.strip() if isinstance(value, str) else ""


def update_row(sheet_name: str, row_number: int, row_values: list) -> None:
    range_notation = f"{sheet_name}!A{row_number}"
    _get_sheets().values().update(
        spreadsheetId=_sheet_id(),
        range=range_notation,
        valueInputOption="RAW",
        body={"values": [row_values]},
    ).execute()


def append_row(
    sheet_name: str,
    row_values: list,
    value_input_option: str = "RAW",
) -> None:
    range_notation = f"{sheet_name}!A1"
    try:
        _get_sheets().values().append(
            spreadsheetId=_sheet_id(),
            range=range_notation,
            valueInputOption=value_input_option,
            insertDataOption="INSERT_ROWS",
            body={"values": [row_values]},
        ).execute()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to append row to sheet '{sheet_name}': {exc}"
        ) from exc


def col_index_to_letter(col: int) -> str:
    """Convert 1-based column index to letter(s). 1→A, 26→Z, 27→AA."""
    result = ""
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        result = chr(65 + remainder) + result
    return result


def update_cell(sheet_name: str, row: int, col: int, value: str) -> None:
    """Write a single cell value to the given sheet."""
    col_letter = col_index_to_letter(col)
    range_notation = f"{sheet_name}!{col_letter}{row}"
    try:
        _get_sheets().values().update(
            spreadsheetId=_sheet_id(),
            range=range_notation,
            valueInputOption="RAW",
            body={"values": [[value]]},
        ).execute()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to update cell {range_notation} in '{sheet_name}': {exc}"
        ) from exc