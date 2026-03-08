from sheets_client import get_sheet_data, get_field, append_row, update_row
from agents.website_audit_agent import audit_website

_LEAD_SHEET = "Lead Database"
_RESULT_SHEET = "Strategic Angle"


def run_lead_audit_workflow() -> None:
    existing_rows = get_sheet_data(_RESULT_SHEET)

    # Lead ID → actual sheet row number (row 1 = header, data starts at row 2)
    lead_row_map: dict[str, int] = {
        get_field(row, "Lead ID"): index + 2
        for index, row in enumerate(existing_rows)
        if get_field(row, "Lead ID")
    }

    # Skip leads already audited (Primary Website Weakness is populated)
    audited_ids: set[str] = {
        get_field(row, "Lead ID")
        for row in existing_rows
        if get_field(row, "Primary Website Weakness")
    }

    rows = get_sheet_data(_LEAD_SHEET)

    for row in rows:
        lead_id = get_field(row, "Lead ID")
        if not lead_id or lead_id in audited_ids:
            continue

        website_url = get_field(row, "Website URL")
        if not website_url:
            continue

        try:
            audit_result = audit_website(website_url)
        except Exception as e:
            print(f"Error while processing Lead ID {lead_id}: {e}")
            continue

        row_data = [
            lead_id,
            str(audit_result.get("primary_website_weakness", "")),
            str(audit_result.get("leverage_angle_used", "")),
            str(audit_result.get("personalized_note", "")),
            str(audit_result.get("confidence_score", "")),
        ]

        try:
            if lead_id in lead_row_map:
                update_row(_RESULT_SHEET, lead_row_map[lead_id], row_data)
            else:
                append_row(_RESULT_SHEET, row_data)
                lead_row_map[lead_id] = len(lead_row_map) + 2
        except Exception as e:
            print(f"Error while processing Lead ID {lead_id}: {e}")
            continue
