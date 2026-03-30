import os
import time

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

_model = genai.GenerativeModel(os.getenv("LLM_MODEL_NAME"))

_MAX_RETRIES = 5
_BACKOFF_BASE = 15

def call_llm(prompt: str) -> str:
    last_exc: Exception = RuntimeError("No attempts made.")

    for attempt in range(_MAX_RETRIES):
        try:
            response = _model.generate_content(prompt)
            # Add base 4s delay on success to prevent spiking 15 RPM limit
            time.sleep(4)
            return response.text
        except Exception as exc:
            last_exc = exc
            if "exhausted" in str(exc).lower() or "429" in str(exc):
                # If we hit a hard rate limit, wait 30 seconds to let the minute bucket reset 
                time.sleep(30)
            elif attempt < _MAX_RETRIES - 1:
                time.sleep(_BACKOFF_BASE * (attempt + 1))

    raise RuntimeError(
        f"Gemini call failed after {_MAX_RETRIES} retries. Rate limits or model overload: {last_exc}"
    ) from last_exc