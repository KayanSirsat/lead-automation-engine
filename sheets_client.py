import os
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
_service = build("sheets", "v4", credentials=_creds)
_sheets = _service.spreadsheets()


def get_sheet_data(sheet_name: str) -> list[dict]:
    try:
        result = _sheets.values().get(
            spreadsheetId=SHEET_ID,
            range=sheet_name
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
    _sheets.values().update(
        spreadsheetId=SHEET_ID,
        range=range_notation,
        valueInputOption="RAW",
        body={"values": [row_values]}
    ).execute()


def append_row(sheet_name: str, row_values: list) -> None:
    range_notation = f"{sheet_name}!A1"
    try:
        _sheets.values().append(
            spreadsheetId=SHEET_ID,
            range=range_notation,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row_values]}
        ).execute()
    except Exception as exc:
        raise RuntimeError(f"Failed to append row to sheet '{sheet_name}': {exc}") from exc
