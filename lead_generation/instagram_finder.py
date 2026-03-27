import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def extract_instagram_from_website(url: str) -> str | None:
    try:
        if not url.startswith("http"):
            url = f"http://{url}"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "instagram.com" in href:
                url_clean = href.split("?")[0].rstrip("/")
                url_clean = url_clean.replace("www.instagram.com", "instagram.com")
                parts = url_clean.split("instagram.com/")
                if len(parts) > 1 and parts[-1]:
                    return parts[-1]
    except Exception as e:
        logger.debug(f"Failed to extract Instagram from website {url}: {e}")
    return None

def find_instagram(lead: dict) -> None:
    if lead.get("instagram"):
        return
    
    website = lead.get("website")
    if not website:
        return
        
    logger.info(f"Instagram discovery: scanning website {website}")
    username = extract_instagram_from_website(website)
    if username:
        logger.info(f"Found Instagram username on website: {username}")
        lead["instagram"] = username
