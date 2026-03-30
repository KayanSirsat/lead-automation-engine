import logging
import random
import time
from typing import Any
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright, Page

logger = logging.getLogger(__name__)

# Both constants now agree — scraper visits up to 60 listings per query
_MAX_RESULTS = 60
_SCROLL_PAUSE_MS = 1500


def _random_delay(min_s: float = 0.8, max_s: float = 2.2) -> None:
    time.sleep(random.uniform(min_s, max_s))


def _safe_text(page: Page, selector: str) -> str | None:
    try:
        el = page.locator(selector).first
        if el.count() == 0:
            return None
        return el.inner_text().strip() or None
    except Exception:
        return None


def _extract_listing(page: Page, url: str) -> dict[str, Any] | None:
    """Visits a single Google Maps listing page and extracts structured business data."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector("h1", timeout=10000)
        _random_delay(0.6, 1.5)

        company_name = _safe_text(page, "h1")
        if not company_name:
            return None

        # Rating + review count: parsed from aria-label like "4.4 stars 187 reviews"
        rating: float | None = None
        review_count: int | None = None
        try:
            aria_el = page.locator("[aria-label*='stars']").first
            label = aria_el.get_attribute("aria-label") if aria_el.count() else None
            if label:
                tokens = label.lower().replace(",", "").split()
                for i, token in enumerate(tokens):
                    if token == "stars" and i > 0:
                        try:
                            rating = float(tokens[i - 1])
                        except ValueError:
                            pass
                    if token == "reviews" and i > 0:
                        try:
                            review_count = int(tokens[i - 1])
                        except ValueError:
                            pass
        except Exception:
            pass

        # Phone
        phone: str | None = None
        try:
            phone_el = page.locator("[data-item-id^='phone:tel:']").first
            if phone_el.count():
                phone = phone_el.get_attribute("data-item-id", timeout=3000)
                if phone:
                    phone = phone.replace("phone:tel:", "").strip()
        except Exception:
            phone = None

        # Address
        address: str | None = None
        try:
            addr_el = page.locator("[data-item-id='address']").first
            address = addr_el.inner_text().strip() if addr_el.count() else None
        except Exception:
            address = None

        # Website
        website: str | None = None
        try:
            web_el = page.locator("a[data-item-id='authority']").first
            if web_el.count():
                website = web_el.get_attribute("href", timeout=3000)
        except Exception:
            website = None

        # Instagram — extracted directly from the listing page
        instagram: str | None = None
        try:
            insta_anchors = page.locator("a[href*='instagram.com']")
            if insta_anchors.count():
                for i in range(insta_anchors.count()):
                    href = insta_anchors.nth(i).get_attribute("href")
                    if href and "instagram.com" in href:
                        clean = href.split("?")[0].rstrip("/")
                        clean = clean.replace("www.instagram.com", "instagram.com")
                        parts = clean.split("instagram.com/")
                        if len(parts) > 1 and parts[-1]:
                            instagram = parts[-1]
                            break
        except Exception:
            instagram = None

        return {
            "company_name": company_name,
            "phone": phone,
            "address": address,
            "rating": rating,
            "review_count": review_count,
            "website": website,
            "instagram": instagram,
            "maps_url": url,
        }

    except Exception as e:
        logger.warning(f"Failed to extract listing at {url}: {e}")
        return None


def _collect_listing_urls(page: Page, query: str, limit: int = _MAX_RESULTS) -> list[str]:
    """Loads the Maps search result sidebar and collects individual listing URLs."""
    encoded_query = quote_plus(query)
    maps_url = f"https://www.google.com/maps/search/{encoded_query}"

    logger.info(f"Opening Google Maps search: {query}")
    page.goto(maps_url, wait_until="domcontentloaded", timeout=30000)

    try:
        page.wait_for_selector("div[role='feed']", timeout=15000)
    except Exception:
        logger.warning("Results feed not found — page may not have loaded correctly.")
        return []

    # Dynamic scroll: stop when listing count stops growing for 2 consecutive rounds
    feed = page.locator("div[role='feed']")
    previous_count = 0
    same_count_iterations = 0

    while True:
        try:
            feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
            page.wait_for_timeout(_SCROLL_PAUSE_MS)
        except Exception as e:
            logger.warning(f"Scroll failed: {e}")
            break

        current_count = page.locator("a[href*='/maps/place/']").count()
        logger.debug(f"Scroll check: {current_count} listings visible")

        if current_count >= limit:
            logger.debug(f"Reached listing cap ({limit}), stopping scroll.")
            break

        if current_count == previous_count:
            same_count_iterations += 1
        else:
            same_count_iterations = 0

        if same_count_iterations >= 2:
            logger.debug("No new listings after 2 scrolls — stopping.")
            break

        previous_count = current_count

    # Collect and deduplicate listing URLs
    anchors = page.locator("a[href*='/maps/place/']")
    hrefs: list[str] = []
    seen: set[str] = set()

    for i in range(anchors.count()):
        try:
            href = anchors.nth(i).get_attribute("href")
            if href and "/maps/place/" in href:
                href = href.split("?")[0]
                if href not in seen:
                    seen.add(href)
                    hrefs.append(href)
        except Exception:
            continue

    logger.info(f"Listings discovered: {len(hrefs)} (query: '{query}')")
    return hrefs[:limit]


def search_maps(query: str, limit: int = _MAX_RESULTS) -> list[dict[str, Any]]:
    """
    Searches Google Maps for the given query using a headless Playwright browser.
    Scrolls dynamically until no new results appear, then visits each listing.

    Args:
        query: e.g. "cafe Satellite Ahmedabad"
        limit: max number of leads to fetch for this query

    Returns:
        List of lead dicts with company_name, phone, address, rating,
        review_count, website, instagram, maps_url.
    """
    results: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )

        search_page = context.new_page()
        listing_urls = _collect_listing_urls(search_page, query, limit)
        search_page.close()

        for url in listing_urls:
            if len(results) >= limit:
                break

            logger.info(f"Extracting [{len(results) + 1}/{len(listing_urls)}]: {url[:80]}...")
            detail_page = context.new_page()
            try:
                data = _extract_listing(detail_page, url)
            except Exception as e:
                logger.warning(f"Listing extraction failed: {e}")
                data = None
            detail_page.close()

            if data and data.get("company_name"):
                results.append(data)
                logger.info(f"Collected: {data['company_name']}")

            _random_delay()

        browser.close()

    logger.info(f"Total extracted: {len(results)} leads for query '{query}'")
    return results