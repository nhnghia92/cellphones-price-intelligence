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
ELEMENT_TIMEOUT = 5000
STOCK_TIMEOUT = 15000


def parse_price(text):
    if not text:
        return None

    text = text.replace(".", "").replace(",", "")

    matches = re.findall(
        r"(\d{4,9})\s*[đ₫]",
        text
    )

    prices = []

    for value in matches:
        price = int(value)

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


def now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


async def is_modal_open(page):
    try:
        modal = page.locator(
            "#change-province"
        ).first

        return await modal.is_visible(
            timeout=500
        )

    except Exception:
        return False


async def wait_for_page_ready(page):
    try:
        await page.locator(
            "body"
        ).wait_for(
            state="visible",
            timeout=ELEMENT_TIMEOUT,
        )
    except Exception:
        pass

    selectors = [
        "#change-province",
        "#inputSearchProvince",
        "body",
    ]

    for selector in selectors:
        try:
            await page.locator(
                selector
            ).first.wait_for(
                state="visible",
                timeout=ELEMENT_TIMEOUT,
            )

            return True

        except Exception:
            continue

    return False


async def open_province_modal(page):
    if await is_modal_open(page):
        return True

    selectors = [
        "text=Hồ Chí Minh",
        "text=Chọn khu vực",
        "text=Chọn tỉnh",
    ]

    for attempt in range(5):
        print(
            f"Opening province modal... attempt {attempt + 1}/5"
        )

        for selector in selectors:
            try:
                locator = page.locator(
                    selector
                ).first

                await locator.wait_for(
                    state="visible",
                    timeout=1500,
                )

                try:
                    await locator.click(
                        timeout=2500
                    )
                except Exception:
                    await locator.evaluate(
                        "(el) => el.click()"
                    )

                try:
                    await page.locator(
                        "#change-province"
                    ).wait_for(
                        state="visible",
                        timeout=2500,
                    )

                    print(
                        "Province modal opened."
                    )

                    return True

                except Exception:
                    continue

            except Exception:
                continue

    return False


async def select_city(page, city):
    if not await is_modal_open(page):
        opened = await open_province_modal(
            page
        )

        if not opened:
            print(
                f"WARNING: Could not open province modal for {city}"
            )

            return False

    try:
        search = page.locator(
            "#inputSearchProvince input"
        ).first

        await search.wait_for(
            state="visible",
            timeout=3000,
        )

        await search.fill(city)

        await asyncio.sleep(0.15)

    except Exception as e:
        print(
            f"WARNING: Province search failed for {city}: {e}"
        )

        return False

    city_links = page.locator(
        "#change-province li a",
        has_text=city,
    )

    try:
        count = await city_links.count()

        print(
            f"{city} elements in modal: {count}"
        )

        if count == 0:
            print(
                f"WARNING: City not found: {city}"
            )

            return False

        city_link = city_links.first

        await city_link.wait_for(
            state="visible",
            timeout=3000,
        )

        try:
            await city_link.click(
                timeout=2500
            )
        except Exception:
            await city_link.evaluate(
                "(el) => el.click()"
            )

        print(
            f"{city} clicked."
        )

        await asyncio.sleep(0.2)

        return True

    except Exception as e:
        print(
            f"WARNING: Could not click {city}: {e}"
        )

        return False


def parse_stock_text(text):
    if not text:
        return None, "UNKNOWN"

    lower = text.lower()

    if (
        "tạm hết hàng" in lower
        or "sắp về hàng" in lower
    ):
        return 0, "OUT_OF_STOCK"

    match = re.search(
        r"Có\s+(\d+)\s+cửa hàng\s+có sản phẩm",
        text,
        re.IGNORECASE,
    )

    if match:
        stock = int(
            match.group(1)
        )

        if stock > 0:
            return stock, "IN_STOCK"

        return 0, "OUT_OF_STOCK"

    return None, "UNKNOWN"


