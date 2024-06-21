"""
Module to retrieve item prices data from a heureka.cz, a comparison site.
"""

# TODO: exceptions
# TODO: async
# TODO: implement logging (loguru?)

import json
import logging
import os
import re
import time
from datetime import datetime

import pandas as pd
import pandas_gbq
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google.oauth2 import service_account

from utils import return_list_of_products, return_table_schema, send_response

# set env variables
load_dotenv()

BQ_PROJECT = os.getenv("BQ_PROJECT_ID")
DESTINATION_DATASET = os.getenv("BQ_DATASET")
DESTINATION_TABLE = os.getenv("BQ_L0_TABLE_NAME")
SERVICE_ACCOUNT_PATH = os.getenv("SERVICE_ACCOUNT_PATH")

PRODUCTS = return_list_of_products()
SCHEMA = return_table_schema()

# start logs
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Scrapes backpack prices from heureka and stores them in the DB.
    """
    start_time = time.time()

    event_body = event.get("body", {}) if "body" in event else {}
    print("Received event:", json.dumps(event_body))

    print(f"Running {context.function_name}")

    # set up a dataframe for the result data
    products_data = pd.DataFrame()

    # this could be async and run faster
    for product in PRODUCTS:

        response = requests.get(url=product["url"], timeout=10)
        parsed_html = BeautifulSoup(response.text, "html.parser")

        # fetch last div to bypass "doporučené nabídky"
        products_list = parsed_html.find_all("div", class_="c-offers-list__cont")[-1]

        data = []

        products = products_list.find_all("section", class_="c-offer")

        current_timestamp = datetime.now()

        for section in products:

            img_tag = section.find("img", class_="c-offer__shop-logo e-image-with-fallback")

            if img_tag:
                img_alt = img_tag["alt"]
            else:
                img_alt = None

            price_tag = section.find("span", class_="c-offer__price u-extra-bold u-delta")

            if price_tag:
                price = price_tag.text.strip()
                price = "".join(re.findall(r"\d", price))
            else:
                price = None

            data.append(
                {
                    "date": current_timestamp,
                    "product_id": product["product_id"],
                    "product_name": product["name"],
                    "color": product["color"],
                    "shop_name": img_alt,
                    "price": price,
                }
            )

        df_data = pd.DataFrame.from_records(data)

        products_data = pd.concat(objs=[products_data, df_data], axis=0)

    # validate data types
    for col in SCHEMA:
        if col["type"] == "STRING":
            products_data[col["name"]] = products_data[col["name"]].astype(str)
        elif col["type"] == "FLOAT":
            products_data[col["name"]] = pd.to_numeric(products_data[col["name"]], errors="coerce")
        elif col["type"] == "INTEGER":
            products_data[col["name"]] = pd.to_numeric(
                products_data[col["name"]], errors="coerce", downcast="integer"
            )
        elif col["type"] == "TIMESTAMP":
            products_data[col["name"]] = pd.to_datetime(products_data[col["name"]], errors="coerce")

    # send the data to BigQuery
    try:
        pandas_gbq.to_gbq(
            dataframe=products_data,
            project_id=BQ_PROJECT,
            destination_table=f"{DESTINATION_DATASET}.{DESTINATION_TABLE}",
            if_exists="append",
            table_schema=SCHEMA,
            credentials=service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH),
        )
    except Exception as e:  # pylint: disable=broad-except
        return send_response(500, "Failed to upload the data to BigQuery.", e)

    end_time = time.time()

    return send_response(
        200,
        f"Retrieved prices of {len(products_data)} products in {round(end_time-start_time, 2)} seconds!",
    )
