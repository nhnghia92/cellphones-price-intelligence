import os
import json
import gspread
from google.oauth2.service_account import Credentials


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


def load_products():
    client = get_google_client()

    spreadsheet = client.open_by_key(
        os.environ["GOOGLE_SHEET_ID"]
    )

    product_sheet = spreadsheet.worksheet(
        "PRODUCT_MASTER"
    )

    url_sheet = spreadsheet.worksheet(
        "PRODUCT_URLS"
    )

    product_rows = product_sheet.get_all_records()
    url_rows = url_sheet.get_all_records()

    # ----------------------------------------
    # PRODUCT MASTER
    # ----------------------------------------

    products = {}

    for row in product_rows:

        active = str(
            row.get("active", "")
        ).upper().strip()

        if active != "TRUE":
            continue

        brand = str(
            row.get("brand", "")
        ).strip()

        if brand.lower() != "belkin":
            continue

        product_id = str(
            row.get("product_id", "")
        ).strip()

        product_name = str(
            row.get("product_name", "")
        ).strip()

        if not product_id:
            continue

        products[product_id] = {
            "product_id": product_id,
            "brand": brand,
            "product_name": product_name,
        }

    # ----------------------------------------
    # PRODUCT URLS
    # ----------------------------------------

    product_urls = []

    for row in url_rows:

        retailer_id = str(
            row.get("retailer_id", "")
        ).strip()

        product_id = str(
            row.get("product_id", "")
        ).strip()

        url = str(
            row.get("url", "")
        ).strip()

        active = str(
            row.get("active", "")
        ).upper().strip()

        if active != "TRUE":
            continue

        if not retailer_id:
            continue

        if not product_id:
            continue

        if not url:
            print(
                f"SKIP {retailer_id} "
                f"{product_id}: missing URL"
            )
            continue

        if product_id not in products:
            print(
                f"SKIP {retailer_id} "
                f"{product_id}: product not found "
                "in PRODUCT_MASTER"
            )
            continue

        product = products[product_id]

        product_urls.append({
            "retailer_id": retailer_id,
            "product_id": product_id,
            "brand": product["brand"],
            "product_name": product["product_name"],
            "url": url,
        })

    print(
        f"Loaded {len(products)} active "
        "Belkin products"
    )

    print(
        f"Loaded {len(product_urls)} active "
        "retailer URLs"
    )

    return product_urls
