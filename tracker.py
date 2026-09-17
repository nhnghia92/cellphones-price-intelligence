import os
import json
import time
from datetime import datetime, timezone, timedelta

import gspread
from google.oauth2.service_account import Credentials
from google import genai
from config_loader import load_products
from scrapers.cellphones import scrape


HEAD = {
    "PRODUCT_MASTER": [
        "product_id",
        "brand",
        "product_name",
        "model",
        "category",
        "subcategory",
        "wattage",
        "technology",
        "msrp",
        "active",
    ],

    "COMPETITOR_MASTER": [
        "competitor_id",
        "brand",
        "type",
        "active",
    ],

    "SKU_MAPPING": [
        "mapping_id",
        "belkin_product_id",
        "competitor_id",
        "competitor_product_id",
        "competitor_product_name",
        "match_type",
        "active",
    ],

    "RETAILER_MASTER": [
        "retailer_id",
        "retailer_name",
        "channel",
        "priority",
        "active",
    ],

    "PRICE_RAW": [
        "timestamp",
        "retailer_id",
        "brand",
        "product_id",
        "product_name",
        "price",
        "original_price",
        "discount_pct",
        "stock_status",
        "promotion",
        "url",
    ],

    "PRICE_DAILY": [
        "date",
        "product_id",
        "brand",
        "product_name",
        "price",
        "change_1d_pct",
        "change_7d_pct",
        "change_30d_pct",
        "min_30d",
        "avg_30d",
    ],

    "PRICE_EVENTS": [
        "event_time",
        "product_id",
        "brand",
        "product_name",
        "event",
        "change_pct",
        "severity",
        "details",
    ],

    "AI_INSIGHTS": [
        "event_time",
        "product_id",
        "brand",
        "product_name",
        "trend",
        "impact",
        "possible_cause",
        "recommended_action",
        "confidence",
        "raw_ai",
    ],

    "DASHBOARD": [
        "metric",
        "value",
    ],
}


def get_google_client():

    info = json.loads(
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    )

    credentials = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    return gspread.authorize(credentials)


def get_sheet(sh, name):

    try:
        sheet = sh.worksheet(name)

    except gspread.WorksheetNotFound:

        sheet = sh.add_worksheet(
            title=name,
            rows=2000,
            cols=20,
        )

        sheet.append_row(
            HEAD[name]
        )

    return sheet


def to_number(value):

    try:
        return float(
            str(value)
            .replace(",", "")
            .replace(".", "")
        )

    except Exception:
        return None


def percentage(current, previous):

    if current is None:
        return None

    if previous in (None, 0):
        return None

    return round(
        (current - previous)
        / previous
        * 100,
        2,
    )


