import re
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright


RETAILER_ID = "RET_005"

CITIES = [
    "Hồ Chí Minh",
    "Hà Nội",
    "Cần Thơ",
    "Đà Nẵng",
]


# =========================================================
# PRICE
# =========================================================

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


# =========================================================
# CELLPHONES STOCK
# =========================================================

def open_province_modal(page):
    """
    Open CellphoneS province selection popup.
    """

    modal = page.locator(
        "#change-province"
    )

    try:
        if modal.is_visible():
            print("Province modal already open.")
            return True
    except Exception:
        pass

    print("Opening province modal...")

    # Click current province / province selector
    selectors = [
        "#change-province",
        "[data-target='#change-province']",
        "text=Hồ Chí Minh",
    ]

    clicked = False

    for selector in selectors:

        try:
            locator = page.locator(selector).first

            if locator.is_visible():
                locator.click()
                clicked = True
                break

        except Exception:
            continue

    if not clicked:
        print("WARNING: Could not click province selector.")
        return False

    try:
        page.locator(
            "#change-province"
        ).wait_for(
            state="visible",
            timeout=5000
        )

        print("Province modal opened.")
        return True

    except Exception:
        print("WARNING: Province modal did not open.")
        return False


def select_city(page, city):
    """
    Select exact city from CellphoneS province popup.
    """

    if not open_province_modal(page):
        return False

    print(f"Searching province: {city}")

    search_input = page.locator(
        "#inputSearchProvince input"
    )

    try:
        search_input.fill(city)
        page.wait_for_timeout(300)
    except Exception as e:
        print(
            f"WARNING: Could not search province "
            f"{city}: {e}"
        )
        return False

    city_elements = page.locator(
        "#change-province li a"
    ).filter(
        has_text=city
    )

    count = city_elements.count()

    print(
        f"{city} elements in modal: {count}"
    )

    if count == 0:
        print(
            f"WARNING: Province not found: {city}"
        )
        return False

    # Click the exact matching city
    clicked = False

    for i in range(count):

        element = city_elements.nth(i)

        try:
            text = element.inner_text().strip()

            if text == city:
                element.click()
                clicked = True
                break

        except Exception:
            continue

    # Fallback: click first matching element
    if not clicked:

        try:
            city_elements.first.click()
            clicked = True
        except Exception:
            pass

    if not clicked:
        print(
            f"WARNING: Could not click {city}"
        )
        return False

    print(f"{city} clicked.")

    return True


def get_stock_count(page, city):
    """
    Read stock information after selecting a city.

    Returns:
        integer stock count
        0 when out of stock
        None when stock cannot be determined
    """

    print(
        f"Checking stock for {city}..."
    )

    # CellphoneS needs a little time to update
    # the stock content after province selection.
    for _ in range(20):

        try:
            text = page.locator(
                "body"
            ).inner_text()

            # -------------------------------------------------
            # IN STOCK
            # Example:
            # Có 1 cửa hàng có sản phẩm
            # -------------------------------------------------

            match = re.search(
                r"Có\s+(\d+)\s+cửa hàng có sản phẩm",
                text,
                re.IGNORECASE
            )

            if match:

                stock = int(
                    match.group(1)
                )

                print(
                    f"Stock text found: "
                    f"Có {stock} cửa hàng có sản phẩm"
                )

                return stock

            # -------------------------------------------------
            # OUT OF STOCK
            # -------------------------------------------------

            text_lower = text.lower()

            if (
                "tạm hết hàng" in text_lower
                or "tạm hết hàng tại" in text_lower
            ):

                print(
                    f"{city}: TẠM HẾT HÀNG"
                )

                return 0

        except Exception:
            pass

        page.wait_for_timeout(500)

    print(
        f"WARNING: Could not determine stock "
        f"for {city}"
    )

    return None


def scrape_stock(page):
    """
    Scrape stock for all configured cities.
    """

    stock_records = []

    for city in CITIES:

        print("")
        print(
            "================================"
        )
        print(
            f"TESTING {city}"
        )
        print(
            "================================"
        )

        success = select_city(
            page,
            city
        )

        if not success:

            stock_records.append({
                "city": city,
                "stock": None,
                "stock_status": "UNKNOWN",
            })

            continue

        stock = get_stock_count(
            page,
            city
        )

        if stock is None:

            stock_status = "UNKNOWN"

        elif stock > 0:

            stock_status = "IN_STOCK"

        else:

            stock_status = "OUT_OF_STOCK"

        stock_records.append({
            "city": city,
            "stock": stock,
            "stock_status": stock_status,
        })

    return stock_records


# =========================================================
# PRODUCT SCRAPER
# =========================================================

def scrape_product(page, product):

    url = product["url"]

    try:

        print(
            f"Scraping CellphoneS: "
            f"{product['product_id']}"
        )

        # -------------------------------------------------
        # OPEN PRODUCT
        # -------------------------------------------------

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        page.wait_for_timeout(2000)

        text = page.locator(
            "body"
        ).inner_text()

        # -------------------------------------------------
        # PRICE
        # -------------------------------------------------

        current_price, original_price = extract_prices(
            text
        )

        if current_price is None:

            print(
                f"WARNING: No price found "
                f"for {product['product_id']}"
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
                2
            )

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

        # -------------------------------------------------
        # STOCK
        # -------------------------------------------------

        stock_records = scrape_stock(
            page
        )

        # -------------------------------------------------
        # OVERALL STOCK STATUS
        # -------------------------------------------------

        known_records = [
            record
            for record in stock_records
            if record["stock_status"] != "UNKNOWN"
        ]

        if not known_records:

            overall_stock_status = "UNKNOWN"

        elif any(
            record["stock_status"] == "IN_STOCK"
            for record in known_records
        ):

            overall_stock_status = "IN_STOCK"

        else:

            overall_stock_status = "OUT_OF_STOCK"

        # -------------------------------------------------
        # RESULT
        # -------------------------------------------------

        return {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),

            "retailer_id": RETAILER_ID,

            "brand": product["brand"],

            "product_id": product["product_id"],

            "product_name": product["product_name"],

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

            "stock_status": overall_stock_status,

            "stock_records": stock_records,

            "promotion": "",

            "url": url,
        }

    except Exception as e:

        print(
            f"CellphoneS error "
            f"{product['product_id']}: {e}"
        )

        return None


# =========================================================
# MAIN SCRAPER
# =========================================================

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

            result = scrape_product(
                page,
                product
            )

            if result:

                results.append(
                    result
                )

            time.sleep(1)

        browser.close()

    return results
