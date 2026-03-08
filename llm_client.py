print("LLM CLIENT LOADED")
import os
import time

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

_model = genai.GenerativeModel(os.getenv("LLM_MODEL_NAME"))

_MAX_RETRIES = 3
_BACKOFF_BASE = 1


def call_llm(prompt: str) -> str:
    last_exc: Exception = RuntimeError("No attempts made.")

    for attempt in range(_MAX_RETRIES):
        try:
            response = _model.generate_content(prompt)
            return response.text
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_BACKOFF_BASE * (2 ** attempt))

    raise RuntimeError(
        f"Gemini call failed after {_MAX_RETRIES} retries: {last_exc}"
    ) from last_exc
