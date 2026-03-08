All modules must:

Use type hints.

Use dataclasses for state.

Use structured logging.

Use retry logic for network calls.

Never mix business logic and infrastructure logic.

Agents must only modify LeadState.

Sheets writing happens only inside workflow layer.

LLM prompts must be deterministic and force JSON output.

Validate JSON with schema before applying changes.

Error Handling Standard:

Raise custom exceptions for:

JSONValidationError

WebsiteFetchError

SheetUpdateError