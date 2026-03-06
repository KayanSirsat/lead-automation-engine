import json
import re
from typing import Any

from agents.website_extractor import extract_website_content
from llm_client import call_llm

_REQUIRED_KEYS = {"primary_website_weakness", "leverage_angle_used", "personalized_note", "confidence_score"}

_AUDIT_PROMPT_TEMPLATE = """
You are a business conversion expert. Analyse the following website data and evaluate how well it converts visitors into customers.

--- WEBSITE DATA ---
Title: {title}

Meta Description: {meta_description}

Headings:
{headings}

Paragraphs (sample):
{paragraphs}

Call-to-Action Buttons:
{cta_buttons}

Navigation Links:
{navigation_links}

Contact Signals:
{contact_indicators}
--- END OF DATA ---

Evaluate the website on:
- Clarity of the value proposition
- Strength of the headline
- Presence and visibility of call-to-action
- Navigation complexity
- Presence of contact signals
- Overall ability to convert visitors

Return ONLY a strict JSON object with no explanation, no markdown, no code fences — just raw JSON:

{{
  "primary_website_weakness": "<the most important issue reducing conversion>",
  "leverage_angle_used": "<the improvement opportunity that could help the business>",
  "personalized_note": "<a short personalized observation usable in outreach>",
  "confidence_score": <integer 1-10>
}}
""".strip()


def _build_prompt(data: dict[str, Any]) -> str:
    def fmt(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "None found"

    return _AUDIT_PROMPT_TEMPLATE.format(
        title=data.get("title") or "N/A",
        meta_description=data.get("meta_description") or "N/A",
        headings=fmt(data.get("headings", [])),
        paragraphs=fmt(data.get("paragraphs", [])[:10]),
        cta_buttons=fmt(data.get("cta_buttons", [])),
        navigation_links=fmt(data.get("navigation_links", [])),
        contact_indicators=fmt(data.get("contact_indicators", [])),
    )


def _parse_response(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
    raw = re.sub(r"```$", "", raw)
    return json.loads(raw.strip())


def _validate_result(result: dict[str, Any]) -> dict[str, Any]:
    missing = _REQUIRED_KEYS - result.keys()
    if missing:
        raise ValueError(f"LLM response missing required keys: {missing}")

    try:
        score = int(result["confidence_score"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid confidence_score value: {result['confidence_score']!r}"
        ) from exc

    result["confidence_score"] = max(1, min(10, score))
    return result


def audit_website(url: str) -> dict[str, Any]:
    website_data = extract_website_content(url)

    if not website_data.get("title") and not website_data.get("headings"):
        raise ValueError("Website extraction returned insufficient data for analysis.")

    prompt = _build_prompt(website_data)

    raw = call_llm(prompt)
    try:
        return _validate_result(_parse_response(raw))
    except (json.JSONDecodeError, ValueError):
        pass

    raw = call_llm(prompt)
    try:
        return _validate_result(_parse_response(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"LLM returned invalid response after two attempts: {raw!r}") from exc
