"""
Module to retrieve item prices data from a heureka.cz, a comparison site.
"""

# TODO: exceptions
# TODO: async
# TODO: implement logging

import base64
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

# import pandas as pd
# import pandas_gbq
import boto3
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.cloud import bigquery
from google.oauth2 import service_account

from utils import return_list_of_products, return_table_schema, send_response

# set env variables
load_dotenv()
BQ_PROJECT = os.getenv("BQ_PROJECT_ID")
DESTINATION_DATASET = os.getenv("BQ_DATASET")
DESTINATION_TABLE = os.getenv("BQ_L0_TABLE_NAME")

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

    # Initialize KMS client
    kms_client = boto3.client("kms")

    # Get the encrypted key from environment variables
    encrypted_key = base64.b64decode(os.environ["GOOGLE_ENCRYPTED_KEY"])

    # Decrypt the key
    decrypted_key = kms_client.decrypt(CiphertextBlob=encrypted_key)["Plaintext"]

    # Load the key as JSON
    service_account_info = json.loads(decrypted_key)

    client = bigquery.Client(
        project=BQ_PROJECT,
        credentials=service_account.Credentials.from_service_account_info(service_account_info),
    )
    credentials = service_account.Credentials.from_service_account_info(
        info=service_account_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    credentials.refresh(Request())

    access_token = credentials.token

    table_ref = client.dataset(f"{DESTINATION_DATASET}").table(DESTINATION_TABLE)

    event_body = event.get("body", {}) if "body" in event else {}
    logger.info("Received event:  %s", json.dumps(event_body))

    logger.info("Running %s", context.function_name)

    # set up a list for the result data
    products_data = []
    current_timestamp = datetime.now(timezone.utc)

    # this could be async and run faster
    for product in PRODUCTS:

        response = requests.get(url=product["url"], timeout=10)
        parsed_html = BeautifulSoup(response.text, "html.parser")

        # fetch last div to bypass "doporučené nabídky"
        products_list = parsed_html.find_all("div", class_="c-offers-list__cont")[-1]

        products = products_list.find_all("section", class_="c-offer")

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

            products_data.append(
                {
                    "date_extracted": str(current_timestamp),
                    "product_id": product["product_id"],
                    "product_name": product["name"],
                    "color": product["color"],
                    "shop_name": str(img_alt),
                    "price": float(price),
                }
            )

    bq_schema = [
        bigquery.SchemaField("date_extracted", "TIMESTAMP"),
        bigquery.SchemaField("product_id", "INTEGER"),
        bigquery.SchemaField("product_name", "STRING"),
        bigquery.SchemaField("color", "STRING"),
        bigquery.SchemaField("shop_name", "STRING"),
        bigquery.SchemaField("price", "FLOAT"),
    ]

    table_id = f"{BQ_PROJECT}.{DESTINATION_DATASET}.{DESTINATION_TABLE}"
    url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{BQ_PROJECT}/datasets/{DESTINATION_DATASET}/tables/{DESTINATION_TABLE}/insertAll"

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    body = {"rows": [{"json": row} for row in products_data]}

    # Make the API request
    response = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
    print(response)
    try:
        # opens an async stream to bq, data shold show up eventualy
        job_result = client.insert_rows(
            table=table_ref, rows=products_data, selected_fields=bq_schema
        )

        client.insert_rows_json(table=table_ref, json_rows=products_data)
        logger.info("stream initiated")
        # print(f"Insertion job result: {job_result}")

    except Exception as e:  # pylint: disable=broad-except
        return send_response(500, "Failed to upload the data to BigQuery.", e)

    end_time = time.time()

    logger.info(
        "Retrieved prices of %s products in %s seconds!",
        len(products_data),
        round(end_time - start_time, 2),
    )

    try:
        return send_response(
            200,
            "Data is being uploaded",
        )
    except Exception as e:
        logger.error(e)
