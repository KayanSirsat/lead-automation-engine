import os
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
)

_MODEL = os.getenv("LLM_MODEL_NAME", "meta/llama-3.1-70b-instruct")
_MAX_RETRIES = 4
_BACKOFF_BASE = 10

def call_llm(prompt: str) -> str:
    last_exc = RuntimeError("No attempts made.")
    for attempt in range(_MAX_RETRIES):
        try:
            response = _client.chat.completions.create(
                model=_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as exc:
            last_exc = exc
            wait = _BACKOFF_BASE * (attempt + 1)
            time.sleep(wait)
    raise RuntimeError(f"NVIDIA API call failed after {_MAX_RETRIES} retries: {last_exc}") from last_exc