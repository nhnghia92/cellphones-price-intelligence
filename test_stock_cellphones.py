import re

from playwright.sync_api import sync_playwright


PRODUCT_URL = (
    "https://cellphones.com.vn/"
    "cu-sac-nhanh-belkin-20w-1-cong-usb-c-pd-pps-"
    "cubic-wall-charger-cu.html"
)

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


def is_modal_open(page):
    try:
        return page.locator(
            "#change-province"
        ).first.is_visible(timeout=500)

    except Exception:
        return False


def open_province_modal(page):
    if is_modal_open(page):
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
            f"Opening province modal... "
            f"attempt {attempt + 1}/5"
        )

        for selector in selectors:
            try:
                locator = page.locator(
                    selector
                )

                count = locator.count()

                for i in range(min(count, 10)):
                    element = locator.nth(i)

                    try:
                        if not element.is_visible(
                            timeout=500
                        ):
                            continue

                        element.evaluate(
                            "(el) => el.click()"
                        )

                        page.wait_for_timeout(500)

                        if is_modal_open(page):
                            print(
                                "Province modal opened."
                            )
                            return True

                    except Exception:
                        continue

            except Exception:
                continue

        page.wait_for_timeout(1000)

    print(
        "WARNING: Could not open province modal."
    )

    return False


def select_city(page, city):
    if not open_province_modal(page):
        return False

    print(
        f"Searching province: {city}"
    )

    try:
        search = page.locator(
            "#inputSearchProvince input"
        ).first

        search.wait_for(
            state="visible",
            timeout=3000,
        )

        search.fill("")
        search.fill(city)

        page.wait_for_timeout(500)

    except Exception as error:
        print(
            f"Search input error: {error}"
        )

    city_locator = page.locator(
        "#change-province li a"
    ).filter(
        has_text=city
    )

    try:
        count = city_locator.count()

        print(
            f"{city} elements in modal: "
            f"{count}"
        )

        if count == 0:
            print(
                f"Province not found: {city}"
            )
            return False

        city_link = city_locator.first

        city_link.wait_for(
            state="visible",
            timeout=3000,
        )

        city_link.evaluate(
            "(el) => el.click()"
        )

        print(
            f"{city} clicked."
        )

        page.wait_for_timeout(500)

        return True

    except Exception as error:
        print(
            f"Could not click {city}: {error}"
        )

        return False


def debug_stock_dom(page, city):
    print("")
    print(
        "========================================"
    )
    print(
        f"DEBUG STOCK DOM: {city}"
    )
    print(
        "========================================"
    )

    try:
        body_text = clean(
            page.locator(
                "body"
            ).inner_text(
                timeout=3000
            )
        )

        keywords = [
            "cửa hàng",
            "sản phẩm",
            "hết hàng",
            "mua hàng",
            "stock",
            "inventory",
            "chi nhánh",
            "tại cửa hàng",
        ]

        lines = body_text.split(
            "\n"
        )

        print(
            "RELEVANT TEXT:"
        )

        found = False

        for line in lines:
            line = clean(line)

            if not line:
                continue

            lower = line.lower()

            if any(
                keyword in lower
                for keyword in keywords
            ):
                print(
                    line[:500]
                )
                found = True

        if not found:
            print(
                "No relevant stock text found."
            )

    except Exception as error:
        print(
            f"Could not read body: {error}"
        )

    try:
        html = page.locator(
            "body"
        ).inner_html(
            timeout=5000
        )

        patterns = [
            r".{0,500}cửa hàng.{0,1000}",
            r".{0,500}sản phẩm.{0,1000}",
            r".{0,500}hết hàng.{0,1000}",
        ]

        print("")
        print(
            "HTML MATCHES:"
        )

        html_found = False

        for pattern in patterns:
            matches = re.findall(
                pattern,
                html,
                re.IGNORECASE | re.DOTALL,
            )

            for match in matches[:5]:
                text = clean(match)

                print(
                    text[:2000]
                )

                html_found = True

        if not html_found:
            print(
                "No HTML matches found."
            )

    except Exception as error:
        print(
            f"Could not read HTML: {error}"
        )

    try:
        stock_candidates = page.locator(
            "[class*='stock'], "
            "[class*='Stock'], "
            "[class*='inventory'], "
            "[class*='Inventory']"
        )

        count = stock_candidates.count()

        print("")
        print(
            f"STOCK CLASS CANDIDATES: {count}"
        )

        for i in range(
            min(count, 30)
        ):
            try:
                element = (
                    stock_candidates.nth(i)
                )

                text = clean(
                    element.inner_text(
                        timeout=1000
                    )
                )

                classes = (
                    element.get_attribute(
                        "class"
                    )
                    or ""
                )

                if text:
                    print(
                        f"[{i}] "
                        f"class={classes} "
                        f"text={text[:500]}"
                    )

            except Exception:
                continue

    except Exception as error:
        print(
            f"Could not inspect "
            f"stock classes: {error}"
        )

    print(
        "========================================"
    )


