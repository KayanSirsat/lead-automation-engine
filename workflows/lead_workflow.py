import datetime

from sheets_client import get_sheet_data, get_field, append_row, update_row, _get_sheets, _sheet_id
from agents.website_audit_agent import audit_website
from agents.outreach_agent import generate_outreach, generate_call_script
from agents.contact_enricher import enrich_contact
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


_DRAFT_SHEET = "Outreach Drafts"


def run_outreach_workflow() -> int:
    """
    Generates cold outreach email drafts for leads that don't yet have a draft.
    Uses audit results if available, otherwise generates a simplified draft 
    for leads that at least have a phone number or Instagram handle.

    Reads:
        - Lead Database sheet (for lead context: name, niche, city, phone, IG)
        - Strategic Angle sheet (for audit results)

    Writes to:
        - Outreach Drafts sheet (columns: Lead ID | Company Name | Niche | Subject Line | Email Body | Generated At | Status)

    Returns:
        Number of new drafts written.
    """
    # Build lookup: Lead ID → audit row
    audit_rows = get_sheet_data(_RESULT_SHEET)
    audit_map: dict[str, dict] = {
        get_field(row, "Lead ID"): row
        for row in audit_rows
        if get_field(row, "Lead ID") and get_field(row, "Primary Website Weakness")
    }

    # Build set of lead IDs already drafted
    draft_rows = get_sheet_data(_DRAFT_SHEET)
    drafted_ids: set[str] = {
        get_field(row, "Lead ID")
        for row in draft_rows
        if get_field(row, "Lead ID")
    }

    lead_rows = get_sheet_data(_LEAD_SHEET)
    written = 0

    for lead in lead_rows:
        lead_id = get_field(lead, "Lead ID")
        if not lead_id or lead_id in drafted_ids:
            continue

        audit = audit_map.get(lead_id)
        if not audit:
            phone = get_field(lead, "Phone Number")
            ig = get_field(lead, "Instagram")
            if not phone and not ig:
                continue
            
            company_name = get_field(lead, "Company Name") or "This business"
            audit = {
                "primary_website_weakness": "No website found for this business",
                "leverage_angle_used": "Building a professional online presence from scratch",
                "personalized_note": f"{company_name} doesn't appear to have a website yet, which means potential clients searching online can't find them",
                "confidence_score": 5
            }

        try:
            draft = generate_outreach(lead, audit)
        except Exception as e:
            print(f"Outreach generation failed for Lead ID {lead_id}: {e}")
            continue

        row_values = [
            lead_id,
            get_field(lead, "Company Name"),
            get_field(lead, "Niche"),
            draft.get("subject_line", ""),
            draft.get("email_body", ""),
            datetime.datetime.utcnow().isoformat() + "Z",
            "Draft",
        ]

        try:
            append_row(_DRAFT_SHEET, row_values)
            drafted_ids.add(lead_id)
            written += 1
        except Exception as e:
            print(f"Failed to write outreach draft for Lead ID {lead_id}: {e}")
            continue

    print(f"Outreach workflow complete. {written} new draft(s) written.")
    return written


_PERSONAL_EMAIL_COL = "N"  # Column 14 in the Lead Database sheet


