import logging
import random
import time
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright, Page

logger = logging.getLogger(__name__)

_ZOMATO_SEARCH = "https://www.zomato.com/search?q={query}"
_HEADLESS = True
_NAV_TIMEOUT = 20000
_SELECTOR_TIMEOUT = 10000


def _random_delay(min_s: float = 0.8, max_s: float = 2.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


def _normalize_instagram_url(href: str) -> str | None:
    """Normalises an Instagram href and extracts the username."""
    url = href.split("?")[0].rstrip("/")
    url = url.replace("www.instagram.com", "instagram.com")
    parts = url.split("instagram.com/")
    if len(parts) > 1 and parts[-1]:
        return parts[-1]
    return None


def _find_instagram_on_page(page: Page) -> str | None:
    """Scans all <a> hrefs on the current page for an Instagram link."""
    try:
        anchors = page.locator("a[href*='instagram.com']")
        count = anchors.count()
        for i in range(count):
            try:
                href = anchors.nth(i).get_attribute("href")
                if href and "instagram.com" in href:
                    return _normalize_instagram_url(href)
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"Error while scanning links for Instagram: {e}")
    return None


def _get_first_result_url(page: Page) -> str | None:
    """Returns the href of the first restaurant card in the Zomato search results.
    Tries multiple selectors in priority order to handle Zomato UI changes.
    """
    selectors = [
        "a[href*='/order']",
        "a[href*='/info']",
        "a[href*='/restaurant']",
    ]
    for selector in selectors:
        try:
            result = page.locator(selector).first
            if result.count():
                href = result.get_attribute("href")
                if href:
                    logger.debug(f"Matched Zomato result with selector '{selector}'")
                    return href
        except Exception as e:
            logger.debug(f"Selector '{selector}' failed: {e}")
            continue
    logger.debug("No Zomato result found with any known selector.")
    return None


def enrich_lead(lead: dict) -> None:
    """
    Enriches an existing lead dictionary in-place with an Instagram URL found via Zomato.

    Searches Zomato for the restaurant by company_name + city, opens the first result,
    and sets lead["instagram"] if an Instagram link is found on the listing page.

    Args:
        lead: A lead dict with at least 'company_name' and 'city' keys.
    """
    company_name: str = lead.get("company_name", "").strip()
    city: str = lead.get("city", "").strip()

    if not company_name:
        logger.warning("enrich_lead called with no company_name — skipping.")
        return

    query = quote_plus(f"{company_name} {city}".strip())
    search_url = _ZOMATO_SEARCH.format(query=query)

    logger.info(f"Zomato enrichment: searching for '{company_name}' in '{city}'")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=_HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )

        try:
            page = context.new_page()

            # 1. Load Zomato search results
            logger.debug(f"Navigating to: {search_url}")
            page.goto(search_url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT)
            _random_delay(1.0, 2.0)

            # 2. Get the first restaurant result URL
            result_url = _get_first_result_url(page)
            if not result_url:
                logger.info(f"No Zomato result found for '{company_name}' — skipping enrichment.")
                return

            # Zomato links are sometimes relative
            if result_url.startswith("/"):
                result_url = f"https://www.zomato.com{result_url}"

            logger.debug(f"Opening Zomato listing: {result_url}")
            page.goto(result_url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT)
            _random_delay(1.0, 1.8)

            # 3. Scan the listing page for Instagram links
            instagram_url = _find_instagram_on_page(page)

            if instagram_url:
                lead["instagram"] = instagram_url
                logger.info(f"Instagram found for '{company_name}': {instagram_url}")
            else:
                logger.info(f"No Instagram link found on Zomato listing for '{company_name}'.")

        except Exception as e:
            logger.warning(f"Zomato enrichment failed for '{company_name}': {e}")

        finally:
            browser.close()
