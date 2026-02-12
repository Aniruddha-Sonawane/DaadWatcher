import requests
import json
import os
import time

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATA_FILE = "daad_programs.json"

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    response = requests.get(url, params=params)
    return response.json()


def send_document(chat_id, file_path):
    url = f"{BASE_URL}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": ("daad_programs.txt", f)}
        data = {"chat_id": chat_id}
        requests.post(url, files=files, data=data)


def main():

    offset = None

    updates = get_updates(offset)

    if not updates.get("ok"):
        return

    for update in updates.get("result", []):

        offset = update["update_id"] + 1

        message = update.get("message")
        if not message:
            continue

        text = message.get("text")
        chat_id = message["chat"]["id"]

        if text == "/getjson":

            if not os.path.exists(DATA_FILE):
                requests.post(
                    f"{BASE_URL}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "JSON file not found."
                    }
                )
                continue

            # Create temporary txt copy
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read()

            with open("daad_programs.txt", "w", encoding="utf-8") as f:
                f.write(content)

            send_document(chat_id, "daad_programs.txt")

    # Clear processed updates
    if offset:
        requests.get(f"{BASE_URL}/getUpdates", params={"offset": offset})


if __name__ == "__main__":
    main()
