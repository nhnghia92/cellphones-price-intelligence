from playwright.sync_api import sync_playwright


URL = "https://hoanghamobile.com/cu-sac/cu-sac-nhanh-belkin-45w-1-cong-usb-c-pd-3-0-pps-gann"


with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True
    )

    page = browser.new_page(
        viewport={
            "width": 1440,
            "height": 900,
        }
    )

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=30000,
    )

    page.wait_for_timeout(3000)

    print("\n========== STORE KEYWORDS ==========")

    elements = page.locator(
        "button, a, input, div, span"
    )

    keywords = [
        "cửa hàng",
        "khu vực",
        "hồ chí minh",
        "tất cả khu vực",
        "đang có sẵn hàng",
        "tạm hết",
    ]

    seen = set()

    for i in range(elements.count()):

        element = elements.nth(i)

        try:

            if not element.is_visible():
                continue

            text = element.inner_text(
                timeout=300
            ).strip()

            if not text:
                continue

            text = " ".join(
                text.split()
            )

            lower = text.lower()

            if not any(
                keyword in lower
                for keyword in keywords
            ):
                continue

            if text in seen:
                continue

            seen.add(text)

            print("\nTEXT:")
            print(text)

            print("TAG:")
            print(
                element.evaluate(
                    "(el) => el.tagName"
                )
            )

            print("HTML:")
            print(
                element.evaluate(
                    "(el) => el.outerHTML"
                )[:2000]
            )

        except Exception:
            continue

    browser.close()
