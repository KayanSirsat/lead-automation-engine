import logging
from typing import Any

# Configure logging for the pipeline
logger = logging.getLogger(__name__)

# Optional scraper modules
google_maps_scraper = None
zomato_scraper = None
instagram_finder = None

try:
    from . import google_maps_scraper
except ImportError:
    pass

try:
    from . import zomato_scraper
except ImportError:
    pass

try:
    from . import instagram_finder
except ImportError:
    pass


def _generate_queries(niche: str, city: str, areas: list[str] | None) -> list[str]:
    """
    Generates location-specific search queries by combining niche synonyms with
    each area and the city. Also includes generic city-level fallbacks.
    """
    # Niche-specific synonym variants
    _NICHE_SYNONYMS: dict[str, list[str]] = {
        "cafe": ["cafe", "coffee shop", "best cafe", "specialty coffee", "espresso bar"],
        "restaurant": ["restaurant", "best restaurant", "fine dining", "eatery"],
        "gym": ["gym", "fitness center", "health club"],
    }

    synonyms = _NICHE_SYNONYMS.get(niche.lower(), [niche])
    seen: set[str] = set()
    queries: list[str] = []

    def _add(q: str) -> None:
        if q not in seen:
            seen.add(q)
            queries.append(q)

    # 1. Area-specific queries (highest specificity, listed first)
    if areas:
        for area in areas:
            for synonym in synonyms:
                _add(f"{synonym} {area} {city}")

    # 2. City-level fallback queries
    for synonym in synonyms:
        _add(f"{synonym} {city}")

    return queries


def _normalize_lead(raw_data: dict[str, Any], niche: str, city: str) -> dict[str, Any]:
    """
    Converts raw unstructured scraper data into a consistent lead schema.
    """
    return {
        "company_name": str(raw_data.get("company_name", "")),
        "phone": raw_data.get("phone"),
        "address": raw_data.get("address"),
        "maps_url": raw_data.get("maps_url"),
        "city": city,
        "rating": raw_data.get("rating"),
        "review_count": raw_data.get("review_count"),
        "website": raw_data.get("website"),
        "instagram": raw_data.get("instagram"),
        "source": "google_maps",
        "niche": niche,
    }


def _calculate_score(rating: float | None, reviews: int | None) -> int:
    """
    Calculates the internal lead score using predefined bracket logic tracking rating vs review count.
    """
    if rating is None or reviews is None:
        return 0

    try:
        rating_val = float(rating)
        reviews_val = int(reviews)
    except (TypeError, ValueError):
        return 0

    if rating_val >= 4.5 and reviews_val >= 200:
        return 10
    if rating_val >= 4.3 and reviews_val >= 100:
        return 8
    if rating_val >= 4.0 and reviews_val >= 50:
        return 6
    if rating_val >= 3.5 and reviews_val >= 30:
        return 4
        
    return 0


def generate_leads(
    niche: str,
    city: str,
    areas: list[str] | None,
    limit: int
) -> list[dict[str, Any]]:
    """
    Main orchestration engine for lead generation.
    Generates queries, fetches raw records via Google Maps, normalizes, deduplicates, 
    and handles enrichment hooks (Zomato/Instagram), enforcing the lead limit constraint. 
    """
    logger.info(f"Starting lead generation pipeline (niche={niche}, city={city}, limit={limit})")

    # 1. Query Generator
    queries = _generate_queries(niche, city, areas)
    logger.info(f"Generated {len(queries)} search queries: {queries}")

    unique_leads: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for query in queries:
        # 8. Limit Control (check before querying)
        if len(unique_leads) >= limit:
            break

        logger.info(f"Executing Google Maps search: '{query}'")

        # 2. Google Maps Scraper
        if google_maps_scraper:
            try:
                raw_results = google_maps_scraper.search_maps(query)
            except Exception as e:
                logger.error(f"Google Maps scraper failed for query '{query}': {e}")
                continue
        else:
            logger.warning("Placeholder 'google_maps_scraper' is missing/unimplemented.")
            raw_results = []

        for raw_record in raw_results:
            # 8. Limit Control (check per record)
            if len(unique_leads) >= limit:
                break

            # 3. Lead Normalization
            lead = _normalize_lead(raw_record, niche, city)
            
            # If the raw data didn't contain a company name, we skip it
            # (as it breaks duplicate detection and later operations)
            if not lead["company_name"]:
                continue

            # 4. Duplicate Detection
            # company_name.lower() + city
            dup_key = f"{lead['company_name'].lower()}_{city.lower()}"
            if dup_key in seen_keys:
                continue
            
            seen_keys.add(dup_key)

            # 5. Zomato Enrichment
            if not lead.get("instagram") and zomato_scraper:
                try:
                    logger.debug(f"Calling Zomato enrichment for {lead['company_name']}")
                    zomato_scraper.enrich_lead(lead)
                except Exception as e:
                    logger.warning(f"Zomato enrichment failed for {lead['company_name']}: {e}")

            # 6. Instagram Discovery
            if not lead.get("instagram") and instagram_finder:
                try:
                    logger.debug(f"Calling Instagram discovery for {lead['company_name']}")
                    instagram_finder.find_instagram(lead)
                except Exception as e:
                    logger.warning(f"Instagram discovery failed for {lead['company_name']}: {e}")

            # 7. Lead Score Calculation
            # Done after enrichment in case rating/reviews were patched
            score = _calculate_score(lead.get("rating"), lead.get("review_count"))
            lead["lead_score"] = score

            unique_leads.append(lead)
            logger.info(f"Successfully processed lead [{len(unique_leads)}/{limit}]: {lead['company_name']}")

    # 9. Return Final Leads
    logger.info(f"Pipeline complete. Yielded {len(unique_leads)} leads.")
    return unique_leads
