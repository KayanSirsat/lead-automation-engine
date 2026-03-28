import json
import re
from typing import Any

from llm_client import call_llm

_REQUIRED_KEYS = {"subject_line", "email_body"}

_AGENCY_CONTEXT = {
    "cafe": {
        "value_props": ["mobile menu clarity", "booking integration", "visual storytelling", "local SEO"],
        "angle": "conversion-focused website that turns foot traffic into loyal repeat customers",
    },
    "coffee shop": {
        "value_props": ["mobile menu clarity", "booking integration", "visual storytelling", "local SEO"],
        "angle": "conversion-focused website that turns foot traffic into loyal repeat customers",
    },
    "restaurant": {
        "value_props": ["mobile menu clarity", "booking integration", "visual storytelling", "local SEO"],
        "angle": "conversion-focused website that turns reservations and foot traffic into loyal regulars",
    },
    "business coach": {
        "value_props": ["authority positioning", "clear offer clarity", "lead magnet funnel", "high-ticket credibility"],
        "angle": "high-converting website that positions expertise and generates qualified inbound leads",
    },
    "immigration": {
        "value_props": ["trust-building", "case results visibility", "consultation booking optimization", "FAQ clarity"],
        "angle": "trust-first website that converts anxious visitors into booked consultations",
    },
}

_DEFAULT_CONTEXT = {
    "value_props": ["clear value proposition", "strong call-to-action", "trust signals", "easy contact"],
    "angle": "high-conversion website that turns visitors into paying customers",
}

_OUTREACH_PROMPT_TEMPLATE = """
You are a cold email copywriter for a web design agency. Your job is to write a short, personalized cold email to a business owner.

--- LEAD INFO ---
Business Name: {company_name}
Niche: {niche}
Location: {city}
--- END LEAD INFO ---

--- WEBSITE AUDIT FINDINGS ---
Primary Weakness: {primary_website_weakness}
Improvement Opportunity: {leverage_angle_used}
Personalized Observation: {personalized_note}
Audit Confidence: {confidence_score}/10
--- END AUDIT FINDINGS ---

--- AGENCY POSITIONING ---
We build high-conversion, mobile-first websites for {niche} businesses.
Our value propositions for this niche: {value_props}
Our core offer: {angle}
Tone: Confident, professional, value-focused. Never generic. Never spammy.
--- END AGENCY POSITIONING ---

Write a personalized cold outreach email to the owner of {company_name}.

Rules:
- Subject line: short, specific, curiosity-driven. Reference the business name or a specific weakness.
- Body: 2–3 short paragraphs. Max 120 words total.
  - Para 1: One sharp observation about their specific website weakness (use the audit finding).
  - Para 2: What fixing it could mean for their business (use the value prop angle).
  - Para 3: A single, low-friction CTA (e.g. "Would you be open to a 15-min call this week?")
- Never mention "audit", "AI", or "automated analysis". Sound like you personally noticed it.
- Never use generic openers like "I hope this finds you well."
- Sign off as: The LeadFlow Team

Return ONLY a strict JSON object. No explanation, no markdown, no code fences — raw JSON only:

{{
  "subject_line": "<short, specific subject line>",
  "email_body": "<full email body as a single string, use \\n\\n between paragraphs>"
}}
""".strip()


def _build_prompt(lead: dict[str, Any], audit: dict[str, Any]) -> str:
    niche = (lead.get("niche") or lead.get("Niche") or "business").lower()
    ctx = _AGENCY_CONTEXT.get(niche, _DEFAULT_CONTEXT)

    return _OUTREACH_PROMPT_TEMPLATE.format(
        company_name=lead.get("company_name") or lead.get("Company Name") or "the business",
        niche=niche,
        city=lead.get("city") or lead.get("Location") or "your city",
        primary_website_weakness=audit.get("primary_website_weakness", "N/A"),
        leverage_angle_used=audit.get("leverage_angle_used", "N/A"),
        personalized_note=audit.get("personalized_note", "N/A"),
        confidence_score=audit.get("confidence_score", "N/A"),
        value_props=", ".join(ctx["value_props"]),
        angle=ctx["angle"],
    )


def _parse_response(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```", "", raw)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM response.")
    return json.loads(match.group())


def _validate_result(result: dict[str, Any]) -> dict[str, Any]:
    missing = _REQUIRED_KEYS - result.keys()
    if missing:
        raise ValueError(f"LLM response missing required keys: {missing}")
    for key in _REQUIRED_KEYS:
        if not isinstance(result[key], str) or not result[key].strip():
            raise ValueError(f"Field '{key}' is empty or not a string.")
    return result


def generate_outreach(lead: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    """
    Generates a personalized cold outreach email for a lead using LLM.

    Args:
        lead: A lead row dict (from Lead Database sheet or normalized engine output).
        audit: An audit result dict (from Strategic Angle sheet or audit_website()).

    Returns:
        Dict with 'subject_line' and 'email_body'.

    Raises:
        ValueError: If the LLM returns invalid output after two attempts.
    """
    prompt = _build_prompt(lead, audit)

    raw = call_llm(prompt)
    try:
        return _validate_result(_parse_response(raw))
    except (json.JSONDecodeError, ValueError):
        pass

    raw = call_llm(prompt)
    try:
        return _validate_result(_parse_response(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"Outreach LLM returned invalid response after two attempts: {raw!r}"
        ) from exc
