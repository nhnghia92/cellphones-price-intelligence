import re
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright


def parse_price(text):
    if not text:
        return None

    text = text.replace(".", "").replace(",", "")

    matches = re.findall(r"(\d{4,9})\s*[đ₫]", text)

    prices = []

    for value in matches:
        price = int(value)

        # Ignore obviously invalid values
        if price >= 10000:
            prices.append(price)

    return prices


def extract_prices(text):
    prices = parse_price(text)

    if not prices:
        return None, None

    current_price = prices[0]
    original_price = None

    for price in prices[1:]:
        if price >= current_price:
            original_price = price
            break

    return current_price, original_price


def scrape_product(page, product):
    url = product["url"]

    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        page.wait_for_timeout(2000)

        text = page.locator("body").inner_text()

        current_price, original_price = extract_prices(text)

        if current_price is None:
            return None

        discount_pct = None

        if original_price and original_price > current_price:
            discount_pct = round(
                (original_price - current_price)
                / original_price
                * 100,
                2
            )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "retailer_id": "RET_005",
            "brand": product["brand"],
            "product_id": product["product_id"],
            "product_name": product["product_name"],
            "price": current_price,
            "original_price": original_price or "",
            "discount_pct": discount_pct or "",
            "stock_status": "UNKNOWN",
            "promotion": "",
            "url": url,
        }

    except Exception as e:
        print(
            f"CellphoneS error "
            f"{product['product_id']}: {e}"
        )

        return None


def scrape(products):
    results = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 900
            }
        )

        for product in products:

            print(
                f"Scraping CellphoneS: "
                f"{product['product_id']}"
            )

            result = scrape_product(
                page,
                product
            )

            if result:
                results.append(result)

            time.sleep(1)

        browser.close()

    return results
