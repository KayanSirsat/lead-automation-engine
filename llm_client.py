import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

_API_ENDPOINT = "https://YOUR_LLM_API_ENDPOINT_HERE"  # TODO: replace with actual endpoint
_MODEL_NAME = os.environ["LLM_MODEL_NAME"]
_API_KEY = os.environ["LLM_API_KEY"]

_TIMEOUT = 30
_MAX_RETRIES = 3
_BACKOFF_BASE = 1


def call_llm(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": _MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
    }

    last_exc: Exception = RuntimeError("No attempts made.")

    for attempt in range(_MAX_RETRIES):
        try:
            response = requests.post(
                _API_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_BACKOFF_BASE * (2 ** attempt))

    raise RuntimeError(
        f"LLM call failed after {_MAX_RETRIES} retries: {last_exc}"
    ) from last_exc
