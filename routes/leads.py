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

from sheets_client import get_field, get_lead_by_id, get_sheet_data, append_row
from agents.outreach_agent import generate_outreach, generate_call_script
from agents.contact_enricher import enrich_contact
from workflows.lead_workflow import (
    run_call_script_workflow,
    run_outreach_workflow,
    run_enrichment_workflow,
    run_lead_audit_workflow
)


logger = logging.getLogger(__name__)
router = APIRouter()

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

        return {
            "total_leads": total,
            "audited": audited,
            "pending_audit": total - audited,
            "with_website": with_website,
            "no_website": no_website,
            "by_niche": niche_counts,
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