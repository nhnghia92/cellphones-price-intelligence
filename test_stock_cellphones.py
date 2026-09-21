
import re

from playwright.sync_api import (
    sync_playwright,
)


# ============================================================
# CONFIG
# ============================================================

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


# ============================================================
# HELPERS
# ============================================================

def clean(text):
    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ============================================================
# PROVINCE MODAL
# ============================================================

def is_province_modal_open(page):
    try:
        modal = page.locator(
            "#change-province"
        ).first

        return modal.is_visible(
            timeout=500
        )

    except Exception:
        return False


def open_province_modal(page):
    """
    Mở popup chọn tỉnh/thành phố.

    Không scan toàn bộ DOM.
    Chỉ thử các selector đã biết.
    """

    if is_province_modal_open(page):

        print(
            "Province modal already open."
        )

        return True

    print(
        "Opening province modal..."
    )

    selectors = [
        "text=Hồ Chí Minh",
        "text=Hà Nội",
        "text=Cần Thơ",
        "text=Đà Nẵng",
        "text=Chọn khu vực",
        "text=Chọn tỉnh",
    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            ).first

            locator.wait_for(
                state="visible",
                timeout=1200,
            )

            locator.click(
                timeout=2500
            )

            # Chờ popup thật sự mở
            page.locator(
                "#change-province"
            ).wait_for(
                state="visible",
                timeout=2500,
            )

            print(
                "Province modal opened."
            )

            return True

        except Exception:
            continue

    print(
        "WARNING: Could not open "
        "province modal."
    )

    return False


# ============================================================
# SELECT CITY
# ============================================================

def select_city(page, city):
    """
    Chọn một tỉnh/thành phố.
    """

    if not open_province_modal(page):
        return False

    print(
        f"Searching province: {city}"
    )

    # --------------------------------------------------------
    # Search box
    # --------------------------------------------------------

    try:

        search = page.locator(
            "#change-province "
            "#inputSearchProvince input"
        ).first

        search.wait_for(
            state="visible",
            timeout=2000,
        )

        search.fill("")

        search.fill(city)

        page.wait_for_timeout(300)

    except Exception as error:

        print(
            f"Search input error: {error}"
        )

    # --------------------------------------------------------
    # City
    # --------------------------------------------------------

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
                f"Province not found: "
                f"{city}"
            )

            return False

        city_link = city_locator.first

        city_link.wait_for(
            state="visible",
            timeout=2000,
        )

        city_link.click(
            timeout=5000
        )

        print(
            f"{city} clicked."
        )

        return True

    except Exception as error:

        print(
            f"Could not click "
            f"{city}: {error}"
        )

        return False


# ============================================================
# STOCK PARSER
# ============================================================

def parse_stock_text(text):
    """
    Trả về:

        (stock, status)

    Ví dụ:

        Có 1 cửa hàng có sản phẩm
        -> (1, "IN_STOCK")

        Có 18 cửa hàng có sản phẩm
        -> (18, "IN_STOCK")

        TẠM HẾT HÀNG
        -> (0, "OUT_OF_STOCK")

        Không tìm thấy
        -> (None, "UNKNOWN")
    """

    if not text:
        return (
            None,
            "UNKNOWN",
        )

    # --------------------------------------------------------
    # IN STOCK
    # --------------------------------------------------------

    stock_pattern = re.compile(
        r"Có\s+(\d+)\s+cửa hàng\s+có sản phẩm",
        re.IGNORECASE,
    )

    match = stock_pattern.search(
        text
    )

    if match:

        stock = int(
            match.group(1)
        )

        if stock > 0:

            return (
                stock,
                "IN_STOCK",
            )

        return (
            0,
            "OUT_OF_STOCK",
        )

    # --------------------------------------------------------
    # OUT OF STOCK
    # --------------------------------------------------------

    out_pattern = re.compile(
        r"TẠM HẾT HÀNG|"
        r"tạm hết hàng tại",
        re.IGNORECASE,
    )

    if out_pattern.search(text):

        return (
            0,
            "OUT_OF_STOCK",
        )

    return (
        None,
        "UNKNOWN",
    )


# ============================================================
# GET STOCK
# ============================================================

def get_stock_count(page, city):
    """
    Chờ CellphoneS cập nhật stock.

    Không dùng wait cố định.

    Kiểm tra mỗi 300ms trong tối đa
    15 giây.

    UNKNOWN không được coi là OUT_OF_STOCK.
    """

    print(
        f"Checking stock for {city}..."
    )

    # --------------------------------------------------------
    # IMPORTANT
    #
    # Sau khi click city, CellphoneS có thể
    # cập nhật DOM bất đồng bộ.
    #
    # Vì vậy không đọc một lần rồi kết luận.
    # --------------------------------------------------------

    for _ in range(
        STOCK_TIMEOUT // 300
    ):

        # ====================================================
        # 1. Tìm trực tiếp text stock
        # ====================================================

        try:

            stock_pattern = re.compile(
                r"Có\s+(\d+)\s+"
                r"cửa hàng\s+có sản phẩm",
                re.IGNORECASE,
            )

            stock_locator = page.get_by_text(
                stock_pattern
            )

            count = stock_locator.count()

            if count > 0:

                for i in range(count):

                    try:

                        element = (
                            stock_locator.nth(i)
                        )

                        if not element.is_visible(
                            timeout=300
                        ):
                            continue

                        text = clean(
                            element.inner_text()
                        )

                        match = (
                            stock_pattern.search(
                                text
                            )
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

        # ====================================================
        # 2. Tìm trạng thái hết hàng
        # ====================================================

        try:

            body_text = clean(
                page.locator(
                    "body"
                ).inner_text(
                    timeout=1500
                )
            )

            lower_text = body_text.lower()

            if (
                "tạm hết hàng" in lower_text
                or
                "tạm hết hàng tại"
                in lower_text
            ):

                print(
                    f"{city}: "
                    "TẠM HẾT HÀNG"
                )

                return 0

        except Exception:
            pass

        # ====================================================
        # 3. Chờ 300ms rồi kiểm tra lại
        # ====================================================

        page.wait_for_timeout(
            300
        )

    # ========================================================
    # UNKNOWN
    # ========================================================

    print(
        f"{city}: STOCK NOT FOUND "
        f"after {STOCK_TIMEOUT / 1000:.0f} seconds"
    )

    return None


# ============================================================
# TEST ONE CITY
# ============================================================

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

    stock = get_stock_count(
        page,
        city,
    )

    return stock


# ============================================================
# MAIN
# ============================================================

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

        # ----------------------------------------------------
        # Browser
        # ----------------------------------------------------

        browser = playwright.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            }
        )

        page.set_default_timeout(
            5000
        )

        print(
            "Opening product..."
        )

        # ----------------------------------------------------
        # Open product
        # ----------------------------------------------------

        page.goto(
            PRODUCT_URL,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        # Chỉ chờ body render.
        # Không hard-code 5 giây.
        try:

            page.locator(
                "body"
            ).wait_for(
                state="visible",
                timeout=10000,
            )

        except Exception:
            pass

        print(
            "Product loaded."
        )

        # ----------------------------------------------------
        # Test all cities
        # ----------------------------------------------------

        for city in CITIES:

            stock = test_city(
                page,
                city,
            )

            results[city] = stock

        browser.close()

    # ========================================================
    # FINAL RESULT
    # ========================================================

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

        stock = results.get(
            city
        )

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


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

