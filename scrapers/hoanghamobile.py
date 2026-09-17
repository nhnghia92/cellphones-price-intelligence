import re
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright


RETAILER_ID = "RET_006"


def parse_price(text):
    """
    Extract Vietnamese prices from page text.

    Examples:
    350.000đ
    490.000đ
    1.290.000₫
    """

    if not text:
        return []

    matches = re.findall(
        r"(\d{1,3}(?:[.,]\d{3})+|\d{4,9})\s*[đ₫]",
        text,
    )

    prices = []

    for value in matches:

        try:

            price = int(
                value.replace(".", "")
                .replace(",", "")
            )

            if price >= 10000:
                prices.append(price)

        except ValueError:

            continue

    return prices


def extract_prices(text):

    prices = parse_price(text)

    if not prices:
        return None, None

    # First valid price = current price
    current_price = prices[0]

    original_price = None

    # Find first price >= current price
    for price in prices[1:]:

        if price >= current_price:

            original_price = price

            break

    return (
        current_price,
        original_price,
    )


def scrape_product(page, product):

    url = product["url"]

    try:

        print(
            f"Opening Hoàng Hà URL: "
            f"{product['product_id']}"
        )

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        page.wait_for_timeout(2500)

        # Get page text
        text = page.locator(
            "body"
        ).inner_text()

        # ------------------------------------
        # BASIC PRODUCT VALIDATION
        # ------------------------------------

        if not text:

            print(
                f"SKIP {product['product_id']}: "
                "empty page"
            )

            return None

        # Make sure page contains Belkin
        if "belkin" not in text.lower():

            print(
                f"WARNING {product['product_id']}: "
                "Belkin not found on page"
            )

        # ------------------------------------
        # PRICE EXTRACTION
        # ------------------------------------

        current_price, original_price = (
            extract_prices(text)
        )

        if current_price is None:

            print(
                f"SKIP {product['product_id']}: "
                "price not found"
            )

            return None

        # ------------------------------------
        # DISCOUNT
        # ------------------------------------

        discount_pct = None

        if (
            original_price
            and original_price > current_price
        ):

            discount_pct = round(
                (
                    original_price
                    - current_price
                )
                / original_price
                * 100,
                2,
            )

        # ------------------------------------
        # RESULT
        # ------------------------------------

        result = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),

            "retailer_id": RETAILER_ID,

            "brand": product[
                "brand"
            ],

            "product_id": product[
                "product_id"
            ],

            "product_name": product[
                "product_name"
            ],

            "price": current_price,

            "original_price": (
                original_price
                or ""
            ),

            "discount_pct": (
                discount_pct
                if discount_pct is not None
                else ""
            ),

            "stock_status": "UNKNOWN",

            "promotion": "",

            "url": url,
        }

        print(
            f"SUCCESS {product['product_id']}: "
            f"{current_price:,}đ"
        )

        if original_price:

            print(
                f"Original price: "
                f"{original_price:,}đ"
            )

        if discount_pct is not None:

            print(
                f"Discount: "
                f"{discount_pct}%"
            )

        return result

    except Exception as e:

        print(
            f"Hoàng Hà error "
            f"{product['product_id']}: "
            f"{e}"
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
                "height": 900,
            },

            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/153.0.0.0 "
                "Safari/537.36"
            ),
        )

        for product in products:

            print(
                f"Scraping Hoàng Hà: "
                f"{product['product_id']}"
            )

            result = scrape_product(
                page,
                product,
            )

            if result:

                results.append(
                    result
                )

            time.sleep(1)

        browser.close()

    return results
