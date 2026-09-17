
import re

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

    keywords = [
        "xem cửa hàng",
        "xem cửa hàng có hàng",
        "cửa hàng có hàng",
        "tìm cửa hàng",
        "chọn cửa hàng",
    ]

    for keyword in keywords:

        locator = page.get_by_text(
            keyword,
            exact=False,
        )

        if locator.count() > 0:

            print(
                f"FOUND stock keyword: {keyword}"
            )

            return locator.first

    return None


def inspect_page(page):

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

        if any(
            keyword in line.lower()
            for keyword in keywords
        ):

            print(
                f"  {line}"
            )


def count_possible_store_elements(page):

    selectors = [
        '[class*="store"]',
        '[class*="Store"]',
        '[class*="shop"]',
        '[class*="Shop"]',
        '[class*="branch"]',
        '[class*="Branch"]',
    ]

    print("")
    print(
        "Possible store elements:"
    )

    for selector in selectors:

        try:

            count = page.locator(
                selector
            ).count()

            if count > 0:

                print(
                    f"  {selector}: {count}"
                )

        except Exception:
            pass


def test_city_names(page):

    print("")
    print("==============================")
    print("CITY TEST")
    print("==============================")

    for city_code, city_names in CITIES.items():

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
                        f"  FOUND: {city_name} "
                        f"({count} elements)"
                    )

                    found = True
                    break

            except Exception:
                pass

        if not found:

            print(
                f"  NOT FOUND: {city_code}"
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
