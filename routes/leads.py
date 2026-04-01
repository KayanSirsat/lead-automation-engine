"""
routes/leads.py

GET /leads                  — all leads from Lead Database sheet
GET /leads/{id}             — single lead by Lead ID
GET /leads/{id}/audit       — audit result from Strategic Angle sheet
POST /leads/{id}/outreach   — generate (and save) a cold outreach draft for a lead
POST /leads/{id}/call-script — generate a structured phone call script for a lead
GET /leads/stats            — dashboard summary counts
"""

import datetime
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sheets_client import get_field, get_lead_by_id, get_sheet_data, append_row, update_cell
from agents.outreach_agent import generate_outreach, generate_call_script
from agents.contact_enricher import enrich_contact
from workflows.lead_workflow import (
    run_call_script_workflow,
    run_outreach_workflow,
    run_enrichment_workflow,
    run_lead_audit_workflow,
    run_outreach_delivery_workflow
)


logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_STATUSES = {"New", "Contacted", "Replied", "Meeting Booked", "Closed", "Dead"}


class StatusUpdate(BaseModel):
    status: str

_LEAD_SHEET = "Lead Database"
_AUDIT_SHEET = "Strategic Angle"


@router.get("/stats")
def get_stats():
    """
    Returns summary counts for the dashboard.
    Reads both sheets once and counts rows.
    """
    try:
        leads = get_sheet_data(_LEAD_SHEET)
        audits = get_sheet_data(_AUDIT_SHEET)

        audited_ids = {
            get_field(r, "Lead ID")
            for r in audits
            if get_field(r, "Primary Website Weakness")
        }

        total = len(leads)
        audited = len(audited_ids)
        with_website = sum(1 for r in leads if get_field(r, "Website URL"))
        no_website = total - with_website

        # Breakdown by niche
        niche_counts: dict[str, int] = {}
        for r in leads:
            niche = get_field(r, "Niche") or "Unknown"
            niche_counts[niche] = niche_counts.get(niche, 0) + 1

        contacted = sum(1 for r in leads if get_field(r, "Status") == "Contacted")

        return {
            "total_leads": total,
            "audited": audited,
            "pending_audit": total - audited,
            "with_website": with_website,
            "no_website": no_website,
            "by_niche": niche_counts,
            "contacted": contacted,
        }

    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def get_leads(
    niche: str | None = None,
    city: str | None = None,
    min_score: int | None = None,
):
    """
    Returns all leads from the Lead Database sheet.
    Supports optional filtering by niche, city, and minimum lead score.
    """
    try:
        rows = get_sheet_data(_LEAD_SHEET)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if niche:
        rows = [r for r in rows if get_field(r, "Niche").lower() == niche.lower()]
    if city:
        rows = [r for r in rows if get_field(r, "Location").lower() == city.lower()]
    if min_score is not None:
        def _score(r):
            try:
                return int(get_field(r, "Lead Score"))
            except (ValueError, TypeError):
                return 0
        rows = [r for r in rows if _score(r) >= min_score]

    return rows


