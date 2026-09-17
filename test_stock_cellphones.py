```python
import re
import time

from playwright.sync_api import sync_playwright


PRODUCT_URL = (
    "https://cellphones.com.vn/"
    "cu-sac-nhanh-belkin-20w-1-cong-usb-c-pd-pps-"
    "cubic-wall-charger-cu.html"
)


CITIES = {
    "HCM": [
        "Hồ Chí Minh",
        "TP. Hồ Chí Minh",
        "TP Hồ Chí Minh",
        "HCM",
    ],
    "HNI": [
        "Hà Nội",
        "HANOI",
    ],
    "CTO": [
        "Cần Thơ",
        "CAN THO",
    ],
    "DAN": [
        "Đà Nẵng",
        "DA NANG",
    ],
}


def clean_text(text):
    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def find_stock_section(page):
    """
    Try to locate the product stock/store area.
    """

    keywords = [
        "xem cửa hàng",
        "xem cửa hàng có hàng",
        "cửa hàng có hàng",
        "tìm cửa hàng",
        "chọn cửa hàng",
        "cửa hàng",
    ]

    for keyword in keywords:

        locator = page.get_by_text(
            keyword,
            exact=False,
        )

        count = locator.count()

        if count > 0:

            print(
                f"FOUND stock keyword: "
                f"{keyword}"
            )

            return locator.first

    return None


def inspect_page(page):
    """
    Print useful information about
    possible stock/store elements.
    """

    print("")
    print("==============================")
    print("PAGE INSPECTION")
    print("==============================")

    body_text = page.locator(
        "body"
    ).inner_text()

    lines = [
        clean_text(line)
        for line in body_text.splitlines()
    ]

    lines = [
        line
        for line in lines
        if line
    ]

    keywords = [
        "cửa hàng",
        "tồn kho",
        "còn hàng",
        "chọn",
        "hồ chí minh",
        "hà nội",
        "đà nẵng",
        "cần thơ",
    ]

    for line in lines:

        line_lower = line.lower()

        if any(
            keyword in line_lower
            for keyword in keywords
        ):

            print(
                f"  {line}"
            )


def count_visible_store_rows(page):
    """
    Heuristic store counting.

    This is intentionally only a test.
    We will replace it with the exact DOM/API
    logic after seeing the real page structure.
    """

    possible_selectors = [
        '[class*="store"]',
        '[class*="Store"]',
        '[class*="shop"]',
        '[class*="Shop"]',
        '[class*="branch"]',
        '[class*="Branch"]',
    ]

    candidates = []

    for selector in possible_selectors:

        try:

            locator = page.locator(
                selector
            )

            count = locator.count()

            if count > 0:

                candidates.append(
                    (
                        selector,
                        count,
                    )
                )

        except Exception:
            pass

    print("")
    print(
        "Possible store elements:"
    )

    for selector, count in candidates:

        print(
            f"  {selector}: {count}"
        )


def main():

    print("")
    print(
        "========================================"
    )
    print(
        "CELLPHONES STOCK TEST"
    )
    print(
        "========================================"
    )
    print("")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
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

        print(
            "Opening product..."
        )

        page.goto(
            PRODUCT_URL,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        page.wait_for_timeout(
            5000
        )

        print(
            "Page loaded."
        )

        inspect_page(page)

        stock_section = (
            find_stock_section(page)
        )

        if stock_section:

            print("")
            print(
                "Clicking stock/store section..."
            )

            try:

                stock_section.click(
                    timeout=5000
                )

                page.wait_for_timeout(
                    2000
                )

                print(
                    "Stock section clicked."
                )

            except Exception as e:

                print(
                    "Could not click stock "
                    f"section: {e}"
                )

        else:

            print("")
            print(
                "WARNING: Could not find "
                "stock/store section."
            )

        inspect_page(page)

        count_visible_store_rows(
            page
        )

        print("")
        print(
            "========================================"
        )
        print(
            "CITY TEST"
        )
        print(
            "========================================"
        )

        for city_code, city_names in (
            CITIES.items()
        ):

            print("")
            print(
                f"Testing city: {city_code}"
            )

            found = False

            for city_name in city_names:

                try:

                    locator = page.get_by_text(
                        city_name,
                        exact=False,
                    )

                    count = locator.count()

                    if count > 0:

                        print(
                            f"  FOUND: "
                            f"{city_name} "
                            f"({count} elements)"
                        )

                        found = True

                        break

                except Exception:
                    pass

            if not found:

                print(
                    f"  NOT FOUND: "
                    f"{city_code}"
                )

        print("")
        print(
            "Keeping browser open briefly "
            "for JS rendering..."
        )

        page.wait_for_timeout(
            3000
        )

        browser.close()

    print("")
    print(
        "========================================"
    )
    print(
        "STOCK TEST COMPLETED"
    )
    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
```
