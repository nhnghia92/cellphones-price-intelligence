from scrapers.cellphones import scrape as scrape_cellphones
from scrapers.hoanghamobile import scrape as scrape_hoangha


SCRAPERS = {
    "RET_005": scrape_cellphones,
    "RET_006": scrape_hoangha,
}


def scrape_all(products):

    grouped = {}

    for product in products:

        retailer_id = product["retailer_id"]

        grouped.setdefault(
            retailer_id,
            []
        ).append(product)

    results = []

    for retailer_id, retailer_products in grouped.items():

        scraper = SCRAPERS.get(
            retailer_id
        )

        if scraper is None:

            print(
                f"WARNING: No scraper configured "
                f"for {retailer_id}"
            )

            continue

        print("")
        print(
            f"Starting scraper: {retailer_id}"
        )

        retailer_results = scraper(
            retailer_products
        )

        results.extend(
            retailer_results
        )

    return results
