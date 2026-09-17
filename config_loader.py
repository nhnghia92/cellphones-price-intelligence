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

    sheet = spreadsheet.worksheet(
        "PRODUCT_MASTER"
    )

    rows = sheet.get_all_records()

    products = []

    for row in rows:

        # Only active products
        active = str(
            row.get("active", "")
        ).upper()

        if active != "TRUE":
            continue

        # Belkin products only for now
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

        url = str(
            row.get("url", "")
        ).strip()

        if not product_id:
            continue

        if not url:
            print(
                f"SKIP {product_id}: "
                "missing URL"
            )
            continue

        products.append({
            "product_id": product_id,
            "brand": brand,
            "product_name": product_name,
            "url": url,
        })

    print(
        f"Loaded {len(products)} "
        "active Belkin products"
    )

    return products
