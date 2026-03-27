import logging

from lead_generation.google_maps_scraper import search_maps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def main():
    query = "cafe satellite ahmedabad"

    print("Starting Google Maps scraper test...")

    results = search_maps(query)

    print("\nRESULTS\n")

    for r in results[:10]:
        print("----------------------")
        print("Name:", r["company_name"])
        print("Phone:", r["phone"])
        print("Rating:", r["rating"], "Reviews:", r["review_count"])
        print("Instagram:", r["instagram"])
        print("Website:", r["website"])
        print("Maps:", r["maps_url"])

    print("\nTotal leads:", len(results))


if __name__ == "__main__":
    main()