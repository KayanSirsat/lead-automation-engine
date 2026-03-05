import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SHEET_ID: str = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_CREDENTIALS_PATH: str = os.environ["GOOGLE_CREDENTIALS_PATH"]
LLM_MODEL_NAME: str = os.environ["LLM_MODEL_NAME"]
