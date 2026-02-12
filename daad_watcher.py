import requests
import json
import os

BASE_API = "https://www2.daad.de/deutschland/studienangebote/international-programmes/api/solr/en/search.json"

DATA_FILE = "daad_programs.json"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

LIMIT = 100


# ---------------- SESSION ----------------

def create_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www2.daad.de/deutschland/studienangebote/international-programmes/en/result/?q="
    })
    return session


# ---------------- FETCH ----------------

def fetch_all_programs():
    session = create_session()
    all_programs = []
    offset = 0

    while True:
        params = {
            "cert": "",
            "admReq": "",
            "langExamPC": "",
            "langExamLC": "",
            "langExamSC": "",
            "langDeAvailable": "",
            "langEnAvailable": "",
            "fee": "",
            "sort": 4,
            "dur": "",
            "q": "",
            "limit": LIMIT,
            "offset": offset,
            "display": "list",
            "isElearning": "",
            "isSep": ""
        }

        response = session.get(BASE_API, params=params)
        response.raise_for_status()

        data = response.json()
        courses = data.get("courses", [])

        if not courses:
            break

        all_programs.extend(courses)
        offset += LIMIT

    return all_programs


# ---------------- STORAGE ----------------

def load_old():
    if not os.path.exists(DATA_FILE):
        return None

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_current(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------- TELEGRAM ----------------

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
    )


def send_long(text):
    MAX = 4000
    for i in range(0, len(text), MAX):
        send_telegram(text[i:i + MAX])


# ---------------- MAIN ----------------

def main():
    current = fetch_all_programs()
    old = load_old()

    current_by_id = {p["id"]: p for p in current}

    if old is None:
        save_current(current)
        print("Initial snapshot saved.")
        return

    old_by_id = {p["id"]: p for p in old}

    added = []
    removed = []

    # Detect new and removed IDs
    new_ids = set(current_by_id) - set(old_by_id)
    removed_ids = set(old_by_id) - set(current_by_id)

    # Handle pure additions
    for pid in new_ids:
        added.append(current_by_id[pid])

    # Handle pure removals
    for pid in removed_ids:
        removed.append(old_by_id[pid])

    # Handle updates as remove + add
    common_ids = set(current_by_id) & set(old_by_id)

    for pid in common_ids:
        if current_by_id[pid] != old_by_id[pid]:
            removed.append(old_by_id[pid])
            added.append(current_by_id[pid])

    if not added and not removed:
        print("No changes detected.")
        return

    message = "🎓 *DAAD PROGRAMMES UPDATED*\n\n"

    if added:
        message += "🆕 *Added:*\n"
        for p in added:
            message += f"• {p['courseName']} – {p['academy']} ({p['city']})\n"
        message += "\n"

    if removed:
        message += "❌ *Removed:*\n"
        for p in removed:
            message += f"• {p['courseName']} – {p['academy']}\n"
        message += "\n"

    send_long(message)
    save_current(current)
    print("Changes detected and notification sent.")


if __name__ == "__main__":
    main()
