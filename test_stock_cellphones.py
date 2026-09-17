
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


def clean(text):
    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def inspect_page(page):
    print("")
    print("==============================")
    print("PAGE INSPECTION")
    print("==============================")

    text = page.locator("body").inner_text()

    keywords = [
        "cửa hàng",
        "tồn kho",
        "còn hàng",
        "chọn cửa hàng",
        "hồ chí minh",
        "hà nội",
        "đà nẵng",
        "cần thơ",
    ]

    for line in text.splitlines():
        line = clean(line)

        if not line:
            continue

        lower = line.lower()

        for keyword in keywords:
            if keyword in lower:
                print(line)
                break


def find_stock_button(page):
    print("")
    print("==============================")
    print("SEARCH STOCK SECTION")
    print("==============================")

    keywords = [
        "xem cửa hàng",
        "xem cửa hàng có hàng",
        "cửa hàng có hàng",
        "tìm cửa hàng",
        "chọn cửa hàng",
    ]

    for keyword in keywords:
        try:
            locator = page.get_by_text(
                keyword,
                exact=False,
            )

            count = locator.count()

            if count > 0:
                print(
                    f"FOUND: {keyword} "
                    f"({count} elements)"
                )

                return locator.first

        except Exception as error:
            print(
                f"Search error for "
                f"{keyword}: {error}"
            )

    print("Stock section not found.")

    return None


def inspect_elements(page):
    print("")
    print("==============================")
    print("POSSIBLE STORE ELEMENTS")
    print("==============================")

    selectors = [
        '[class*="store"]',
        '[class*="Store"]',
        '[class*="shop"]',
        '[class*="Shop"]',
        '[class*="branch"]',
        '[class*="Branch"]',
    ]

    for selector in selectors:
        try:
            count = page.locator(
                selector
            ).count()

            if count > 0:
                print(
                    f"{selector}: {count}"
                )

        except Exception:
            pass


def test_cities(page):
    print("")
    print("==============================")
    print("CITY TEST")
    print("==============================")

    for city_code, names in CITIES.items():

        print("")
        print(
            f"Testing {city_code}"
        )

        found = False

        for name in names:
            try:
                locator = page.get_by_text(
                    name,
                    exact=False,
                )

                count = locator.count()

                if count > 0:
                    print(
                        f"FOUND: {name} "
                        f"({count} elements)"
                    )

                    found = True
                    break

            except Exception as error:
                print(
                    f"Error: {error}"
                )

        if not found:
            print(
                f"NOT FOUND: {city_code}"
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

        print("")
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

        stock_button = find_stock_button(
            page
        )

        if stock_button is not None:
            print("")
            print(
                "Clicking stock section..."
            )

            try:
                stock_button.click(
                    timeout=5000
                )

                page.wait_for_timeout(
                    2000
                )

                print(
                    "Stock section clicked."
                )

            except Exception as error:
                print(
                    "Click failed:"
                )
                print(error)

        else:
            print("")
            print(
                "No stock button found."
            )

        inspect_page(page)

        inspect_elements(page)

        test_cities(page)

        print("")
        print(
            "Waiting for final rendering..."
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

