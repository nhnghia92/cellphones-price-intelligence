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


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def open_province_modal(page):
    """Mở popup chọn tỉnh/thành."""

    modal = page.locator("#change-province")

    # Popup đã mở
    if modal.is_visible():
        print("Province modal already open.")
        return True

    print("Opening province modal...")

    # Tìm nút/element đang hiển thị tỉnh hiện tại
    selectors = [
        "text=Hồ Chí Minh",
        "text=Hà Nội",
        "text=Cần Thơ",
        "text=Đà Nẵng",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector)

            if locator.count() > 0:
                locator.first.click(timeout=5000)
                page.wait_for_timeout(500)

                if modal.is_visible():
                    print("Province modal opened.")
                    return True

        except Exception:
            pass

    print("Stock province selector not found.")

    return False


def select_city(page, city):
    """Tìm tỉnh bằng ô search rồi click kết quả."""

    print("")
    print("=" * 40)
    print(f"TESTING {city}")
    print("=" * 40)

    if not open_province_modal(page):
        return False

    # --------------------------------------------------
    # Ô tìm kiếm chính xác từ HTML
    # --------------------------------------------------

    search = page.locator(
        "#inputSearchProvince input"
    )

    if search.count() == 0:

        print("Province search input not found.")

        return False

    # --------------------------------------------------
    # Nhập tên tỉnh
    # --------------------------------------------------

    print(
        f"Searching province: {city}"
    )

    search.fill(city)

    page.wait_for_timeout(300)

    # --------------------------------------------------
    # Tìm kết quả trong popup
    # --------------------------------------------------

    city_locator = page.locator(
        "#change-province li a"
    ).filter(
        has_text=city
    )

    count = city_locator.count()

    print(
        f"{city} elements in modal: {count}"
    )

    if count == 0:

        print(
            f"{city}: NOT FOUND"
        )

        return False

    # --------------------------------------------------
    # Click tỉnh
    # --------------------------------------------------

    try:

        city_locator.first.click(
            timeout=5000
        )

        print(
            f"{city} clicked."
        )

    except Exception as error:

        print(
            f"Could not click {city}: {error}"
        )

        return False

    # --------------------------------------------------
    # Chờ CellphoneS cập nhật
    #
    # URL có thể KHÔNG thay đổi.
    # --------------------------------------------------

    page.wait_for_timeout(2000)

    return True


def get_page_text(page):

    try:
        return page.locator(
            "body"
        ).inner_text()

    except Exception:
        return ""


def inspect_stock(page, city):

    print("")
    print(
        f"Checking stock for {city}..."
    )

    text = get_page_text(page)

    keywords = [
        "còn hàng",
        "hết hàng",
        "tồn kho",
        "cửa hàng",
    ]

    lines = []

    for line in text.splitlines():

        line = clean(line)

        if not line:
            continue

        lower = line.lower()

        if any(
            keyword in lower
            for keyword in keywords
        ):
            lines.append(line)

    if lines:

        for line in lines[:30]:
            print(line)

    else:

        print(
            "No stock information found."
        )


def main():

    print("")
    print("=" * 40)
    print("CELLPHONES CITY STOCK TEST")
    print("=" * 40)

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
            timeout=30000,
        )

        page.wait_for_timeout(5000)

        print("Product loaded.")

        # --------------------------------------------------
        # TEST 4 TỈNH
        # --------------------------------------------------

        for city in CITIES:

            success = select_city(
                page,
                city
            )

            if success:

                inspect_stock(
                    page,
                    city
                )

            else:

                print(
                    f"{city}: FAILED"
                )

        browser.close()

    print("")
    print("=" * 40)
    print("TEST COMPLETED")
    print("=" * 40)


if __name__ == "__main__":
    main()
