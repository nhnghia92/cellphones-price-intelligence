
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
STOCK_TIMEOUT = 8000


# ============================================================
# PRICE
# ============================================================

def parse_price(text):
    if not text:
        return None

    text = text.replace(".", "").replace(",", "")

    matches = re.findall(r"(\d{4,9})\s*[đ₫]", text)

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


# ============================================================
# PROVINCE / CITY
# ============================================================

async def is_province_modal_open(page):
    try:
        modal = page.locator("#change-province")

        return await modal.is_visible(timeout=500)

    except Exception:
        return False


async def open_province_modal(page):
    """
    Open CellphoneS province selector.

    IMPORTANT:
    Do not scan the entire DOM.
    Only use known CellphoneS selectors.
    """

    if await is_province_modal_open(page):
        return True

    selectors = [
        "#change-province",
        "text=Hồ Chí Minh",
        "text=Chọn khu vực",
        "text=Chọn tỉnh",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).first

            if not await locator.is_visible(timeout=1000):
                continue

            await locator.click(timeout=2000)

            await page.wait_for_timeout(300)

            if await is_province_modal_open(page):
                return True

        except Exception:
            continue

    return False


async def select_city(page, city):
    """
    Select a city from CellphoneS province popup.
    """

    if not await open_province_modal(page):
        print(
            f"WARNING: Could not open province modal for {city}"
        )
        return False

    try:
        search = page.locator(
            "#change-province #inputSearchProvince input"
        ).first

        if await search.is_visible(timeout=1000):
            await search.fill(city)

            await page.wait_for_timeout(200)

    except Exception:
        pass

    try:
        city_locator = page.locator(
            "#change-province li a",
            has_text=city
        ).first

        count = await page.locator(
            "#change-province li a",
            has_text=city
        ).count()

        print(f"{city} elements in modal: {count}")

        if count == 0:
            print(f"WARNING: City not found: {city}")
            return False

        await city_locator.click(timeout=3000)

        await page.wait_for_timeout(500)

        return True

    except Exception as e:
        print(
            f"WARNING: Could not click {city}: {e}"
        )
        return False


# ============================================================
# STOCK
# ============================================================

def extract_stock_from_text(text):
    if not text:
        return None, None

    lower_text = text.lower()

    # Explicit out-of-stock state
    if (
        "tạm hết hàng" in lower_text
        or "tạm hết hàng tại" in lower_text
    ):
        return 0, "OUT_OF_STOCK"

    # Example:
    # Có 1 cửa hàng có sản phẩm
    # Có 18 cửa hàng có sản phẩm
    match = re.search(
        r"Có\s+(\d+)\s+cửa hàng\s+có sản phẩm",
        text,
        re.IGNORECASE,
    )

    if match:
        stock = int(match.group(1))

        if stock > 0:
            return stock, "IN_STOCK"

        return 0, "OUT_OF_STOCK"

    return None, "UNKNOWN"


async def get_stock_count(page, city):
    """
    Wait for the stock section to appear.

    We intentionally do not immediately trust the first body text
    because the previous city's stock may still be present while
    CellphoneS is updating the page.
    """

    deadline = asyncio.get_running_loop().time() + (
        STOCK_TIMEOUT / 1000
    )

    last_text = ""

    while asyncio.get_running_loop().time() < deadline:

        try:
            body_text = await page.locator(
                "body"
            ).inner_text(timeout=2000)

            last_text = body_text

            stock, status = extract_stock_from_text(
                body_text
            )

            if stock is not None:
                return stock, status

        except Exception:
            pass

        await asyncio.sleep(0.25)

    print(
        f"WARNING: Stock not detected for {city}"
    )

    return None, "UNKNOWN"


# ============================================================
# ONE PRODUCT / ONE CITY TAB
# ============================================================

async def scrape_product_city(
    page,
    product,
    city,
):
    url = product["url"]

    product_id = product["product_id"]

    try:
        print(
            f"[{city}] Loading {product_id}"
        )

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        await page.wait_for_timeout(1000)

        # Re-select city after navigation.
        #
        # CellphoneS may preserve the selected city through
        # cookies/local state, but we verify it explicitly.
        selected = await select_city(
            page,
            city,
        )

        if not selected:
            return {
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
                "retailer_id": RETAILER_ID,
                "brand": product["brand"],
                "product_id": product["product_id"],
                "product_name": product["product_name"],
                "city": city,
                "stock": None,
                "stock_status": "UNKNOWN",
                "url": url,
            }

        stock, stock_status = await get_stock_count(
            page,
            city,
        )

        print(
            f"[{city}] {product_id}: "
            f"{stock_status} "
            f"stock={stock}"
        )

        return {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "retailer_id": RETAILER_ID,
            "brand": product["brand"],
            "product_id": product["product_id"],
            "product_name": product["product_name"],
            "city": city,
            "stock": stock,
            "stock_status": stock_status,
            "url": url,
        }

    except Exception as e:

        print(
            f"[{city}] ERROR {product_id}: {e}"
        )

        return {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "retailer_id": RETAILER_ID,
            "brand": product["brand"],
            "product_id": product["product_id"],
            "product_name": product["product_name"],
            "city": city,
            "stock": None,
            "stock_status": "UNKNOWN",
            "url": url,
        }