def get_stock_count(page, city):
    print(
        f"Checking stock for {city}..."
    )

    stock_pattern = re.compile(
        r"Có\s+(\d+)\s+cửa hàng\s+có sản phẩm",
        re.IGNORECASE,
    )

    out_pattern = re.compile(
        r"TẠM HẾT HÀNG|tạm hết hàng tại|SẮP VỀ HÀNG",
        re.IGNORECASE,
    )

    attempts = STOCK_TIMEOUT // 300

    for _ in range(attempts):
        try:
            stock_locator = page.get_by_text(
                stock_pattern
            )

            count = stock_locator.count()

            if count > 0:
                for i in range(count):
                    try:
                        element = stock_locator.nth(i)

                        if not element.is_visible(
                            timeout=300
                        ):
                            continue

                        text = clean(
                            element.inner_text()
                        )

                        match = stock_pattern.search(
                            text
                        )

                        if match:
                            stock = int(
                                match.group(1)
                            )

                            print(
                                f"Stock text found: "
                                f"{text}"
                            )

                            print(
                                f"{city}: "
                                f"{stock} cửa hàng "
                                f"có sản phẩm"
                            )

                            return stock

                    except Exception:
                        continue

        except Exception:
            pass

        try:
            body_text = clean(
                page.locator(
                    "body"
                ).inner_text(
                    timeout=1500
                )
            )

            if out_pattern.search(
                body_text
            ):
                print(
                    f"{city}: TẠM HẾT HÀNG"
                )

                return 0

        except Exception:
            pass

        page.wait_for_timeout(300)

    print(
        f"{city}: STOCK NOT FOUND "
        f"after {STOCK_TIMEOUT / 1000:.0f} seconds"
    )

    debug_stock_dom(
        page,
        city,
    )

    return None


def test_city(page, city):
    print("")
    print(
        "========================================"
    )
    print(
        f"TESTING {city}"
    )
    print(
        "========================================"
    )

    selected = select_city(
        page,
        city,
    )

    if not selected:
        print(
            f"{city}: FAILED TO SELECT"
        )
        return None

    return get_stock_count(
        page,
        city,
    )


def main():
    print("")
    print(
        "========================================"
    )
    print(
        "CELLPHONES CITY STOCK TEST"
    )
    print(
        "========================================"
    )

    results = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            }
        )

        page.set_default_timeout(5000)

        print(
            "Opening product..."
        )

        page.goto(
            PRODUCT_URL,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        page.locator(
            "body"
        ).wait_for(
            state="visible",
            timeout=10000,
        )

        print(
            "Product loaded."
        )

        for city in CITIES:
            results[city] = test_city(
                page,
                city,
            )

        browser.close()

    print("")
    print(
        "========================================"
    )
    print(
        "FINAL RESULT"
    )
    print(
        "========================================"
    )

    for city in CITIES:
        stock = results.get(city)

        if stock is None:
            print(
                f"{city}: NOT FOUND"
            )
        else:
            print(
                f"{city}: {stock}"
            )

    print(
        "========================================"
    )
    print(
        "TEST COMPLETED"
    )
    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
