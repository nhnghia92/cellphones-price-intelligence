import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


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
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def open_province_modal(page):
    """
    Mở popup chọn tỉnh/thành phố.
    """

    modal = page.locator("#change-province")

    # Nếu modal đã mở thì không cần mở lại
    if modal.count() > 0 and modal.first.is_visible():
        print("Province modal already open.")
        return True

    print("Opening province modal...")

    selectors = [
        "text=Hồ Chí Minh",
        "text=Hà Nội",
        "text=Cần Thơ",
        "text=Đà Nẵng",
    ]

    # Tìm nút hiện tại dùng để mở province selector
    for selector in selectors:
        try:
            locator = page.locator(selector)

            if locator.count() > 0:
                for i in range(min(locator.count(), 5)):
                    element = locator.nth(i)

                    if element.is_visible():
                        try:
                            element.click(timeout=3000)
                            page.wait_for_timeout(500)

                            if page.locator("#change-province").count() > 0:
                                print("Province modal opened.")
                                return True

                        except Exception:
                            pass

        except Exception:
            pass

    print("Could not open province modal.")
    return False


def select_city(page, city):
    """
    Chọn tỉnh/thành phố trong popup.
    """

    if not open_province_modal(page):
        return False

    print(f"Searching province: {city}")

    search = page.locator("#inputSearchProvince input")

    try:
        if search.count() > 0:
            search.fill("")
            search.fill(city)
            page.wait_for_timeout(500)
    except Exception as error:
        print(f"Search input error: {error}")

    city_locator = page.locator(
        "#change-province li a"
    ).filter(has_text=city)

    count = city_locator.count()

    print(f"{city} elements in modal: {count}")

    if count == 0:
        print(f"Province not found: {city}")
        return False

    try:
        city_locator.first.click(timeout=5000)
        print(f"{city} clicked.")

        # Cho CPS thời gian update stock
        page.wait_for_timeout(1500)

        return True

    except Exception as error:
        print(f"Could not click {city}: {error}")
        return False


def get_stock_count(page, city):
    """
    Đọc stock sau khi CPS đã cập nhật tỉnh.

    Ưu tiên tìm:
        Có X cửa hàng có sản phẩm

    Nếu không có và thấy:
        TẠM HẾT HÀNG
        hoặc
        tạm hết hàng tại ...

    thì trả về 0.
    """

    print(f"Checking stock for {city}...")

    # ---------------------------------------------------------
    # 1. Chờ tối đa 10 giây để CPS render stock
    # ---------------------------------------------------------

    stock_pattern = re.compile(
        r"Có\s+(\d+)\s+cửa hàng có sản phẩm",
        re.IGNORECASE
    )

    out_of_stock_pattern = re.compile(
        r"TẠM HẾT HÀNG|tạm hết hàng tại",
        re.IGNORECASE
    )

    for _ in range(20):

        try:
            # Tìm chính xác element chứa:
            # "Có X cửa hàng có sản phẩm"
            stock_locator = page.get_by_text(
                stock_pattern
            )

            if stock_locator.count() > 0:

                for i in range(stock_locator.count()):

                    try:
                        text = clean(
                            stock_locator.nth(i).inner_text()
                        )

                        print(f"Stock text found: {text}")

                        match = stock_pattern.search(text)

                        if match:
                            count = int(match.group(1))

                            print(
                                f"{city}: {count} cửa hàng có sản phẩm"
                            )

                            return count

                    except Exception:
                        pass

            # -------------------------------------------------
            # 2. Kiểm tra hết hàng
            # -------------------------------------------------

            body_text = clean(
                page.locator("body").inner_text()
            )

            if out_of_stock_pattern.search(body_text):

                print(f"{city}: TẠM HẾT HÀNG")

                return 0

        except Exception:
            pass

        page.wait_for_timeout(500)

    # ---------------------------------------------------------
    # 3. Không tìm được trạng thái
    # ---------------------------------------------------------

    print(f"{city}: STOCK NOT FOUND")

    return None


def test_city(page, city):
    """
    Chọn tỉnh → chờ CPS update → lấy stock.
    """

    print("")
    print("========================================")
    print(f"TESTING {city}")
    print("========================================")

    selected = select_city(page, city)

    if not selected:
        print(f"{city}: FAILED TO SELECT")

        return None

    stock = get_stock_count(page, city)

    return stock


def main():

    print("")
    print("========================================")
    print("CELLPHONES CITY STOCK TEST")
    print("========================================")

    results = {}

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000
            }
        )

        print("Opening product...")

        page.goto(
            PRODUCT_URL,
            wait_until="domcontentloaded",
            timeout=30000
        )

        page.wait_for_timeout(5000)

        print("Product loaded.")

        # -----------------------------------------------------
        # TEST TỪNG TỈNH
        # -----------------------------------------------------

        for city in CITIES:

            stock = test_city(
                page,
                city
            )

            results[city] = stock

        browser.close()

    # ---------------------------------------------------------
    # FINAL RESULT
    # ---------------------------------------------------------

    print("")
    print("========================================")
    print("FINAL RESULT")
    print("========================================")

    for city, stock in results.items():

        if stock is None:
            print(f"{city}: NOT FOUND")

        else:
            print(f"{city}: {stock}")

    print("========================================")
    print("TEST COMPLETED")
    print("========================================")


if __name__ == "__main__":
    main()
