"""Utilities module"""

import json
import os

import requests


def return_table_schema():
    """Returns table schema."""
    return [
        {"name": "date_extracted", "type": "TIMESTAMP"},
        {"name": "product_id", "type": "INTEGER"},
        {"name": "product_name", "type": "STRING"},
        {"name": "color", "type": "STRING"},
        {"name": "shop_name", "type": "STRING"},
        {"name": "price", "type": "FLOAT"},
    ]


def return_list_of_products():
    """Returns the list of products where price should be retrieved."""
    return [
        {
            "product_id": 1,
            "name": "Osprey Aether II 65",
            "color": "black",
            "url": "https://turisticke-batohy.heureka.cz/osprey-aether-ii-65l-black_3/#prehled/",
        },
        {
            "product_id": 1,
            "name": "Osprey Aether II 65",
            "color": "blue",
            "url": "https://turisticke-batohy.heureka.cz/osprey-aether-ii-65l-modra_2/#prehled/",
        },
        {
            "product_id": 1,
            "name": "Osprey Aether II 65",
            "color": "garlic mustard green",
            "url": "https://turisticke-batohy.heureka.cz/osprey-aether-ii-65l-garlic-mustard-green_2/#prehled/",
        },
        {
            "product_id": 2,
            "name": "Osprey Kestrel 58",
            "color": "black",
            "url": "https://turisticke-batohy.heureka.cz/osprey-kestrel-58l-black_2/#prehled/",
        },
        {
            "product_id": 2,
            "name": "Osprey Kestrel 58",
            "color": "bonsai green",
            "url": "https://turisticke-batohy.heureka.cz/osprey-kestrel-58l-bonsai-green/#prehled/",
        },
        {
            "product_id": 3,
            "name": "Osprey Atmos Ag 65",
            "color": "black",
            "url": "https://turisticke-batohy.heureka.cz/osprey-atmos-ag-65l-black/#prehled/",
        },
        {
            "product_id": 3,
            "name": "Osprey Atmos Ag 65",
            "color": "venturi blue",
            "url": "https://turisticke-batohy.heureka.cz/osprey-atmos-ag-65l-venturi-blue/#prehled/",
        },
        {
            "product_id": 3,
            "name": "Osprey Atmos Ag 65",
            "color": "mythical green",
            "url": "https://turisticke-batohy.heureka.cz/osprey-atmos-ag-65l-mythical-green/#prehled/",
        },
    ]


def send_telegram_message(message: str, is_alert: bool):
    """
    Function to send a simple message to Telegram via API.
    The function takes two arguements:
        1) message (string) - the message that will be sent to Telgram
        2) is_alert (boolean) - denoting whether the message should be sent
            to the regular logging channel or the alerting channel
    The function returns a HTTP response given by the Telegram API
    """
    if is_alert:
        chat_id = os.getenv("TELEGRAM_ALERTING_CHANNEL_ID")
    else:
        chat_id = os.getenv("TELEGRAM_LOGGING_CHANNEL_ID")

    token = os.getenv("TELEGRAM_BOT_TOKEN")

    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}"

    response = requests.get(url=url, timeout=10).json()

    return response


def send_response(status_code: int, message: str, e=""):
    """
    Sends a HTTP response.
    Args:
        status_code (int): HTTP status
        message (str): message in the body of the response
        e (str) : optional, error description
    """
    if e == "":
        sep = ""
    else:
        sep = "\n"

    message = f"{message}{sep}{e}"

    if status_code not in [200, 202]:
        send_as_alert = False
    else:
        send_as_alert = True

    send_telegram_message(message=message, is_alert=send_as_alert)

    response = {"status_code": status_code, "body": json.dumps({"message": f"{message}"})}
    return response
