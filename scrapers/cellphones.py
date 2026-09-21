
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
STOCK_TIMEOUT = 10000


# ============================================================
# PRICE
# ============================================================

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


# ============================================================
# TIME
# ============================================================

def now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# PROVINCE MODAL
# ============================================================

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
    """
    Wait for CellphoneS page to actually render.

    We do NOT use a fixed 1-second sleep.
    """

    try:
        await page.locator(
            "body"
        ).wait_for(
            state="visible",
            timeout=ELEMENT_TIMEOUT,
        )
    except Exception:
        pass

    # Wait for either the province selector
    # or the product page content.
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
    """
    Open CellphoneS province modal.

    No broad DOM scanning.
    No long fallback loop.
    """

    if await is_modal_open(page):
        return True

    selectors = [
        "text=Hồ Chí Minh",
        "text=Chọn khu vực",
        "text=Chọn tỉnh",
    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            ).first

            await locator.wait_for(
                state="visible",
                timeout=1500,
            )

            await locator.click(
                timeout=2500
            )

            try:
                await page.locator(
                    "#change-province"
                ).wait_for(
                    state="visible",
                    timeout=2500,
                )

                return True

            except Exception:
                pass

        except Exception:
            continue

    return False


# ============================================================
# CITY SELECTION
# ============================================================

async def select_city(page, city):
    """
    Open province selector and select exact city.
    """

    # If modal is not open, open it.
    if not await is_modal_open(page):

        opened = await open_province_modal(
            page
        )

        if not opened:
            print(
                f"WARNING: Could not open "
                f"province modal for {city}"
            )

            return False

    # --------------------------------------------------------
    # Search city
    # --------------------------------------------------------

    try:

        search = page.locator(
            "#change-province "
            "#inputSearchProvince input"
        ).first

        await search.wait_for(
            state="visible",
            timeout=2000,
        )

        await search.fill(city)

        await asyncio.sleep(0.15)

    except Exception:
        pass

    # --------------------------------------------------------
    # Find exact city
    # --------------------------------------------------------

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
                f"WARNING: City not found: "
                f"{city}"
            )

            return False

        city_link = city_links.first

        await city_link.wait_for(
            state="visible",
            timeout=2000,
        )

        await city_link.click(
            timeout=2500
        )

        # Give CellphoneS a short window to
        # start updating the stock section.
        await asyncio.sleep(0.2)

        return True

    except Exception as e:

        print(
            f"WARNING: Could not click "
            f"{city}: {e}"
        )

        return False


# ============================================================
# STOCK PARSER
# ============================================================

def parse_stock_text(text):
    if not text:
        return None, "UNKNOWN"

    lower = text.lower()

    # Explicit out-of-stock
    if (
        "tạm hết hàng" in lower
        or "tạm hết hàng tại" in lower
    ):
        return 0, "OUT_OF_STOCK"

    # Example:
    #
    # Có 1 cửa hàng có sản phẩm
    # Có 18 cửa hàng có sản phẩm
    #
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


# ============================================================
# STOCK WAIT
# ============================================================

async def wait_for_stock(page, city):
    """
    Wait for actual stock information.

    IMPORTANT:
    Do not immediately parse the page after clicking city.
    CellphoneS updates the content asynchronously.
    """

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
        f"WARNING: Stock not detected "
        f"for {city}"
    )

    return None, "UNKNOWN"


# ============================================================
# ONE CITY / ONE PRODUCT
# ============================================================

async def scrape_city(
    page,
    product,
    city,
):
    product_id = product[
        "product_id"
    ]

    url = product[
        "url"
    ]

    try:

        print(
            f"[{city}] Loading "
            f"{product_id}"
        )

        # ----------------------------------------------------
        # LOAD PRODUCT
        # ----------------------------------------------------

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        await wait_for_page_ready(
            page
        )

        # ----------------------------------------------------
        # SELECT CITY
        # ----------------------------------------------------

        selected = await select_city(
            page,
            city,
        )

        if not selected:

            return {
                "timestamp": now_iso(),
                "retailer_id": RETAILER_ID,
                "brand": product["brand"],
                "product_id": product[
                    "product_id"
                ],
                "product_name": product[
                    "product_name"
                ],
                "city": city,
                "stock": None,
                "stock_status": "UNKNOWN",
                "url": url,
            }

        # ----------------------------------------------------
        # WAIT STOCK
        # ----------------------------------------------------

        stock, status = await wait_for_stock(
            page,
            city,
        )

        print(
            f"[{city}] {product_id}: "
            f"{status} stock={stock}"
        )

        return {
            "timestamp": now_iso(),
            "retailer_id": RETAILER_ID,
            "brand": product["brand"],
            "product_id": product[
                "product_id"
            ],
            "product_name": product[
                "product_name"
            ],
            "city": city,
            "stock": stock,
            "stock_status": status,
            "url": url,
        }

    except Exception as e:

        print(
            f"[{city}] ERROR "
            f"{product_id}: {e}"
        )

        return {
            "timestamp": now_iso(),
            "retailer_id": RETAILER_ID,
            "brand": product["brand"],
            "product_id": product[
                "product_id"
            ],
            "product_name": product[
                "product_name"
            ],
            "city": city,
            "stock": None,
            "stock_status": "UNKNOWN",
            "url": url,
        }


# ============================================================
# MAIN ASYNC SCRAPER
# ============================================================

async def scrape_async(products):

    price_results = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        # ====================================================
        # CREATE FOUR TABS
        # ====================================================

        pages = {}

        for city in CITIES:

            pages[city] = (
                await browser.new_page(
                    viewport={
                        "width": 1440,
                        "height": 900,
                    }
                )
            )

            print(
                f"Created tab for {city}"
            )

        # ====================================================
        # PROCESS PRODUCTS
        # ====================================================

        for product in products:

            product_id = product[
                "product_id"
            ]

            print("")
            print(
                "========================================"
            )
            print(
                f"SCRAPING CellphoneS: "
                f"{product_id}"
            )
            print(
                "========================================"
            )

            # =================================================
            # PRICE
            # =================================================

            price_page = pages[
                "Hồ Chí Minh"
            ]

            try:

                await price_page.goto(
                    product["url"],
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT,
                )

                await wait_for_page_ready(
                    price_page
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
                        "timestamp": now_iso(),
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
                        ),
                        "stock_status": "UNKNOWN",
                        "promotion": "",
                        "url": product[
                            "url"
                        ],
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
                    f"ERROR price "
                    f"{product_id}: {e}"
                )

            # =================================================
            # STOCK - FOUR TABS IN PARALLEL
            # =================================================

            stock_tasks = []

            for city in CITIES:

                stock_tasks.append(
                    scrape_city(
                        pages[city],
                        product,
                        city,
                    )
                )

            stock_records = await asyncio.gather(
                *stock_tasks
            )

            # -------------------------------------------------
            # IMPORTANT
            #
            # tracker.py already knows how to read
            # product["stock_records"].
            # -------------------------------------------------

            product[
                "stock_records"
            ] = stock_records

        # ====================================================
        # CLOSE BROWSER
        # ====================================================

        await browser.close()

    return price_results


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

    results = asyncio.run(
        scrape_async(products)
    )

    return results