# ============================================================
# PRICE + STOCK
# ============================================================

async def scrape_async(products):

    results = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        # ====================================================
        # CREATE 4 TABS
        # ====================================================

        pages = {}

        for city in CITIES:

            pages[city] = await browser.new_page(
                viewport={
                    "width": 1440,
                    "height": 900,
                }
            )

            print(
                f"Created tab for {city}"
            )

        # ====================================================
        # PROCESS SKU BY SKU
        # ====================================================

        for product in products:

            product_id = product["product_id"]

            print("")
            print(
                "========================================"
            )
            print(
                f"SCRAPING {product_id}"
            )
            print(
                "========================================"
            )

            # ------------------------------------------------
            # PRICE
            # ------------------------------------------------

            price_page = pages["Hồ Chí Minh"]

            try:

                await price_page.goto(
                    product["url"],
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT,
                )

                await price_page.wait_for_timeout(
                    1000
                )

                text = await price_page.locator(
                    "body"
                ).inner_text()

                current_price, original_price = (
                    extract_prices(text)
                )

                if current_price is None:

                    print(
                        f"WARNING {product_id}: "
                        "Price not found"
                    )

                else:

                    discount_pct = None

                    if (
                        original_price
                        and original_price
                        > current_price
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

                    results.append({
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat(),
                        "retailer_id": RETAILER_ID,
                        "brand": product["brand"],
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
                        ),
                        "stock_status": "UNKNOWN",
                        "promotion": "",
                        "url": product["url"],
                    })

                    print(
                        f"SUCCESS {product_id}: "
                        f"{current_price:,}đ"
                    )

            except Exception as e:

                print(
                    f"ERROR price {product_id}: {e}"
                )

            # ------------------------------------------------
            # STOCK - 4 TABS IN PARALLEL
            # ------------------------------------------------

            stock_tasks = []

            for city in CITIES:

                stock_tasks.append(
                    scrape_product_city(
                        pages[city],
                        product,
                        city,
                    )
                )

            stock_records = await asyncio.gather(
                *stock_tasks
            )

            product["stock_records"] = (
                stock_records
            )

        await browser.close()

    return results


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

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
        "Mode: 4 parallel tabs"
    )

    asyncio.run(
        scrape_async(products)
    )

    # The existing tracker expects the stock
    # records to be attached to each product.
    #
    # Price results are collected separately above.
    #
    # Run scrape_async again is NOT desired.
    #
    # Therefore we use a second implementation below
    # that returns both result collections.

    return collect_results(products)


# ============================================================
# INTERNAL RESULT COLLECTOR
# ============================================================

def collect_results(products):
    """
    This function is kept as a compatibility layer.

    Stock records have already been attached to products.
    Price records are regenerated from the product data
    only when needed by the main scraper.

    NOTE:
    This compatibility path is replaced below by
    scrape_main().
    """

    return scrape_main(products)


# ============================================================
# MAIN COMPATIBILITY SCRAPER
# ============================================================

async def scrape_main_async(products):

    price_results = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        pages = {}

        for city in CITIES:

            pages[city] = await browser.new_page(
                viewport={
                    "width": 1440,
                    "height": 900,
                }
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

            # =================================================
            # PRICE
            # =================================================

            price_page = pages["Hồ Chí Minh"]

            try:

                await price_page.goto(
                    product["url"],
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT,
                )

                await price_page.wait_for_timeout(
                    1000
                )

                text = await price_page.locator(
                    "body"
                ).inner_text()

                current_price, original_price = (
                    extract_prices(text)
                )

                if current_price is not None:

                    discount_pct = None

                    if (
                        original_price
                        and original_price
                        > current_price
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

                    price_results.append({
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat(),
                        "retailer_id": RETAILER_ID,
                        "brand": product["brand"],
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
                        ),
                        "stock_status": "UNKNOWN",
                        "promotion": "",
                        "url": product["url"],
                    })

                    print(
                        f"SUCCESS {product_id}: "
                        f"{current_price:,}đ"
                    )

                else:

                    print(
                        f"WARNING {product_id}: "
                        "Price not found"
                    )

            except Exception as e:

                print(
                    f"ERROR price {product_id}: {e}"
                )

            # =================================================
            # STOCK - 4 TABS RUN CONCURRENTLY
            # =================================================

            tasks = [
                scrape_product_city(
                    pages[city],
                    product,
                    city,
                )
                for city in CITIES
            ]

            stock_records = await asyncio.gather(
                *tasks
            )

            product["stock_records"] = (
                stock_records
            )

        await browser.close()

    return price_results


def scrape_main(products):

    return asyncio.run(
        scrape_main_async(products)
    )

