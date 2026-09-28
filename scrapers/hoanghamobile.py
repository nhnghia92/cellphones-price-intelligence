import json
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


def get_stock_by_city(page):
    result = {
        city: {
            "status": "OUT_OF_STOCK",
            "stock_count": 0,
        }
        for city in TARGET_CITIES
    }

    addresses = page.locator(
        "#store-address .stores-address-item.instock .text-item-address"
    )

    count = addresses.count()

    print(f"Hoàng Hà available store addresses: {count}")

    for i in range(count):
        try:
            address = addresses.nth(i).inner_text().strip()
        except Exception:
            continue

        if not address:
            continue

        for city in TARGET_CITIES:
            if city.lower() in address.lower():
                result[city]["stock_count"] += 1
                result[city]["status"] = "IN_STOCK"

    for city in TARGET_CITIES:
        status = result[city]["status"]
        stock_count = result[city]["stock_count"]

        print(
            f"Stock {city}: "
            f"{status} "
            f"({stock_count})"
        )

    return result


def scrape_product(page, product):
    url = product["url"]

    try:
        print(f"Opening Hoàng Hà URL: {product['product_id']}")

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        page.wait_for_timeout(2500)

        text = page.locator("body").inner_text()

        if not text:
            print(f"SKIP {product['product_id']}: empty page")
            return None

        if "belkin" not in text.lower():
            print(
                f"WARNING {product['product_id']}: "
                f"Belkin not found on page"
            )

        current_price, original_price = extract_prices(text)

        if current_price is None:
            print(
                f"SKIP {product['product_id']}: "
                f"price not found"
            )
            return None

        stock_by_city = get_stock_by_city(page)

        total_stock = sum(
            item["stock_count"]
            for item in stock_by_city.values()
        )

        if total_stock > 0:
            stock_status = "IN_STOCK"
        else:
            stock_status = "OUT_OF_STOCK"

        discount_pct = None

        if original_price and original_price > current_price:
            discount_pct = round(
                (
                    (original_price - current_price)
                    / original_price
                ) * 100,
                2,
            )

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "retailer_id": RETAILER_ID,
            "brand": product["brand"],
            "product_id": product["product_id"],
            "product_name": product["product_name"],
            "price": current_price,
            "original_price": original_price or "",
            "discount_pct": (
                discount_pct
                if discount_pct is not None
                else ""
            ),
            "stock_status": stock_status,
            "stock_count": total_stock,
            "stock_by_city": json.dumps(
                stock_by_city,
                ensure_ascii=False,
            ),
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
                f"Discount: {discount_pct}%"
            )

        print(f"Stock: {stock_status}")
        print(f"Total stock: {total_stock}")
        print(
            "Stock by city: "
            + json.dumps(
                stock_by_city,
                ensure_ascii=False,
            )
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
        browser = p.chromium.launch(headless=True)

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