def run_enrichment_workflow() -> int:
    """
    Enriches leads with email addresses and writes them back to the Lead Database sheet.

    For each lead that does not yet have a Personal Email value:
      - Calls enrich_contact() which runs a 5-source waterfall (website scrape,
        Instagram bio, Google search, Hunter.io, Prospeo)
      - On success, writes the discovered email to column N (Personal Email)
        of that lead's row using a targeted single-cell Sheets API update

    Returns:
        Number of leads successfully enriched.
    """
    rows = get_sheet_data(_LEAD_SHEET)
    enriched = 0

    for index, row in enumerate(rows):
        lead_id = get_field(row, "Lead ID")
        if not lead_id:
            continue

        # Skip leads that already have a Personal Email
        if get_field(row, "Personal Email"):
            continue

        # Build a unified lead_dict for the enricher
        lead_dict = {
            "company_name": get_field(row, "Company Name"),
            "Company Name":  get_field(row, "Company Name"),
            "website":       get_field(row, "Website URL"),
            "Website URL":   get_field(row, "Website URL"),
            "city":          get_field(row, "Location"),
            "City":          get_field(row, "Location"),
            "instagram":     get_field(row, "Instagram"),
        }

        try:
            email = enrich_contact(lead_dict)
        except Exception as exc:
            print(f"Enrichment failed for Lead ID {lead_id}: {exc}")
            continue

        if not email:
            continue

        # Row number in the sheet: header is row 1, data starts at row 2
        sheet_row = index + 2
        cell_range = f"{_LEAD_SHEET}!{_PERSONAL_EMAIL_COL}{sheet_row}"

        try:
            _get_sheets().values().update(
                spreadsheetId=_sheet_id(),
                range=cell_range,
                valueInputOption="RAW",
                body={"values": [[email]]},
            ).execute()
            enriched += 1
        except Exception as exc:
            print(f"Failed to write email for Lead ID {lead_id}: {exc}")
            continue

    print(f"Enrichment workflow complete. {enriched} lead(s) enriched.")
    return enriched


_CALL_SCRIPT_SHEET = "Call Scripts"


def run_call_script_workflow() -> int:
    """
    Generates phone call scripts for all audited leads that don't yet have one.

    Reads:
        - Lead Database sheet
        - Strategic Angle sheet (audit required — skips leads with no audit)
        - Call Scripts sheet (to skip already-scripted leads)

    Writes to:
        - Call Scripts sheet (columns: Lead ID | Company Name | Niche | Phone Number |
          Opener | Hook | Value Prop | Not Interested | No Time | Have Website | Close | Generated At)

    Returns:
        Number of new call scripts written.
    """
    # Build audit lookup: Lead ID → audit row
    audit_rows = get_sheet_data(_RESULT_SHEET)
    audit_map: dict[str, dict] = {
        get_field(row, "Lead ID"): row
        for row in audit_rows
        if get_field(row, "Lead ID") and get_field(row, "Primary Website Weakness")
    }

    if not audit_map:
        print("No audited leads found. Skipping call script workflow.")
        return 0

    # Build set of already-scripted Lead IDs
    existing_scripts = get_sheet_data(_CALL_SCRIPT_SHEET)
    scripted_ids: set[str] = {
        get_field(row, "Lead ID")
        for row in existing_scripts
        if get_field(row, "Lead ID")
    }

    lead_rows = get_sheet_data(_LEAD_SHEET)
    written = 0

    for lead in lead_rows:
        lead_id = get_field(lead, "Lead ID")
        if not lead_id or lead_id in scripted_ids:
            continue

        audit = audit_map.get(lead_id)
        if not audit:
            continue  # Call scripts require real audit data

        try:
            script = generate_call_script(lead, audit)
        except Exception as e:
            print(f"Call script generation failed for Lead ID {lead_id}: {e}")
            continue

        objections = script.get("objection_responses", {})
        row_values = [
            lead_id,
            get_field(lead, "Company Name"),
            get_field(lead, "Niche"),
            get_field(lead, "Phone Number"),
            script.get("opener", ""),
            script.get("hook", ""),
            script.get("value_prop", ""),
            objections.get("not_interested", ""),
            objections.get("no_time", ""),
            objections.get("have_website", ""),
            script.get("close", ""),
            datetime.datetime.utcnow().isoformat() + "Z",
        ]

        try:
            append_row(_CALL_SCRIPT_SHEET, row_values)
            scripted_ids.add(lead_id)
            written += 1
        except Exception as e:
            print(f"Failed to write call script for Lead ID {lead_id}: {e}")
            continue

    print(f"Call script workflow complete. {written} script(s) written.")
    return written
