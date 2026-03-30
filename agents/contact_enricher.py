import logging
import os
import re
from urllib.parse import urlparse, urljoin, quote_plus

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

_SKIP_PATTERNS = (
    "sentry",
    "wix",
    "example",
    "placeholder",
    "noreply",
    "support@",
    "info@wordpress",
)

_CONTACT_KEYWORDS = ("contact", "about", "team")

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_REQUEST_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_valid_email(email: str) -> bool:
    """Return True if the email does not match any skip pattern."""
    lower = email.lower()
    return not any(skip in lower for skip in _SKIP_PATTERNS)


def _extract_emails_from_text(text: str) -> list[str]:
    """Find all valid emails in raw text, deduped and order-preserved."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _EMAIL_RE.findall(text):
        email_lower = match.lower()
        if email_lower not in seen and _is_valid_email(match):
            seen.add(email_lower)
            found.append(match)
    return found


def _extract_domain(url: str | None) -> str | None:
    """Return bare domain (e.g. 'example.com') from a URL, or None."""
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        netloc = parsed.netloc or parsed.path
        domain = netloc.lstrip("www.")
        return domain if domain else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Source 1 — Website contact page scrape
# ---------------------------------------------------------------------------

def _source_website(lead: dict) -> str | None:
    """Scrape the lead's website contact/about/team pages for an email."""
    website = lead.get("website") or lead.get("Website URL")
    if not website:
        return None

    if "://" not in website:
        website = f"https://{website}"

    try:
        resp = requests.get(website, headers=_BROWSER_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        homepage_html = resp.text
    except Exception as exc:
        logger.debug("source_website: homepage fetch failed for %s — %s", website, exc)
        return None

    # Scan homepage directly first
    emails = _extract_emails_from_text(homepage_html)
    if emails:
        logger.info("source_website: found email on homepage for %s", website)
        return emails[0]

    # Collect contact-like links from homepage
    contact_links: list[str] = []
    base_domain = urlparse(website).netloc

    link_re = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    for href in link_re.findall(homepage_html):
        if any(kw in href.lower() for kw in _CONTACT_KEYWORDS):
            resolved = urljoin(website, href)
            if urlparse(resolved).netloc == base_domain:
                contact_links.append(resolved)

    for link in contact_links[:3]:
        try:
            page_resp = requests.get(link, headers=_BROWSER_HEADERS, timeout=_REQUEST_TIMEOUT)
            page_resp.raise_for_status()
            emails = _extract_emails_from_text(page_resp.text)
            if emails:
                logger.info("source_website: found email on %s", link)
                return emails[0]
        except Exception as exc:
            logger.debug("source_website: failed to fetch %s — %s", link, exc)

    return None


# ---------------------------------------------------------------------------
# Source 2 — Instagram bio parse
# ---------------------------------------------------------------------------

def _source_instagram(lead: dict) -> str | None:
    """Fetch the Instagram profile page and scan for an email in the HTML."""
    instagram = lead.get("instagram")
    if not instagram:
        return None

    username = instagram.strip().lstrip("@").split("/")[-1]
    if not username:
        return None

    url = f"https://www.instagram.com/{username}/"
    try:
        resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        emails = _extract_emails_from_text(resp.text)
        if emails:
            logger.info("source_instagram: found email in bio for @%s", username)
            return emails[0]
    except Exception as exc:
        logger.debug("source_instagram: failed for @%s — %s", username, exc)

    return None


# ---------------------------------------------------------------------------
# Source 3 — Google search scrape
# ---------------------------------------------------------------------------

def _source_google(lead: dict) -> str | None:
    """Query Google with company + city + email and scan result snippets."""
    company = lead.get("company_name") or lead.get("Company Name") or ""
    city = lead.get("city") or lead.get("City") or ""

    if not company:
        return None

    query = f'"{company}" "{city}" email contact' if city else f'"{company}" email contact'
    url = f"https://www.google.com/search?q={quote_plus(query)}"

    try:
        resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        emails = _extract_emails_from_text(resp.text)
        if emails:
            logger.info("source_google: found email for '%s'", company)
            return emails[0]
    except Exception as exc:
        logger.debug("source_google: search failed for '%s' — %s", company, exc)

    return None


# ---------------------------------------------------------------------------
# Source 4 — Hunter.io API
# ---------------------------------------------------------------------------

def _source_hunter(lead: dict) -> str | None:
    """Look up a domain on Hunter.io and return the first verified email."""
    api_key = os.environ.get("HUNTER_API_KEY", "").strip()
    if not api_key:
        logger.debug("source_hunter: HUNTER_API_KEY not set, skipping")
        return None

    website = lead.get("website") or lead.get("Website URL")
    domain = _extract_domain(website)
    if not domain:
        logger.debug("source_hunter: no domain available, skipping")
        return None

    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={api_key}"
    try:
        resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        emails = data.get("emails", [])
        if emails:
            email = emails[0].get("value")
            if email and _is_valid_email(email):
                logger.info("source_hunter: found email for %s via Hunter.io", domain)
                return email
    except Exception as exc:
        logger.debug("source_hunter: API call failed for %s — %s", domain, exc)

    return None


# ---------------------------------------------------------------------------
# Source 5 — Prospeo API
# ---------------------------------------------------------------------------

def _source_prospeo(lead: dict) -> str | None:
    """Look up a domain on Prospeo.io and return the first email found."""
    api_key = os.environ.get("PROSPEO_API_KEY", "").strip()
    if not api_key:
        logger.debug("source_prospeo: PROSPEO_API_KEY not set, skipping")
        return None

    website = lead.get("website") or lead.get("Website URL")
    domain = _extract_domain(website)
    if not domain:
        logger.debug("source_prospeo: no domain available, skipping")
        return None

    url = f"https://api.prospeo.io/domain-search?domain={domain}"
    headers = {**_BROWSER_HEADERS, "X-KEY": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        emails = data.get("emails", [])
        if emails:
            email = emails[0].get("email")
            if email and _is_valid_email(email):
                logger.info("source_prospeo: found email for %s via Prospeo", domain)
                return email
    except Exception as exc:
        logger.debug("source_prospeo: API call failed for %s — %s", domain, exc)

    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_WATERFALL: list[tuple[str, callable]] = [
    ("website_scrape", _source_website),
    ("instagram_bio", _source_instagram),
    ("google_search", _source_google),
    ("hunter_io", _source_hunter),
    ("prospeo", _source_prospeo),
]


def enrich_contact(lead: dict) -> str | None:
    """
    Run the waterfall enrichment pipeline and return the first email found.

    Tries each source in order:
      1. Website contact page scrape
      2. Instagram bio parse
      3. Google search snippet scan
      4. Hunter.io domain search API
      5. Prospeo domain search API

    The email is written into ``lead["email"]`` in-place before returning.
    Returns ``None`` if all sources are exhausted without finding an email.
    """
    company = lead.get("company_name") or lead.get("Company Name") or "<unknown>"

    for source_name, source_fn in _WATERFALL:
        try:
            email = source_fn(lead)
        except Exception as exc:
            logger.debug(
                "enrich_contact: unexpected error in %s for '%s' — %s",
                source_name, company, exc,
            )
            email = None

        if email:
            lead["email"] = email
            logger.info(
                "enrich_contact: '%s' — email found via %s: %s",
                company, source_name, email,
            )
            return email

    logger.debug("enrich_contact: no email found for '%s' after all sources", company)
    return None


# ---------------------------------------------------------------------------
# Owner name discovery
# ---------------------------------------------------------------------------

_OWNER_KEYWORDS = (
    "founder", "director", "ceo", "md", "managing director",
    "proprietor", "owner", "co-founder", "head",
)

# Matches typical "First Last" Western-style full names
_NAME_RE = re.compile(r"\b([A-Z][a-z]{1,20})\s+([A-Z][a-z]{1,20})\b")

_OWNER_PAGE_KEYWORDS = ("about", "team", "founder", "director", "management")


def _find_name_near_keyword(text: str) -> str | None:
    """
    Scan text for a capitalised full-name that appears within 100 characters
    of an ownership-role keyword. Returns the first match, or None.
    """
    lower = text.lower()
    for kw in _OWNER_KEYWORDS:
        idx = lower.find(kw)
        while idx != -1:
            window = text[max(0, idx - 100): idx + 100 + len(kw)]
            match = _NAME_RE.search(window)
            if match:
                return match.group()
            idx = lower.find(kw, idx + 1)
    return None


def _owner_source_website(lead: dict) -> str | None:
    """Try the website about/team pages for an owner name."""
    website = lead.get("website") or lead.get("Website URL")
    if not website:
        return None
    if "://" not in website:
        website = f"https://{website}"

    try:
        resp = requests.get(website, headers=_BROWSER_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        homepage_html = resp.text
    except Exception as exc:
        logger.debug("find_owner_name website: homepage fetch failed — %s", exc)
        return None

    # Check homepage directly
    name = _find_name_near_keyword(homepage_html)
    if name:
        return name

    # Collect about/team/founder/director/management sub-links
    base_domain = urlparse(website).netloc
    link_re = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    owner_links: list[str] = []
    for href in link_re.findall(homepage_html):
        if any(kw in href.lower() for kw in _OWNER_PAGE_KEYWORDS):
            resolved = urljoin(website, href)
            if urlparse(resolved).netloc == base_domain:
                owner_links.append(resolved)

    for link in owner_links[:2]:
        try:
            page_resp = requests.get(link, headers=_BROWSER_HEADERS, timeout=_REQUEST_TIMEOUT)
            page_resp.raise_for_status()
            name = _find_name_near_keyword(page_resp.text)
            if name:
                logger.debug("find_owner_name website: found name on %s", link)
                return name
        except Exception as exc:
            logger.debug("find_owner_name website: failed to fetch %s — %s", link, exc)

    return None


def _owner_source_google(lead: dict) -> str | None:
    """Query Google for founder/director/owner name and extract from snippets."""
    company = lead.get("company_name") or lead.get("Company Name") or ""
    city = lead.get("city") or lead.get("City") or ""
    if not company:
        return None

    query = f'"{company}" "{city}" founder OR director OR owner' if city else f'"{company}" founder OR director OR owner'
    url = f"https://www.google.com/search?q={quote_plus(query)}"

    try:
        resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        name = _find_name_near_keyword(resp.text)
        if name:
            logger.debug("find_owner_name google: found name for '%s'", company)
            return name
    except Exception as exc:
        logger.debug("find_owner_name google: search failed for '%s' — %s", company, exc)

    return None


def find_owner_name(lead: dict) -> str | None:
    """
    Tries to discover the owner, founder, or director name of the business.

    Sources tried in order (stops at first success):
      A. Website about/team page — looks for names near ownership keywords
      B. Google search — queries for founder/director/owner in result snippets

    Writes the name into ``lead["owner_name"]`` in-place before returning.
    Returns ``None`` if all sources are exhausted.
    """
    company = lead.get("company_name") or lead.get("Company Name") or "<unknown>"

    for source_label, source_fn in [
        ("website_about", _owner_source_website),
        ("google_search", _owner_source_google),
    ]:
        try:
            name = source_fn(lead)
        except Exception as exc:
            logger.debug(
                "find_owner_name: unexpected error in %s for '%s' — %s",
                source_label, company, exc,
            )
            name = None

        if name:
            lead["owner_name"] = name
            logger.info(
                "find_owner_name: '%s' — name found via %s: %s",
                company, source_label, name,
            )
            return name

    logger.debug("find_owner_name: no name found for '%s' after all sources", company)
    return None
