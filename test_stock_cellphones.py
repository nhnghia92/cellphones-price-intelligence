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
    "Đà Nẵng",
    "Cần Thơ",
]


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def print_relevant_text(page):
    keywords = [
        "cửa hàng",
        "tồn kho",
        "còn hàng",
        "hết hàng",
        "Hồ Chí Minh",
        "Hà Nội",
        "Đà Nẵng",
        "Cần Thơ",
    ]

    text = page.locator("body").inner_text()

    for line in text.splitlines():
        line = clean(line)

        if not line:
            continue

        if any(
            keyword.lower() in line.lower()
            for keyword in keywords
        ):
            print(line)


def open_store_section(page):
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
                exact=False
            )

            if locator.count() > 0:
                locator.first.click(timeout=5000)
                page.wait_for_timeout(1500)

                print("Đã mở phần cửa hàng.")
                return True

        except Exception:
            pass

    print("Không tìm thấy phần cửa hàng.")
    return False


def select_city(page, city):
    print("")
    print(f"Đang chọn: {city}")

    try:
        # Tìm tên thành phố trong popup
        locator = page.get_by_text(
            city,
            exact=True
        )

        if locator.count() == 0:
            locator = page.get_by_text(
                city,
                exact=False
            )

        if locator.count() == 0:
            print(f"Không tìm thấy {city}")
            return False

        locator.first.click(timeout=5000)

        # CellphoneS có thể cập nhật nội dung
        # nhưng URL không đổi
        page.wait_for_timeout(3000)

        print(f"Đã chọn: {city}")

        return True

    except Exception as error:
        print(f"Lỗi khi chọn {city}: {error}")
        return False


def main():

    print("=" * 50)
    print("CELLPHONES CITY STOCK TEST")
    print("=" * 50)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            }
        )

        print("")
        print("Opening product...")

        page.goto(
            PRODUCT_URL,
            wait_until="domcontentloaded",
            timeout=30000
        )

        page.wait_for_timeout(5000)

        print("Page loaded.")

        # Mở phần cửa hàng
        if not open_store_section(page):
            browser.close()
            return

        # Test từng tỉnh
        for city in CITIES:

            print("")
            print("-" * 50)

            if select_city(page, city):
                print_relevant_text(page)
            else:
                print(f"FAILED: {city}")

        browser.close()

    print("")
    print("=" * 50)
    print("TEST COMPLETED")
    print("=" * 50)


if __name__ == "__main__":
    main()
