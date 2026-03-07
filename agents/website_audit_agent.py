import json
import re
from typing import Any

from agents.website_extractor import extract_website_content
from llm_client import call_llm

_REQUIRED_KEYS = {"primary_website_weakness", "leverage_angle_used", "personalized_note", "confidence_score"}

_AUDIT_PROMPT_TEMPLATE = """
You are a website conversion consultant. Your job is to evaluate whether a business website effectively encourages visitors to contact or engage with the business.

--- WEBSITE DATA ---
Website URL: {url}

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
--- END OF WEBSITE DATA ---

Evaluate the website for conversion leaks. Focus only on these common failure points:
- Unclear value proposition (visitor cannot quickly understand what the business does or who it serves)
- Weak or missing call-to-action (no clear next step for the visitor)
- Navigation overload (too many links distracting from conversion)
- Missing trust signals (no testimonials, credentials, case studies, or social proof)
- Vague or generic service explanation (benefits not clearly communicated)
- Friction in contacting the business (hard to find phone, email, or booking option)

Your task:
1. Identify ONE primary conversion weakness. Be specific and ground it in the actual website data provided.
2. Describe ONE concrete improvement opportunity that would directly address that weakness.
3. Write a short, natural-sounding outreach note that references something specific from the website data.

Confidence scoring:
- 1 to 3: insufficient data to draw meaningful conclusions
- 4 to 6: moderate signal, some evidence of the weakness
- 7 to 10: strong, clear evidence visible in the data

Return ONLY a strict JSON object. No explanation, no markdown, no code fences — raw JSON only:

{{
  "primary_website_weakness": "<one specific conversion weakness grounded in the site data>",
  "leverage_angle_used": "<one concrete improvement opportunity>",
  "personalized_note": "<a short natural outreach note referencing something from the site>",
  "confidence_score": <integer 1-10>
}}
""".strip()


def _build_prompt(url: str, data: dict[str, Any]) -> str:
    def fmt(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "None found"

    return _AUDIT_PROMPT_TEMPLATE.format(
        url=url,
        title=data.get("title") or "N/A",
        meta_description=data.get("meta_description") or "N/A",
        headings=fmt(data.get("headings", [])),
        paragraphs=fmt(data.get("paragraphs", [])[:10]),
        cta_buttons=fmt(data.get("cta_buttons", [])),
        navigation_links=fmt(data.get("navigation_links", [])[:10]),
        contact_indicators=fmt(data.get("contact_indicators", [])),
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
        website_data["paragraphs"] = [
            "Website content could not be extracted. Perform a general website conversion audit based on available information."
        ]

    prompt = _build_prompt(url, website_data)

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
