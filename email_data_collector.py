"""
Collects data from the receipt emails from Morrison's and
inserts it into a database
"""


import os
import pickle
from datetime import datetime
from base64 import urlsafe_b64decode
from typing import Optional, Any

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


def gmail_authenticate() -> Optional[Any]:
    """
    Authenticates the user to access the 'Groceries' project

    :return: A service to enable interaction with the Google API
    """
    creds = None

    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json',
                                                             ['https://mail.google.com/'])
            creds = flow.run_local_server(port=0)

        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)


def search_messages(service: Any, query: str) -> list[dict[str, str]]:
    """
    Searches the user's mailbox for any emails that satisfy the given query

    :param service: The resource to interact with the Google API
    :param query: The query string to select emails
    :return: A list of email identifiers that can be used to identify the wanted emails
    """
    result = service.users().messages().list(userId='me', q=query).execute()
    messages = []
    if 'messages' in result:
        messages.extend(result['messages'])
    while 'nextPageToken' in result:
        page_token = result['nextPageToken']
        result = service.users().messages().list(userId='me',
                                                 q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
    return messages


def get_data(service: Any, message: dict[str, str]) \
        -> tuple[str, dict[str, tuple[float, float]]]:
    """
    Collects the desired Grocery data from the given email

    :param service: The resource to interact with the Google API
    :param message: The email identifier for the desired email
    :return: The date of the delivery, and the (amount, cost/item)
    information about the items purchased
    """
    msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()

    payload = msg['payload']
    parts = payload.get("parts")

    text = urlsafe_b64decode(parts[0]["body"]["data"]).decode()

    text_lines = text.split("\n")

    data_mode = False

    date = ""

    data = {}

    ctr = 0

    while ctr < len(text_lines):
        line = text_lines[ctr]

        if not data_mode:
            if "Delivery date" in line:
                date = datetime.strptime(text_lines[ctr + 1].strip(),
                                         "%d %b %Y").strftime("%d-%m-%Y")
                ctr += 1

            if "Your Items" in line:
                data_mode = True
            ctr += 1
        else:
            if line.strip() == "":
                break

            item = text_lines[ctr].strip()
            amount = float(text_lines[ctr + 1].strip())
            cost = float(text_lines[ctr + 2].strip().replace("£", "")) / amount

            data[item] = (amount, cost)

            ctr += 3

    return date, data


def collect_grocery_data():
    """
    Collects the data about all the grocery orders and inserts them into a database
    """
    gmail_service = gmail_authenticate()
    messages = search_messages(gmail_service, "label:groceries")

    full_msg_data = {}

    for msg in messages:
        key, data = get_data(gmail_service, msg)
        full_msg_data[key] = data


print(collect_grocery_data())