async def wait_for_stock(page, city):
    loop = asyncio.get_running_loop()

    deadline = (
        loop.time()
        + STOCK_TIMEOUT / 1000
    )

    while loop.time() < deadline:
        try:
            body_text = await page.locator(
                "body"
            ).inner_text(
                timeout=2000
            )

            stock, status = parse_stock_text(
                body_text
            )

            if stock is not None:
                return stock, status

        except Exception:
            pass

        await asyncio.sleep(
            0.25
        )

    print(
        f"WARNING: Stock not detected for {city}"
    )

    return None, "UNKNOWN"


def build_stock_record(
    product,
    city,
    stock,
    status,
):
    return {
        "timestamp": now_iso(),
        "retailer_id": RETAILER_ID,
        "brand": product["brand"],
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "city": city,
        "stock": stock,
        "stock_status": status,
        "url": product["url"],
    }


async def scrape_city(
    page,
    product,
    city,
):
    product_id = product["product_id"]

    try:
        print(
            f"[{city}] Checking {product_id}"
        )

        selected = await select_city(
            page,
            city,
        )

        if not selected:
            return build_stock_record(
                product,
                city,
                None,
                "UNKNOWN",
            )

        print(
            f"Checking stock for {city}..."
        )

        stock, status = await wait_for_stock(
            page,
            city,
        )

        if status == "OUT_OF_STOCK":
            print(
                f"{city}: TẠM HẾT HÀNG"
            )

        elif status == "IN_STOCK":
            print(
                f"{city}: {stock} cửa hàng có sản phẩm"
            )

        else:
            print(
                f"{city}: STOCK UNKNOWN"
            )

        return build_stock_record(
            product,
            city,
            stock,
            status,
        )

    except Exception as e:
        print(
            f"[{city}] ERROR {product_id}: {e}"
        )

        return build_stock_record(
            product,
            city,
            None,
            "UNKNOWN",
        )


async def scrape_product(
    page,
    product,
):
    product_id = product["product_id"]
    url = product["url"]

    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=PAGE_TIMEOUT,
    )

    await wait_for_page_ready(
        page
    )

    text = await page.locator(
        "body"
    ).inner_text()

    current_price, original_price = extract_prices(
        text
    )

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

    stock_records = []

    for city in CITIES:
        if city != CITIES[0]:
            await open_province_modal(
                page
            )

        stock_record = await scrape_city(
            page,
            product,
            city,
        )

        stock_records.append(
            stock_record
        )

    if current_price is not None:
        print(
            f"SUCCESS {product_id}: {current_price:,}đ"
        )
    else:
        print(
            f"WARNING {product_id}: Price not found"
        )

    return {
        "timestamp": now_iso(),
        "retailer_id": RETAILER_ID,
        "brand": product["brand"],
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "price": current_price,
        "original_price": original_price or "",
        "discount_pct": discount_pct,
        "stock_status": "UNKNOWN",
        "promotion": "",
        "url": url,
        "stock_records": stock_records,
    }


async def scrape_async(products):
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page(
            viewport={
                "width": 1440,
                "height": 900,
            }
        )

        print(
            "Created single CellphoneS tab"
        )

        for product in products:
            product_id = product["product_id"]

            print("")
            print(
                "========================================"
            )
            print(
                f"SCRAPING CellphoneS: {product_id}"
            )
            print(
                "========================================"
            )

            try:
                result = await scrape_product(
                    page,
                    product,
                )

                results.append(
                    result
                )

                print(
                    f"Stock records: "
                    f"{len(result['stock_records'])}"
                )

            except Exception as e:
                print(
                    f"ERROR {product_id}: {e}"
                )

        await browser.close()

    return results


def scrape(products):
    print("")
    print(
        "========================================"
    )
    print(
        "CELLPHONES PRICE + STOCK SCRAPER"
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
        "Mode: 1 browser + 1 tab"
    )

    return asyncio.run(
        scrape_async(products)
    )
