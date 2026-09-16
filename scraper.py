import os
import re
import json
from datetime import datetime, timezone
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

URL = os.getenv(
    'CELLPHONES_URL',
    'https://cellphones.com.vn/phu-kien/sac-dien-thoai/sac.html?order=filter_price&dir=asc&sac_cong_suat=45w-duoi-67w'
)


def money_values(s):
    """
    Extract các giá tiền thực tế trong text.
    Không lấy phần trăm và hạn chế các số tiền nằm trong câu khuyến mãi.
    """
    if not s:
        return []

    values = []

    # Tìm số có dạng 590.000đ / 890.000đ / 1.290.000đ
    for m in re.finditer(r'(\d{1,3}(?:[.,]\d{3})+)\s*(?:đ|₫)', s, re.I):
        raw = m.group(1)

        try:
            value = int(raw.replace('.', '').replace(',', ''))

            if 10000 <= value <= 50000000:
                # Lấy một đoạn text trước giá để xem có phải khuyến mãi không
                before = s[max(0, m.start() - 50):m.start()].lower()

                promo_keywords = [
                    'giảm đến',
                    'giảm ngay',
                    'giảm thêm',
                    'tiết kiệm',
                    'voucher',
                    'coupon',
                    'smember',
                    'mã giảm',
                    'ưu đãi'
                ]

                is_promo = any(x in before for x in promo_keywords)

                values.append({
                    'value': value,
                    'promo': is_promo,
                    'position': m.start()
                })

        except Exception:
            pass

    return values


def extract_prices(text):
    """
    Trả về:
        current_price
        original_price

    Ví dụ:
        590.000đ 890.000đ Giảm 34% Smember giảm đến 30.000đ

    => current_price = 590000
       original_price = 890000
    """

    prices = money_values(text)

    if not prices:
        return None, None

    # Loại bỏ các khoản giảm giá / voucher / Smember...
    normal_prices = [x for x in prices if not x['promo']]

    if not normal_prices:
        normal_prices = prices

    # Thông thường giá bán hiện tại xuất hiện trước giá gốc
    current_price = normal_prices[0]['value']

    original_price = ''

    if len(normal_prices) >= 2:
        second = normal_prices[1]['value']

        # Giá gốc thường phải >= giá bán hiện tại
        if second >= current_price:
            original_price = second

    return current_price, original_price


def pid(url):
    return url.split('?')[0].rstrip('/').split('/')[-1].lower()


def clean(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def scrape():
    now = datetime.now(timezone.utc).isoformat()
    out = {}

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)

        page = b.new_page(
            locale='vi-VN',
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36'
        )

        page.goto(
            URL,
            wait_until='domcontentloaded',
            timeout=90000
        )

        page.wait_for_timeout(5000)

        for _ in range(6):
            page.mouse.wheel(0, 1800)
            page.wait_for_timeout(1000)

        for a in page.locator('a[href*=".html"]').all():

            try:
                href = a.get_attribute('href') or ''
                text = clean(a.inner_text(timeout=1000))
            except Exception:
                continue

            u = urljoin(URL, href)

            if 'cellphones.com.vn' not in u or not text:
                continue

            low = text.lower()

            if not any(
                x in low
                for x in [
                    'belkin',
                    'esr',
                    'anker',
                    'ugreen',
                    'baseus',
                    'sạc',
                    'charger',
                    'củ sạc'
                ]
            ):
                continue

            # Lấy text của product card
            card_text = text

            try:
                parent_text = a.locator(
                    'xpath=ancestor::*[self::div or self::li][1]'
                ).inner_text(timeout=1000)

                parent_text = clean(parent_text)

                # Nếu parent có nhiều thông tin hơn thì dùng parent
                if len(parent_text) > len(card_text):
                    card_text = parent_text

            except Exception:
                pass

            current_price, original_price = extract_prices(card_text)

            if not current_price:
                continue

            k = pid(u)

            brand = next(
                (
                    x.title()
                    for x in [
                        'belkin',
                        'esr',
                        'anker',
                        'ugreen',
                        'baseus',
                        'apple',
                        'samsung',
                        'xiaomi'
                    ]
                    if x in low
                ),
                ''
            )

            out[k] = {
                'product_id': k,
                'brand': brand,
                'product_name': text.split('\n')[0][:250],
                'category': 'Charger',
                'wattage': '',
                'current_price': current_price,
                'original_price': original_price,
                'stock_status': '',
                'url': u,
                'scraped_at': now
            }

        b.close()

    return list(out.values())


if __name__ == '__main__':
    print(
        json.dumps(
            scrape(),
            ensure_ascii=False
        )
    )
