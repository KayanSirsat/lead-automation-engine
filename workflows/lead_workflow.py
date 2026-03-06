from sheets_client import get_sheet_data, get_field, append_row
from agents.website_audit_agent import audit_website

_LEAD_SHEET = "Lead Database"
_RESULT_SHEET = "Strategic Angle"


def run_lead_audit_workflow() -> None:
    existing_rows = get_sheet_data(_RESULT_SHEET)
    processed_ids = {get_field(row, "Lead ID") for row in existing_rows}

    rows = get_sheet_data(_LEAD_SHEET)

    for row in rows:
        lead_id = get_field(row, "Lead ID")
        if not lead_id or lead_id in processed_ids:
            continue

        website_url = get_field(row, "Website URL")

        if not website_url:
            continue

        try:
            audit_result = audit_website(website_url)
        except Exception:
            continue

        try:
            append_row(_RESULT_SHEET, [
                lead_id,
                str(audit_result.get("primary_website_weakness", "")),
                str(audit_result.get("leverage_angle_used", "")),
                str(audit_result.get("personalized_note", "")),
                str(audit_result.get("confidence_score", "")),
            ])
        except Exception:
            continue
        else:
            processed_ids.add(lead_id)
