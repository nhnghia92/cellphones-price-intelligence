import re
import time
import json
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright


RETAILER_ID = "RET_006"

STOCK_CITIES = [
    "Hồ Chí Minh",
    "Hà Nội",
    "Cần Thơ",
    "Đà Nẵng",
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

    return (
        current_price,
        original_price,
    )


def normalize_text(text):
    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def deduplicate(items):
    result = []
    seen = set()

    for item in items:
        value = normalize_text(item)

        if not value:
            continue

        key = value.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


def get_stock_area(page):
    candidates = [
        "text=Cửa hàng còn hàng",
        "text=Đang có sẵn hàng",
        "text=Có  Cửa hàng còn hàng",
    ]

    for selector in candidates:
        try:
            locator = page.locator(
                selector
            )

            if locator.count() == 0:
                continue

            element = locator.first

            for _ in range(6):
                try:
                    parent = element.locator(
                        ".."
                    )

                    text = normalize_text(
                        parent.inner_text()
                    )

                    if (
                        "Cửa hàng còn hàng"
                        in text
                        or "Đang có sẵn hàng"
                        in text
                    ):
                        return parent

                    element = parent

                except Exception:
                    break

        except Exception:
            continue

    return None


def get_region_control(page):
    selectors = [
        "input[placeholder*='Tất cả khu vực']",
        "input[value*='Tất cả khu vực']",
        "button:has-text('Tất cả khu vực')",
        "[role='combobox']",
    ]

    for selector in selectors:
        try:
            locator = page.locator(
                selector
            )

            count = locator.count()

            for i in range(count):
                element = locator.nth(i)

                try:
                    text = normalize_text(
                        element.inner_text(
                            timeout=500
                        )
                    )

                except Exception:
                    text = ""

                try:
                    value = normalize_text(
                        element.get_attribute(
                            "value"
                        ) or ""
                    )

                except Exception:
                    value = ""

                combined = (
                    f"{text} {value}"
                ).lower()

                if (
                    "tất cả khu vực"
                    in combined
                ):
                    return element

        except Exception:
            continue

    return None


def select_city(page, city):
    control = get_region_control(page)

    if not control:
        print(
            f"Stock {city}: "
            "region control not found"
        )

        return False

    try:
        control.click(
            timeout=3000
        )

    except Exception as e:
        print(
            f"Stock {city}: "
            f"cannot open region selector: {e}"
        )

        return False

    page.wait_for_timeout(
        500
    )

    selectors = [
        f"text={city}",
        f"button:has-text('{city}')",
        f"[role='option']:has-text('{city}')",
        f"li:has-text('{city}')",
    ]

    for selector in selectors:
        try:
            locator = page.locator(
                selector
            )

            count = locator.count()

            for i in range(count):
                element = locator.nth(i)

                try:
                    if not element.is_visible():
                        continue
                except Exception:
                    pass

                try:
                    element.click(
                        timeout=2000
                    )

                    page.wait_for_timeout(
                        1000
                    )

                    print(
                        f"Stock {city}: "
                        "region selected"
                    )

                    return True

                except Exception:
                    continue

        except Exception:
            continue

    print(
        f"Stock {city}: "
        "city option not found"
    )

    return False


def get_store_dropdown(page):
    keywords = [
        "Đang có sẵn hàng",
        "Tạm hết",
        "Tạm hết - Nhận hàng sau",
    ]

    for keyword in keywords:
        try:
            locator = page.get_by_text(
                keyword,
                exact=False,
            )

            count = locator.count()

            for i in range(count):
                element = locator.nth(i)

                try:
                    if not element.is_visible():
                        continue
                except Exception:
                    pass

                parent = element

                for _ in range(8):
                    try:
                        text = normalize_text(
                            parent.inner_text()
                        )

                        if (
                            "Đang có sẵn hàng"
                            in text
                            and
                            (
                                "Tạm hết"
                                in text
                                or
                                "Tạm hết - Nhận"
                                in text
                            )
                        ):
                            return parent

                        parent = parent.locator(
                            ".."
                        )

                    except Exception:
                        break

        except Exception:
            continue

    return None


def extract_store_sections(page):
    container = get_store_dropdown(
        page
    )

    if not container:
        return [], []

    try:
        lines = container.inner_text(
            timeout=3000
        ).splitlines()

    except Exception:
        return [], []

    available = []
    unavailable = []

    section = None

    for raw_line in lines:
        line = normalize_text(
            raw_line
        )

        if not line:
            continue

        lower = line.lower()

        if (
            "đang có sẵn hàng"
            in lower
        ):
            section = "available"
            continue

        if (
            "tạm hết"
            in lower
        ):
            section = "unavailable"
            continue

        if section == "available":
            available.append(line)

        elif section == "unavailable":
            unavailable.append(line)

    ignored = {
        "cửa hàng",
        "tìm kiếm",
        "tất cả khu vực",
        "đang có sẵn hàng",
    }

    available = [
        item
        for item in available
        if item.lower()
        not in ignored
    ]

    unavailable = [
        item
        for item in unavailable
        if item.lower()
        not in ignored
    ]

    return (
        deduplicate(available),
        deduplicate(unavailable),
    )


def scrape_city_stock(page, city):
    result = {
        "city": city,
        "status": "UNKNOWN",
        "stock_count": 0,
        "available_stores": [],
        "unavailable_stores": [],
    }

    if not select_city(
        page,
        city,
    ):
        return result

    page.wait_for_timeout(
        700
    )

    available, unavailable = (
        extract_store_sections(page)
    )

    result[
        "available_stores"
    ] = available

    result[
        "unavailable_stores"
    ] = unavailable

    result[
        "stock_count"
    ] = len(available)

    if available:
        result["status"] = "IN_STOCK"

    elif unavailable:
        result["status"] = "OUT_OF_STOCK"

    print(
        f"Stock {city}: "
        f"{result['status']} | "
        f"available={len(available)} | "
        f"unavailable={len(unavailable)}"
    )

    for store in available:
        print(
            f"  + {store}"
        )

    for store in unavailable:
        print(
            f"  - {store}"
        )

    return result


def scrape_stock(page):
    results = []

    for city in STOCK_CITIES:
        result = scrape_city_stock(
            page,
            city,
        )

        results.append(
            result
        )

        page.wait_for_timeout(
            500
        )

    if any(
        item["status"] == "IN_STOCK"
        for item in results
    ):
        overall_status = "IN_STOCK"

    elif all(
        item["status"] == "OUT_OF_STOCK"
        for item in results
    ):
        overall_status = "OUT_OF_STOCK"

    else:
        overall_status = "UNKNOWN"

    return (
        overall_status,
        results,
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

        page.wait_for_timeout(
            2500
        )

        text = page.locator(
            "body"
        ).inner_text()

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

        stock_status, stock_by_city = (
            scrape_stock(page)
        )

        stock_data = {
            item["city"]: {
                "status": item[
                    "status"
                ],
                "stock_count": item[
                    "stock_count"
                ],
                "available_stores": item[
                    "available_stores"
                ],
                "unavailable_stores": item[
                    "unavailable_stores"
                ],
            }
            for item in stock_by_city
        }

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

            "stock_status": stock_status,

            "promotion": "",

            "stock_by_city": json.dumps(
                stock_data,
                ensure_ascii=False,
            ),

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

        print(
            f"Stock: "
            f"{stock_status}"
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
