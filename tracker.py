import os
import json
from datetime import datetime, timezone, timedelta

import gspread
from google.oauth2.service_account import Credentials

from config_loader import load_products
from retailer_router import scrape_all


HEAD = {
    "PRICE_RAW": [
        "timestamp",
        "retailer_id",
        "brand",
        "product_id",
        "product_name",
        "price",
        "original_price",
        "discount_pct",
        "promotion",
        "url",
    ],

    "STOCK_RAW": [
        "timestamp",
        "retailer_id",
        "brand",
        "product_id",
        "product_name",
        "city",
        "stock",
        "stock_status",
        "url",
    ],

    "PRICE_DAILY": [
        "date",
        "retailer_id",
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
        "retailer_id",
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


def get_sheet(spreadsheet, name):

    try:

        sheet = spreadsheet.worksheet(name)

    except gspread.WorksheetNotFound:

        sheet = spreadsheet.add_worksheet(
            title=name,
            rows=2000,
            cols=20,
        )

        sheet.append_row(
            HEAD[name]
        )

    return sheet


def to_number(value):

    if value is None:
        return None

    try:

        text = str(value).strip()

        if not text:
            return None

        return float(
            text.replace(",", "")
                .replace(".", "")
        )

    except (ValueError, TypeError):

        return None


def percentage(current, previous):

    if current is None:
        return None

    if previous is None:
        return None

    if previous == 0:
        return None

    return round(
        (current - previous)
        / previous
        * 100,
        2,
    )


def get_min_change_pct():

    value = os.getenv(
        "MIN_CHANGE_PCT",
        "5",
    )

    if value is None:
        return 5.0

    value = str(value).strip()

    if not value:
        return 5.0

    try:

        return float(value)

    except ValueError:

        print(
            "WARNING: Invalid MIN_CHANGE_PCT. "
            "Using 5%."
        )

        return 5.0


def main(products):

    print(
        "Connecting to Google Sheets..."
    )

    client = get_google_client()

    spreadsheet = client.open_by_key(
        os.environ["GOOGLE_SHEET_ID"]
    )

    price_raw = get_sheet(
        spreadsheet,
        "PRICE_RAW",
    )

    stock_raw = get_sheet(
        spreadsheet,
        "STOCK_RAW",
    )

    price_daily = get_sheet(
        spreadsheet,
        "PRICE_DAILY",
    )

    price_events = get_sheet(
        spreadsheet,
        "PRICE_EVENTS",
    )

    dashboard = get_sheet(
        spreadsheet,
        "DASHBOARD",
    )

    print(
        "Google Sheets connected."
    )

    # ========================================
    # SAVE RAW PRICE DATA
    # ========================================

    raw_rows = []

    for product in products:

        raw_rows.append([
            product.get(
                "timestamp",
                "",
            ),

            product.get(
                "retailer_id",
                "",
            ),

            product.get(
                "brand",
                "",
            ),

            product.get(
                "product_id",
                "",
            ),

            product.get(
                "product_name",
                "",
            ),

            product.get(
                "price",
                "",
            ),

            product.get(
                "original_price",
                "",
            ),

            product.get(
                "discount_pct",
                "",
            ),

            product.get(
                "promotion",
                "",
            ),

            product.get(
                "url",
                "",
            ),
        ])

    if raw_rows:

        print(
            f"Saving {len(raw_rows)} "
            "price records..."
        )

        price_raw.append_rows(
            raw_rows,
            value_input_option="USER_ENTERED",
        )

    else:

        print(
            "WARNING: No raw price data."
        )

    # ========================================
    # SAVE RAW STOCK DATA
    # ========================================

    stock_rows = []

    for product in products:

        stock_records = product.get(
            "stock_records",
            []
        )

        for stock in stock_records:

            stock_rows.append([
                product.get(
                    "timestamp",
                    "",
                ),

                product.get(
                    "retailer_id",
                    "",
                ),

                product.get(
                    "brand",
                    "",
                ),

                product.get(
                    "product_id",
                    "",
                ),

                product.get(
                    "product_name",
                    "",
                ),

                stock.get(
                    "city",
                    "",
                ),

                stock.get(
                    "stock",
                    "",
                ),

                stock.get(
                    "stock_status",
                    "UNKNOWN",
                ),

                product.get(
                    "url",
                    "",
                ),
            ])

    if stock_rows:

        print(
            f"Saving {len(stock_rows)} "
            "stock records..."
        )

        stock_raw.append_rows(
            stock_rows,
            value_input_option="USER_ENTERED",
        )

    else:

        print(
            "No stock records returned "
            "by scrapers."
        )

    # ========================================
    # READ PRICE HISTORY
    # ========================================

    print(
        "Reading price history..."
    )

    raw = price_raw.get_all_values()

    now = datetime.now(
        timezone.utc
    )

    history = {}

    for row in raw[1:]:

        if len(row) < 6:
            continue

        retailer_id = row[1]

        product_id = row[3]

        if not retailer_id:
            continue

        if not product_id:
            continue

        price = to_number(
            row[5]
        )

        if price is None:
            continue

        timestamp_text = row[0]

        try:

            timestamp = datetime.fromisoformat(
                timestamp_text.replace(
                    "Z",
                    "+00:00",
                )
            )

        except Exception:

            continue

        key = (
            retailer_id,
            product_id,
        )

        history.setdefault(
            key,
            []
        ).append(
            (
                timestamp,
                price,
            )
        )

    # ========================================
    # PRODUCT LOOKUP
    # ========================================

    product_lookup = {}

    for product in products:

        product_id = product.get(
            "product_id"
        )

        if product_id:

            product_lookup[
                product_id
            ] = product

    # ========================================
    # CALCULATE DAILY DATA
    # ========================================

    daily_rows = []

    events = []

    min_change_pct = (
        get_min_change_pct()
    )

    print(
        "Minimum price event threshold: "
        f"{min_change_pct}%"
    )

    for (
        retailer_id,
        product_id,
    ), records in history.items():

        records.sort(
            key=lambda x: x[0]
        )

        if not records:
            continue

        current_price = records[-1][1]

        previous_price = (
            records[-2][1]
            if len(records) >= 2
            else None
        )

        # ------------------------------------
        # FIND HISTORICAL PRICE
        # ------------------------------------

        def get_price_before(days):

            cutoff = (
                now
                - timedelta(days=days)
            )

            eligible = [
                price
                for timestamp, price
                in records
                if timestamp <= cutoff
            ]

            if not eligible:
                return None

            return eligible[-1]

        price_1d = (
            get_price_before(1)
        )

        price_7d = (
            get_price_before(7)
        )

        price_30d = (
            get_price_before(30)
        )

        change_1d = percentage(
            current_price,
            price_1d,
        )

        change_7d = percentage(
            current_price,
            price_7d,
        )

        change_30d = percentage(
            current_price,
            price_30d,
        )

        # ------------------------------------
        # 30 DAY STATISTICS
        # ------------------------------------

        cutoff_30d = (
            now
            - timedelta(days=30)
        )

        recent_prices = [
            price
            for timestamp, price
            in records
            if timestamp >= cutoff_30d
        ]

        if not recent_prices:

            recent_prices = [
                current_price
            ]

        # ------------------------------------
        # PRODUCT INFORMATION
        # ------------------------------------

        product_info = (
            product_lookup.get(
                product_id
            )
        )

        if product_info:

            brand = product_info.get(
                "brand",
                "",
            )

            product_name = (
                product_info.get(
                    "product_name",
                    "",
                )
            )

        else:

            brand = ""

            product_name = ""

        # ------------------------------------
        # DAILY ROW
        # ------------------------------------

        daily_rows.append([
            now.date().isoformat(),

            retailer_id,

            product_id,

            brand,

            product_name,

            current_price,

            change_1d,

            change_7d,

            change_30d,

            min(recent_prices),

            round(
                sum(recent_prices)
                / len(recent_prices),
                0,
            ),
        ])

        # ====================================
        # PRICE EVENTS
        # ====================================

        if (
            change_1d is not None
            and abs(change_1d)
            >= min_change_pct
        ):

            if change_1d < 0:

                event_type = (
                    "PRICE_DROP"
                )

            else:

                event_type = (
                    "PRICE_INCREASE"
                )

            if abs(change_1d) >= 10:

                severity = "HIGH"

            else:

                severity = "MEDIUM"

            if previous_price is not None:

                previous_display = (
                    f"{previous_price:,.0f}"
                )

            else:

                previous_display = "N/A"

            current_display = (
                f"{current_price:,.0f}"
            )

            events.append([
                now.isoformat(),

                retailer_id,

                product_id,

                brand,

                product_name,

                event_type,

                change_1d,

                severity,

                (
                    f"{previous_display} "
                    f"-> "
                    f"{current_display}"
                ),
            ])

    # ========================================
    # SAVE DAILY DATA
    # ========================================

    if daily_rows:

        print(
            f"Saving {len(daily_rows)} "
            "daily records..."
        )

        price_daily.append_rows(
            daily_rows,
            value_input_option="USER_ENTERED",
        )

    else:

        print(
            "No daily records generated."
        )

    # ========================================
    # SAVE EVENTS
    # ========================================

    if events:

        print(
            f"Detected {len(events)} "
            "price events."
        )

        price_events.append_rows(
            events,
            value_input_option="USER_ENTERED",
        )

    else:

        print(
            "No significant price events "
            "detected."
        )

    # ========================================
    # UPDATE DASHBOARD BACKEND
    # ========================================

    print(
        "Updating dashboard backend..."
    )

    dashboard.clear()

    dashboard.append_rows([
        [
            "metric",
            "value",
        ],

        [
            "Last scrape UTC",
            now.isoformat(),
        ],

        [
            "Products scraped",
            len(products),
        ],

        [
            "Price records",
            len(raw_rows),
        ],

        [
            "Stock records",
            len(stock_rows),
        ],

        [
            "Retailers scraped",
            len(
                set(
                    product.get(
                        "retailer_id",
                        "",
                    )
                    for product in products
                )
            ),
        ],

        [
            "Events this run",
            len(events),
        ],

        [
            "Price drops",
            sum(
                1
                for event in events
                if event[5]
                == "PRICE_DROP"
            ),
        ],

        [
            "Price increases",
            sum(
                1
                for event in events
                if event[5]
                == "PRICE_INCREASE"
            ),
        ],
    ])

    print(
        "Tracking completed successfully."
    )


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":

    print("")

    print(
        "========================================"
    )

    print(
        "PRICE & STOCK INTELLIGENCE"
    )

    print(
        "========================================"
    )

    print("")

    # ----------------------------------------
    # LOAD PRODUCT + RETAILER URLS
    # ----------------------------------------

    print(
        "Loading products and retailer URLs..."
    )

    products = load_products()

    if not products:

        print(
            "ERROR: No active retailer URLs "
            "found."
        )

        raise SystemExit(1)

    print(
        f"Found {len(products)} "
        "active retailer URLs."
    )

    print("")

    # ----------------------------------------
    # SCRAPE ALL RETAILERS
    # ----------------------------------------

    print(
        "Starting retailer scrapers..."
    )

    print("")

    results = scrape_all(
        products
    )

    print("")

    print(
        f"SCRAPED: {len(results)} "
        "price records"
    )

    if not results:

        print(
            "ERROR: No products were scraped."
        )

        raise SystemExit(1)

    print("")

    # ----------------------------------------
    # SAVE + ANALYZE
    # ----------------------------------------

    main(results)

    print("")

    print(
        "========================================"
    )

    print(
        "TRACKING COMPLETED"
    )

    print(
        "========================================"
    )
