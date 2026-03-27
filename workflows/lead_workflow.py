import datetime

from sheets_client import get_sheet_data, get_field, append_row, update_row
from agents.website_audit_agent import audit_website
from lead_generation.engine import generate_leads

_LEAD_SHEET = "Lead Database"
_RESULT_SHEET = "Strategic Angle"


def _normalize_key(name: str, city: str) -> str:
    """Produces a consistent deduplication key from company name and city."""
    return f"{name.strip().lower()}::{city.strip().lower()}"


def _build_address_cell(address: str | None, maps_url: str | None, city: str | None) -> str:
    """Builds the Address cell value, appending city to the label and using a HYPERLINK formula when possible."""
    label = address

    if address and city:
        label = f"{address}, {city}"

    if label and maps_url:
        return f'=HYPERLINK("{maps_url}","{label}")'
    if label:
        return label
    if maps_url:
        return maps_url
    return ""


def _build_rating_cell(rating: float | None, review_count: int | None) -> str:
    """Combines rating and review count into a display string e.g. '4.5 (210)'. Falls back to rating alone."""
    if rating is not None and review_count is not None:
        return f"{rating} ({review_count})"
    if rating is not None:
        return str(rating)
    return ""


def _calculate_tier(review_count: int | None) -> str:
    """Classifies tier based on review count."""
    if review_count is None:
        return ""
    if review_count >= 300:
        return "Executive"
    if review_count >= 150:
        return "Premium"
    if review_count >= 80:
        return "Mid"
    if review_count >= 30:
        return "Low"
    return ""


def _calculate_revenue_level(rating: float | None, review_count: int | None) -> str:
    """Estimates revenue level based on rating and review volume."""
    if rating is None or review_count is None:
        return "Low"
    if rating >= 4.5 and review_count >= 200:
        return "High"
    if rating >= 4.2 and review_count >= 80:
        return "Mid"
    return "Low"


def _next_lead_id(existing_rows: list[dict]) -> int:
    """Returns the next Lead ID by finding the current maximum and incrementing by 1."""
    max_id = 0
    for row in existing_rows:
        raw = get_field(row, "Lead ID")
        try:
            max_id = max(max_id, int(raw))
        except (ValueError, TypeError):
            continue
    return max_id + 1


def write_leads_to_sheet(leads: list[dict]) -> None:
    """
    Writes normalized leads into the Lead Database sheet, matching its exact column order.
    Skips leads already present (matched by company_name + city).
    Uses USER_ENTERED so HYPERLINK formulas are interpreted by Sheets.
    """
    existing_rows = get_sheet_data(_LEAD_SHEET)

    existing_keys: set[str] = {
        _normalize_key(
            get_field(row, "Company Name"),
            get_field(row, "Location"),
        )
        for row in existing_rows
    }

    next_id = _next_lead_id(existing_rows)

    for lead in leads:
        dedup_key = _normalize_key(
            lead.get("company_name", ""),
            lead.get("city", ""),
        )
        if dedup_key in existing_keys:
            continue

        address_cell = _build_address_cell(
            lead.get("address"),
            lead.get("maps_url"),
            lead.get("city"),
        )
        rating_cell = _build_rating_cell(
            lead.get("rating"),
            lead.get("review_count"),
        )

        tier = _calculate_tier(lead.get("review_count"))
        revenue_level = _calculate_revenue_level(lead.get("rating"), lead.get("review_count"))

        ig = lead.get("instagram")
        instagram_cell = f'=HYPERLINK("https://instagram.com/{ig}","{ig}")' if ig else ""

        # Exact column order of the Lead Database sheet
        row_values = [
            str(next_id),                        # Lead ID
            datetime.date.today().isoformat(),   # Date Added
            lead.get("company_name", ""),        # Company Name
            lead.get("niche", ""),               # Niche
            address_cell,                        # Address (HYPERLINK formula)
            lead.get("city", ""),                # Location
            "",                                  # First Name
            "",                                  # Last Name
            lead.get("phone") or "",             # Phone Number
            instagram_cell,                      # Instagram
            rating_cell,                         # Google Rating
            lead.get("source", ""),              # Lead Source
            str(lead.get("lead_score") or ""),   # Lead Score
            "",                                  # Personal Email
            "",                                  # Personal LinkedIn
            "",                                  # Company mail
            "",                                  # Company LinkedIn
            lead.get("website") or "",           # Website URL
            tier,                                # Tier
            revenue_level,                       # Est Revenue Level
        ]

        append_row(_LEAD_SHEET, row_values, value_input_option="USER_ENTERED")
        existing_keys.add(dedup_key)
        next_id += 1


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
