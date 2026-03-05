import re
from urllib.parse import urlparse, urljoin
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

_CTA_KEYWORDS = {"book", "contact", "order", "reserve", "get started", "call", "schedule", "quote"}

_CONTACT_PATTERN = re.compile(
    r"(\+?\d[\d\s\-().]{7,}\d|[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    r"|contact|call us|book|reserve)",
    re.IGNORECASE,
)

_EMPTY_RESULT: dict[str, Any] = {
    "title": "",
    "meta_description": "",
    "headings": [],
    "paragraphs": [],
    "cta_buttons": [],
    "navigation_links": [],
    "internal_links": [],
    "contact_indicators": [],
}


def _clean(texts: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for text in texts:
        stripped = text.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            result.append(stripped)
            if len(result) == limit:
                break
    return result


def extract_website_content(url: str) -> dict[str, Any]:
    try:
        response = requests.get(url, headers=_HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return _EMPTY_RESULT.copy()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    base_domain = urlparse(url).netloc

    # title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # meta description
    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = (
        meta_tag.get("content", "").strip()
        if isinstance(meta_tag, Tag)
        else ""
    )

    # headings
    headings = _clean(
        [tag.get_text() for tag in soup.find_all(["h1", "h2"])],
        limit=20,
    )

    # paragraphs
    paragraphs = _clean(
        [tag.get_text() for tag in soup.find_all("p")],
        limit=30,
    )

    # CTA buttons
    cta_candidates: list[str] = []
    for tag in soup.find_all(["a", "button"]):
        text = tag.get_text(strip=True).lower()
        if any(kw in text for kw in _CTA_KEYWORDS):
            cta_candidates.append(tag.get_text(strip=True))
    cta_buttons = _clean(cta_candidates, limit=15)

    # navigation links
    nav_texts: list[str] = []
    nav_container = (
        soup.find("nav")
        or soup.find("header")
        or soup.find(attrs={"role": "navigation"})
    )
    if isinstance(nav_container, Tag):
        nav_texts = [a.get_text() for a in nav_container.find_all("a", href=True)]
    navigation_links = _clean(nav_texts, limit=20)

    # internal links
    raw_links: list[str] = []
    for a in soup.find_all("a", href=True):
        resolved = urljoin(url, a["href"])
        if urlparse(resolved).netloc == base_domain:
            raw_links.append(resolved)
    internal_links = _clean(raw_links, limit=30)

    # contact indicators
    contact_candidates: list[str] = []
    for tag in soup.find_all(["p", "span", "li", "div", "a"]):
        text = tag.get_text(strip=True)
        if text and len(text) <= 120 and _CONTACT_PATTERN.search(text):
            contact_candidates.append(text)
    contact_indicators = _clean(contact_candidates, limit=10)

    return {
        "title": title,
        "meta_description": meta_description,
        "headings": headings,
        "paragraphs": paragraphs,
        "cta_buttons": cta_buttons,
        "navigation_links": navigation_links,
        "internal_links": internal_links,
        "contact_indicators": contact_indicators,
    }
