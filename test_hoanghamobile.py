from scrapers.hoanghamobile import scrape


PRODUCTS = [
    {
        "brand": "Belkin",
        "product_id": "WCA013",
        "product_name": "Belkin 45W Charger",
        "url": "URL_HOANG_HA_CUA_NIC",
    },
]


if __name__ == "__main__":
    results = scrape(PRODUCTS)

    print("")
    print("=" * 60)
    print("HOANG HA TEST RESULT")
    print("=" * 60)

    for result in results:
        print(result)
