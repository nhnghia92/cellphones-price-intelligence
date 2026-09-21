import asyncio
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

RETAILER_ID = "RET_005"

CITIES = [
    "Hồ Chí Minh",
    "Hà Nội",
    "Cần Thơ",
    "Đà Nẵng",
]

PAGE_TIMEOUT = 45000
STOCK_TIMEOUT = 15000


def parse_price(text):
    if not text:
        return None

    text = text.replace(".", "").replace(",", "")

    matches = re.findall(r"(\d{5,8})\s*[đ₫]", text)

    if not matches:
        matches = re.findall(r"(\d{5,8})", text)

    if not matches:
        return None

    values = [int(x) for x in matches if 50000 <= int(x) <= 100000000]

    if not values:
        return None

    return values[0]


def parse_stock_text(text):
    if not text:
        return {
            "stock": 0,
            "stock_status": "UNKNOWN"
        }

    normalized = re.sub(r"\s+", " ", text.strip().lower())

    if "tạm hết hàng" in normalized:
        return {
            "stock": 0,
            "stock_status": "OUT_OF_STOCK"
        }

    if "sắp về hàng" in normalized:
        return {
            "stock": 0,
            "stock_status": "OUT_OF_STOCK"
        }

    match = re.search(
        r"có\s+(\d+)\s+cửa hàng\s+có\s+sản phẩm",
        normalized
    )

    if match:
        count = int(match.group(1))

        return {
            "stock": count,
            "stock_status": "IN_STOCK" if count > 0 else "OUT_OF_STOCK"
        }

    return {
        "stock": 0,
        "stock_status": "UNKNOWN"
    }


async def wait_for_page_ready(page):
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
    except PlaywrightTimeoutError:
        pass

    await page.wait_for_timeout(1500)


async def open_province_modal(page):
    button = page.locator("#change-province")

    try:
        await button.wait_for(state="visible", timeout=10000)
    except PlaywrightTimeoutError:
        return False

    try:
        await button.click(timeout=5000)
    except Exception:
        try:
            await button.evaluate("(el) => el.click()")
        except Exception:
            return False

    try:
        await page.locator("#inputSearchProvince input").wait_for(
            state="visible",
            timeout=5000
        )
        return True
    except PlaywrightTimeoutError:
        return False


async def select_city(page, city):
    if not await open_province_modal(page):
        return False

    search_input = page.locator("#inputSearchProvince input")

    try:
        await search_input.fill(city)
        await page.wait_for_timeout(500)
    except Exception:
        return False

    city_locator = page.locator(
        "#change-province li a"
    ).filter(has_text=city).first

    try:
        count = await city_locator.count()

        if count == 0:
            return False

        await city_locator.wait_for(
            state="visible",
            timeout=5000
        )

        await city_locator.evaluate("(el) => el.click()")

    except Exception:
        return False

    await page.wait_for_timeout(2000)

    return True


async def get_stock_state(page, city):
    selectors = [
        "text=TẠM HẾT HÀNG",
        "text=SẮP VỀ HÀNG",
        "text=/Có \\d+ cửa hàng có sản phẩm/"
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).first

            if await locator.count() > 0:
                try:
                    text = await locator.inner_text(timeout=3000)
                except Exception:
                    text = await locator.text_content(timeout=3000)

                result = parse_stock_text(text)

                if result["stock_status"] != "UNKNOWN":
                    return result

        except Exception:
            pass

    deadline = asyncio.get_running_loop().time() + STOCK_TIMEOUT / 1000

    while asyncio.get_running_loop().time() < deadline:
        try:
            body_text = await page.locator("body").inner_text(timeout=3000)

            result = parse_stock_text(body_text)

            if result["stock_status"] != "UNKNOWN":
                return result

        except Exception:
            pass

        await page.wait_for_timeout(1000)

    return {
        "stock": 0,
        "stock_status": "UNKNOWN"
    }


async def scrape_city(browser, product, city):
    page = await browser.new_page()

    try:
        print(f"[{city}] Checking {product['product_id']}")

        await page.goto(
            product["url"],
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT
        )

        await wait_for_page_ready(page)

        selected = await select_city(page, city)

        if not selected:
            print(f"{city}: FAILED_TO_SELECT_CITY")

            return {
                "city": city,
                "stock": 0,
                "stock_status": "UNKNOWN"
            }

        print(f"Checking stock for {city}...")

        stock = await get_stock_state(page, city)

        if stock["stock_status"] == "IN_STOCK":
            print(
                f"{city}: {stock['stock']} cửa hàng có sản phẩm"
            )
        elif stock["stock_status"] == "OUT_OF_STOCK":
            print(f"{city}: OUT_OF_STOCK")
        else:
            print(f"{city}: UNKNOWN")

        return {
            "city": city,
            "stock": stock["stock"],
            "stock_status": stock["stock_status"]
        }

    except Exception as e:
        print(f"{city}: ERROR - {type(e).__name__}: {e}")

        return {
            "city": city,
            "stock": 0,
            "stock_status": "UNKNOWN"
        }

    finally:
        await page.close()


async def scrape_product(browser, product):
    print("")
    print(f"SCRAPING CellphoneS: {product['product_id']}")

    price_page = await browser.new_page()

    current_price = None
    original_price = None

    try:
        await price_page.goto(
            product["url"],
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT
        )

        await wait_for_page_ready(price_page)

        body_text = await price_page.locator("body").inner_text()

        current_price = parse_price(body_text)

        if current_price is None:
            print(
                f"WARNING {product['product_id']}: price not found"
            )

    except Exception as e:
        print(
            f"WARNING {product['product_id']}: price error - "
            f"{type(e).__name__}: {e}"
        )

    finally:
        await price_page.close()

    stock_records = []

    for city in CITIES:
        record = await scrape_city(
            browser,
            product,
            city
        )

        stock_records.append(record)

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
        "original_price": original_price or "",
        "discount_pct": "",
        "stock_status": "UNKNOWN",
        "promotion": "",
        "url": product["url"],
        "stock_records": stock_records,
    }

    print(
        f"SUCCESS {product['product_id']}: "
        f"{current_price:,}đ"
        if current_price
        else f"SUCCESS {product['product_id']}: price UNKNOWN"
    )

    print(f"Stock records: {len(stock_records)}")

    return result


async def scrape_async(products):
    print("")
    print("========================================")
    print("CELLPHONES SCRAPER")
    print("========================================")
    print(f"Products: {len(products)}")
    print(f"Cities: {len(CITIES)}")
    print("Mode: 1 browser + fresh page per city")
    print("")

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
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
    return asyncio.run(scrape_async(products))
