All LLM agents must return STRICT JSON only.

Audit Agent Contract:

{
"primary_website_weakness": string,
"leverage_angle_used": string,
"personalized_note": string,
"confidence_score": integer
}

Outreach Agent Contract:

{
"subject_line": string,
"pitch_version": "V1" | "V2" | "V3",
"outreach_channel": "Email" | "LinkedIn" | "Other",
"email_body": string
}

Rules:

No markdown.

No explanation.

No extra fields.

No trailing commas.

JSON must be parseable with json.loads().

If invalid → retry once.