@router.get("/{lead_id}")
def get_lead(lead_id: str):
    """Returns a single lead row by Lead ID."""
    try:
        lead = get_lead_by_id(_LEAD_SHEET, lead_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    return lead


@router.get("/{lead_id}/audit")
def get_audit(lead_id: str):
    """Returns the Strategic Angle audit result for a given Lead ID."""
    try:
        rows = get_sheet_data(_AUDIT_SHEET)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    audit = next(
        (r for r in rows if get_field(r, "Lead ID") == lead_id),
        None,
    )
    if not audit:
        raise HTTPException(
            status_code=404,
            detail=f"No audit found for Lead ID {lead_id}",
        )
    return audit


_DRAFT_SHEET = "Outreach Drafts"
_CALL_SCRIPT_SHEET = "Call Scripts"


@router.post("/{lead_id}/outreach", status_code=201)
def generate_lead_outreach(lead_id: str):
    """
    Generates a personalized cold email draft for a lead using its website audit result.
    Saves the draft to the Outreach Drafts sheet and returns it.
    Requires the lead to have an existing audit in the Strategic Angle sheet.
    """
    # Fetch lead
    try:
        lead = get_lead_by_id(_LEAD_SHEET, lead_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

    # Fetch audit
    try:
        audit_rows = get_sheet_data(_AUDIT_SHEET)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    audit = next((r for r in audit_rows if get_field(r, "Lead ID") == lead_id), None)
    if not audit:
        raise HTTPException(
            status_code=404,
            detail=f"No audit result found for Lead ID {lead_id}. Run the audit first.",
        )

    # Generate outreach draft
    try:
        draft = generate_outreach(lead, audit)
    except Exception as e:
        logger.error(f"Outreach generation failed for Lead {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Outreach generation failed: {e}")

    # Persist to Outreach Drafts sheet
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
    except Exception as e:
        logger.warning(f"Could not persist outreach draft for Lead {lead_id}: {e}")

    return {
        "lead_id": lead_id,
        "company_name": get_field(lead, "Company Name"),
        "subject_line": draft.get("subject_line"),
        "email_body": draft.get("email_body"),
        "status": "Draft",
    }


@router.post("/{lead_id}/enrich", status_code=200)
def enrich_lead_contact(lead_id: str):
    try:
        lead = get_lead_by_id(_LEAD_SHEET, lead_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

    existing_email = get_field(lead, "Personal Email")
    if existing_email:
        return {"lead_id": lead_id, "email": existing_email, "source": "existing"}

    # Map necessary fields for contact_enricher
    lead["city"] = get_field(lead, "Location")
    lead["instagram"] = get_field(lead, "Instagram")
    lead["company_name"] = get_field(lead, "Company Name")
    lead["website"] = get_field(lead, "Website URL")

    try:
        email = enrich_contact(lead)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {e}")

    if email:
        return {"lead_id": lead_id, "email": email, "source": "enriched"}

    raise HTTPException(status_code=404, detail="No email found for this lead")


@router.post("/{lead_id}/call-script", status_code=200)
def generate_lead_call_script(lead_id: str):
    """
    Generates a structured phone call script for a lead using its website audit result.
    Requires the lead to have an existing audit in the Strategic Angle sheet.
    """
    # Fetch lead
    try:
        lead = get_lead_by_id(_LEAD_SHEET, lead_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

    # Fetch audit
    try:
        audit_rows = get_sheet_data(_AUDIT_SHEET)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    audit = next((r for r in audit_rows if get_field(r, "Lead ID") == lead_id), None)
    if not audit:
        raise HTTPException(
            status_code=404,
            detail=f"No audit result found for Lead ID {lead_id}. Run the audit first.",
        )

    # Generate call script
    try:
        script = generate_call_script(lead, audit)
    except Exception as e:
        logger.error(f"Call script generation failed for Lead {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Call script generation failed: {e}")

    # Persist to Call Scripts sheet
    objections = script.get("objection_responses", {})
    script_row = [
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
        append_row(_CALL_SCRIPT_SHEET, script_row)
    except Exception as e:
        logger.warning(f"Could not persist call script for Lead {lead_id}: {e}")

    return script


@router.post("/sync/call-scripts", status_code=200)
def sync_call_scripts():
    count = run_call_script_workflow()
    return {"scripted": count}

@router.post("/sync/outreach", status_code=200)
def sync_outreach():
    count = run_outreach_workflow()
    return {"outreached": count}

@router.post("/sync/enrichment", status_code=200)
def sync_enrichment():
    count = run_enrichment_workflow()
    return {"enriched": count}

@router.post("/sync/audit", status_code=200)
def sync_audit():
    run_lead_audit_workflow()
    return {"status": "success"}


@router.post("/{lead_id}/send-email", status_code=200)
def send_lead_email(lead_id: str):
    """
    Sends the outreach email for a specific lead.
    
    Requires:
      - Lead must exist in Lead Database with a Personal Email
      - Lead must have an outreach draft in Outreach Drafts sheet with status "Draft"
    
    On success:
      - Sends the email
      - Updates the draft status to "Sent" with timestamp
      - Returns success response
    """
    from agents.email_sender import send_email
    
    _DRAFT_SHEET = "Outreach Drafts"
    
    # Fetch lead from Lead Database
    try:
        lead = get_lead_by_id(_LEAD_SHEET, lead_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    
    to_email = get_field(lead, "Personal Email")
    if not to_email:
        raise HTTPException(
            status_code=404,
            detail=f"Lead {lead_id} has no Personal Email. Run enrichment first."
        )
    
    # Fetch draft from Outreach Drafts
    try:
        draft_rows = get_sheet_data(_DRAFT_SHEET)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    draft = None
    draft_row_index = None
    for i, row in enumerate(draft_rows):
        if get_field(row, "Lead ID") == lead_id:
            draft = row
            draft_row_index = i
            break
    
    if not draft:
        raise HTTPException(
            status_code=404,
            detail=f"No outreach draft found for Lead {lead_id}. Generate draft first."
        )
    
    # Check if already sent
    status = get_field(draft, "Status")
    if status and status.startswith("Sent"):
        raise HTTPException(
            status_code=400,
            detail=f"Email already sent for Lead {lead_id}. Status: {status}"
        )
    
    subject = get_field(draft, "Subject Line")
    body = get_field(draft, "Email Body")
    company_name = get_field(lead, "Company Name")
    
    if not subject or not body:
        raise HTTPException(
            status_code=400,
            detail=f"Draft for Lead {lead_id} is missing subject or body"
        )
    
    # Send the email
    try:
        success = send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            from_name="LeadFlow Team",
        )
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} for Lead {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Email sending failed: {e}")
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Email sending failed for {to_email}. Check logs for details."
        )
    
    # Update draft status to "Sent" with timestamp
    sheet_row = draft_row_index + 2  # +2 because header is row 1, data starts at row 2
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    new_status = f"Sent ({timestamp})"
    
    try:
        # Status is column 7 (G) in Outreach Drafts sheet
        update_cell(_DRAFT_SHEET, sheet_row, 7, new_status)
    except Exception as e:
        logger.warning(f"Email sent but failed to update draft status for Lead {lead_id}: {e}")
    
    logger.info(f"Email sent successfully to {company_name} ({to_email}), Lead ID {lead_id}")
    
    return {
        "lead_id": lead_id,
        "company_name": company_name,
        "to_email": to_email,
        "subject": subject,
        "status": "sent",
        "sent_at": timestamp,
    }


@router.post("/sync/delivery", status_code=200)
def sync_delivery():
    """
    Bulk sends all pending outreach drafts (status = "Draft") that have
    enriched email addresses in the Lead Database.
    """
    count = run_outreach_delivery_workflow()
    return {"sent": count}


@router.patch("/{lead_id}/status", status_code=200)
def update_lead_status(lead_id: str, body: StatusUpdate):
    if body.status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of: {', '.join(sorted(_VALID_STATUSES))}"
        )

    # Scan Lead Database to find the 1-based row number of this lead
    # Row 1 is the header, so data starts at row 2
    rows = get_sheet_data(_LEAD_SHEET)
    row_number = None
    for i, row in enumerate(rows):
        if row.get("Lead ID") == lead_id:
            row_number = i + 2  # +1 for 0-index, +1 for header row
            break

    if row_number is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

    # Column U = 21
    update_cell(_LEAD_SHEET, row_number, 21, body.status)
    logger.info(f"Lead {lead_id} status updated to '{body.status}' at row {row_number}")

    return {"lead_id": lead_id, "status": body.status}