def main(products):

    client = get_google_client()

    spreadsheet = client.open_by_key(
        os.environ["GOOGLE_SHEET_ID"]
    )

    PRICE_RAW = get_sheet(
        spreadsheet,
        "PRICE_RAW"
    )

    PRICE_DAILY = get_sheet(
        spreadsheet,
        "PRICE_DAILY"
    )

    PRICE_EVENTS = get_sheet(
        spreadsheet,
        "PRICE_EVENTS"
    )

    AI_INSIGHTS = get_sheet(
        spreadsheet,
        "AI_INSIGHTS"
    )

    DASHBOARD = get_sheet(
        spreadsheet,
        "DASHBOARD"
    )

    # ------------------------------------------------
    # SAVE RAW PRICE DATA
    # ------------------------------------------------

    rows = []

    for product in products:

        rows.append([
            product.get("timestamp", ""),
            product.get("retailer_id", ""),
            product.get("brand", ""),
            product.get("product_id", ""),
            product.get("product_name", ""),
            product.get("price", ""),
            product.get("original_price", ""),
            product.get("discount_pct", ""),
            product.get("stock_status", ""),
            product.get("promotion", ""),
            product.get("url", ""),
        ])

    if rows:

        PRICE_RAW.append_rows(
            rows,
            value_input_option="USER_ENTERED"
        )

    # ------------------------------------------------
    # BUILD DAILY DATA
    # ------------------------------------------------

    raw = PRICE_RAW.get_all_values()

    now = datetime.now(timezone.utc)

    grouped = {}

    for row in raw[1:]:

        if len(row) < 6:
            continue

        product_id = row[3]

        price = to_number(row[5])

        if not product_id or price is None:
            continue

        try:

            timestamp = datetime.fromisoformat(
                row[0].replace("Z", "+00:00")
            )

        except Exception:

            continue

        grouped.setdefault(
            product_id,
            []
        ).append(
            (timestamp, price)
        )

    daily_rows = []
    events = []

    for product_id, history in grouped.items():

        history.sort()

        current_price = history[-1][1]

        previous_price = (
            history[-2][1]
            if len(history) >= 2
            else None
        )

        def price_before(days):

            cutoff = (
                now
                - timedelta(days=days)
            )

            values = [
                price
                for timestamp, price
                in history
                if timestamp <= cutoff
            ]

            return (
                values[-1]
                if values
                else None
            )

        price_1d = price_before(1)
        price_7d = price_before(7)
        price_30d = price_before(30)

        change_1d = percentage(
            current_price,
            price_1d
        )

        change_7d = percentage(
            current_price,
            price_7d
        )

        change_30d = percentage(
            current_price,
            price_30d
        )

        recent_prices = [
            price
            for timestamp, price
            in history
            if timestamp >= now - timedelta(days=30)
        ]

        if not recent_prices:
            recent_prices = [
                current_price
            ]

        daily_rows.append([
            now.date().isoformat(),
            product_id,
            "",
            "",
            current_price,
            change_1d,
            change_7d,
            change_30d,
            min(recent_prices),
            round(
                sum(recent_prices)
                / len(recent_prices),
                0
            ),
        ])

       min_change_raw = os.getenv(
    "MIN_CHANGE_PCT",
    "5"
)

try:
    min_change = float(
        min_change_raw
    ) if min_change_raw.strip() else 5.0
except ValueError:
    min_change = 5.0
        if (
            change_1d is not None
            and abs(change_1d) >= min_change
        ):

            events.append([
                now.isoformat(),
                product_id,
                "",
                "",
                (
                    "PRICE_DROP"
                    if change_1d < 0
                    else "PRICE_INCREASE"
                ),
                change_1d,
                (
                    "HIGH"
                    if abs(change_1d) >= 10
                    else "MEDIUM"
                ),
                f"{previous_price:,.0f} -> "
                f"{current_price:,.0f}",
            ])

    if daily_rows:

        PRICE_DAILY.append_rows(
            daily_rows,
            value_input_option="USER_ENTERED"
        )

    if events:

        PRICE_EVENTS.append_rows(
            events,
            value_input_option="USER_ENTERED"
        )

    # ------------------------------------------------
    # DASHBOARD BACKEND
    # ------------------------------------------------

    DASHBOARD.clear()

    DASHBOARD.append_rows([
        ["metric", "value"],
        [
            "Last scrape UTC",
            now.isoformat()
        ],
        [
            "Products scraped",
            len(products)
        ],
        [
            "Events this run",
            len(events)
        ],
        [
            "Price drops",
            sum(
                1
                for e in events
                if e[4] == "PRICE_DROP"
            )
        ],
        [
            "Price increases",
            sum(
                1
                for e in events
                if e[4] == "PRICE_INCREASE"
            )
        ],
    ])


if __name__ == "__main__":

    print("================================")
    print("BELKIN PRICE INTELLIGENCE")
    print("================================")

    print("Loading products from PRODUCT_MASTER...")

    products = load_products()

    if not products:
        print("ERROR: No active products found.")
        raise SystemExit(1)

    print(
        f"Found {len(products)} active Belkin products."
    )

    print("Starting CellphoneS scraper...")

    results = scrape(products)

    print(
        f"SCRAPED: {len(results)} products"
    )

    if not results:
        print(
            "ERROR: No products were scraped."
        )
        raise SystemExit(1)

    main(results)

    print("================================")
    print("TRACKING COMPLETED")
    print("================================")
