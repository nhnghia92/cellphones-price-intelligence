import re
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright


RETAILER_ID = "RET_006"

TARGET_CITIES = [
    "Hồ Chí Minh",
    "Hà Nội",
    "Đà Nẵng",
    "Cần Thơ",
]


def parse_price(text):
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

    current_price = prices[0]
    original_price = None

    for price in prices[1:]:
        if price >= current_price:
            original_price = price
            break

    return current_price, original_price


def normalize_city(address):
    text = address.lower().strip()

    city_aliases = {
        "Hồ Chí Minh": [
            "hồ chí minh",
            "ho chi minh",
            "tp.hcm",
            "tp. hcm",
            "tp hcm",
            "tphcm",
            "tp.hồ chí minh",
            "tp. hồ chí minh",
        ],
        "Hà Nội": [
            "hà nội",
            "ha noi",
        ],
        "Đà Nẵng": [
            "đà nẵng",
            "da nang",
        ],
        "Cần Thơ": [
            "cần thơ",
            "can tho",
        ],
    }

    for city, aliases in city_aliases.items():
        for alias in aliases:
            if alias in text:
                return city

    return None


def get_stock_records(page):
    stock_counts = {
        city: 0
        for city in TARGET_CITIES
    }

    addresses = page.locator(
        "#store-address .stores-address-item.instock .text-item-address"
    )

    count = addresses.count()

    print(
        f"Hoàng Hà available store addresses: {count}"
    )

    for i in range(count):
        try:
            address = addresses.nth(i).inner_text().strip()
        except Exception:
            continue

        if not address:
            continue

        city = normalize_city(address)

        if city:
            stock_counts[city] += 1

    stock_records = []

    for city in TARGET_CITIES:
        stock = stock_counts[city]

        if stock > 0:
            stock_status = "IN_STOCK"
        else:
            stock_status = "OUT_OF_STOCK"

        stock_records.append({
            "city": city,
            "stock": stock,
            "stock_status": stock_status,
        })

        print(
            f"Stock {city}: "
            f"{stock_status} "
            f"({stock})"
        )

    return stock_records


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

        text = page.locator("body").inner_text()

        if not text:
            print(
                f"SKIP {product['product_id']}: "
                "empty page"
            )
            return None

        if "belkin" not in text.lower():
            print(
                f"WARNING {product['product_id']}: "
                "Belkin not found on page"
            )

        current_price, original_price = (
            extract_prices(text)
        )

        if current_price is None:
            print(
                f"SKIP {product['product_id']}: "
                "price not found"
            )
            return None

        stock_records = get_stock_records(page)

        total_stock = sum(
            record["stock"]
            for record in stock_records
        )

        if total_stock > 0:
            stock_status = "IN_STOCK"
        else:
            stock_status = "OUT_OF_STOCK"

        discount_pct = None

        if (
            original_price
            and original_price > current_price
        ):
            discount_pct = round(
                (
                    (
                        original_price
                        - current_price
                    )
                    / original_price
                )
                * 100,
                2,
            )

        result = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),

            "retailer_id": RETAILER_ID,

            "brand": product.get(
                "brand",
                "",
            ),

            "product_id": product.get(
                "product_id",
                "",
            ),

            "product_name": product.get(
                "product_name",
                "",
            ),

            "price": current_price,

            "original_price": (
                original_price
                if original_price is not None
                else ""
            ),

            "discount_pct": (
                discount_pct
                if discount_pct is not None
                else ""
            ),

            "promotion": "",

            "url": url,

            "stock_records": stock_records,
        }

        print(
            f"SUCCESS "
            f"{product['product_id']}: "
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

        print(
            f"Stock: "
            f"{stock_status}"
        )

        print(
            f"Total stock: "
            f"{total_stock}"
        )

        for record in stock_records:
            print(
                f"  {record['city']}: "
                f"{record['stock_status']} "
                f"({record['stock']})"
            )

        return result

    except Exception as e:
        print(
            f"Hoàng Hà error "
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
                results.append(result)

            time.sleep(1)

        browser.close()

    return results
