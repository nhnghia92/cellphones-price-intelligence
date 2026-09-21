import asyncio
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright

RETAILER_ID = "RET_005"

CITIES = [
    "Hồ Chí Minh",
    "Hà Nội",
    "Cần Thơ",
    "Đà Nẵng",
]

PAGE_TIMEOUT = 30000
STOCK_TIMEOUT = 15000


def clean(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def parse_price(text):
    if not text:
        return None

    text = text.replace(".", "").replace(",", "")

    matches = re.findall(r"(\d{5,8})\s*[đ₫]", text)

    if not matches:
        matches = re.findall(r"(\d{5,8})", text)

    values = [
        int(value)
        for value in matches
        if 50000 <= int(value) <= 100000000
    ]

    if not values:
        return None

    return values[0]


def is_modal_open(page):
    try:
        return awaitable_is_visible(
            page.locator("#change-province").first
        )
    except Exception:
        return False


async def awaitable_is_visible(locator):
    try:
        return await locator.is_visible(timeout=500)
    except Exception:
        return False


async def open_province_modal(page):
    if await awaitable_is_visible(
        page.locator("#change-province").first
    ):
        print("Province modal already open.")
        return True

    selectors = [
        "text=Hồ Chí Minh",
        "text=Hà Nội",
        "text=Cần Thơ",
        "text=Đà Nẵng",
        "text=Chọn khu vực",
        "text=Chọn tỉnh",
    ]

    for attempt in range(5):
        print(
            f"Opening province modal... attempt {attempt + 1}/5"
        )

        for selector in selectors:
            try:
                locator = page.locator(selector)

                count = await locator.count()

                for i in range(min(count, 10)):
                    element = locator.nth(i)

                    try:
                        if not await element.is_visible(
                            timeout=500
                        ):
                            continue

                        await element.evaluate(
                            "(el) => el.click()"
                        )

                        await page.wait_for_timeout(500)

                        if await awaitable_is_visible(
                            page.locator("#change-province").first
                        ):
                            print("Province modal opened.")
                            return True

                    except Exception:
                        continue

            except Exception:
                continue

        await page.wait_for_timeout(1000)

    print("WARNING: Could not open province modal.")

    return False


async def select_city(page, city):
    if not await open_province_modal(page):
        return False

    print(f"Searching province: {city}")

    try:
        search = page.locator(
            "#inputSearchProvince input"
        ).first

        await search.wait_for(
            state="visible",
            timeout=3000
        )

        await search.fill("")
        await search.fill(city)

        await page.wait_for_timeout(500)

    except Exception as error:
        print(f"Search input error: {error}")
        return False

    city_locator = page.locator(
        "#change-province li a"
    ).filter(
        has_text=city
    )

    try:
        count = await city_locator.count()

        print(
            f"{city} elements in modal: {count}"
        )

        if count == 0:
            print(
                f"Province not found: {city}"
            )
            return False

        city_link = city_locator.first

        await city_link.wait_for(
            state="visible",
            timeout=3000
        )

        await city_link.evaluate(
            "(el) => el.click()"
        )

        print(f"{city} clicked.")

        await page.wait_for_timeout(500)

        return True

    except Exception as error:
        print(
            f"Could not click {city}: {error}"
        )

        return False


async def get_stock_count(page, city):
    print(f"Checking stock for {city}...")

    stock_pattern = re.compile(
        r"Có\s+(\d+)\s+cửa hàng\s+có sản phẩm",
        re.IGNORECASE
    )

    out_pattern = re.compile(
        r"TẠM HẾT HÀNG|tạm hết hàng tại|SẮP VỀ HÀNG",
        re.IGNORECASE
    )

    attempts = STOCK_TIMEOUT // 300

    for _ in range(attempts):
        try:
            stock_locator = page.get_by_text(
                stock_pattern
            )

            count = await stock_locator.count()

            if count > 0:
                for i in range(count):
                    try:
                        element = stock_locator.nth(i)

                        if not await element.is_visible(
                            timeout=300
                        ):
                            continue

                        text = clean(
                            await element.inner_text()
                        )

                        match = stock_pattern.search(text)

                        if match:
                            stock = int(
                                match.group(1)
                            )

                            print(
                                f"Stock text found: {text}"
                            )

                            print(
                                f"{city}: "
                                f"{stock} cửa hàng có sản phẩm"
                            )

                            return {
                                "stock": stock,
                                "stock_status": (
                                    "IN_STOCK"
                                    if stock > 0
                                    else "OUT_OF_STOCK"
                                )
                            }

                    except Exception:
                        continue

        except Exception:
            pass

        try:
            body_text = clean(
                await page.locator("body").inner_text(
                    timeout=1500
                )
            )

            if out_pattern.search(body_text):
                print(f"{city}: TẠM HẾT HÀNG")

                return {
                    "stock": 0,
                    "stock_status": "OUT_OF_STOCK"
                }

        except Exception:
            pass

        await page.wait_for_timeout(300)

    print(
        f"{city}: STOCK NOT FOUND "
        f"after {STOCK_TIMEOUT / 1000:.0f} seconds"
    )

    return {
        "stock": 0,
        "stock_status": "UNKNOWN"
    }


async def scrape_product(browser, product):
    print("")
    print(
        f"SCRAPING CellphoneS: "
        f"{product['product_id']}"
    )

    page = await browser.new_page(
        viewport={
            "width": 1440,
            "height": 1000
        }
    )

    page.set_default_timeout(5000)

    current_price = None
    stock_records = []

    try:
        await page.goto(
            product["url"],
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT
        )

        await page.locator("body").wait_for(
            state="visible",
            timeout=10000
        )

        body_text = clean(
            await page.locator("body").inner_text()
        )

        current_price = parse_price(body_text)

        for city in CITIES:
            print("")
            print(
                "========================================"
            )
            print(
                f"CHECKING {city}"
            )
            print(
                "========================================"
            )

            selected = await select_city(
                page,
                city
            )

            if not selected:
                print(
                    f"{city}: FAILED TO SELECT"
                )

                stock_records.append({
                    "city": city,
                    "stock": 0,
                    "stock_status": "UNKNOWN"
                })

                continue

            stock = await get_stock_count(
                page,
                city
            )

            stock_records.append({
                "city": city,
                "stock": stock["stock"],
                "stock_status": stock["stock_status"]
            })

    except Exception as error:
        print(
            f"ERROR {product['product_id']}: "
            f"{type(error).__name__}: {error}"
        )

    finally:
        await page.close()

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    result = {
        "timestamp": timestamp,
        "retailer_id": RETAILER_ID,
        "brand": product["brand"],
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "price": current_price,
        "original_price": "",
        "discount_pct": "",
        "stock_status": "UNKNOWN",
        "promotion": "",
        "url": product["url"],
        "stock_records": stock_records
    }

    if current_price:
        print(
            f"SUCCESS {product['product_id']}: "
            f"{current_price:,}đ"
        )
    else:
        print(
            f"SUCCESS {product['product_id']}: "
            f"price UNKNOWN"
        )

    print(
        f"Stock records: {len(stock_records)}"
    )

    return result


async def scrape_async(products):
    print("")
    print(
        "========================================"
    )
    print(
        "CELLPHONES SCRAPER"
    )
    print(
        "========================================"
    )
    print(
        f"Products: {len(products)}"
    )
    print(
        f"Cities: {len(CITIES)}"
    )
    print(
        "Mode: 1 browser + 1 page per SKU"
    )

    results = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        try:
            for product in products:
                result = await scrape_product(
                    browser,
                    product
                )

                results.append(result)

        finally:
            await browser.close()

    return results


def scrape(products):
    return asyncio.run(
        scrape_async(products)
    )
