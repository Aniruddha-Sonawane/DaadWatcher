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

    added_ids = set(current_by_id) - set(old_by_id)
    removed_ids = set(old_by_id) - set(current_by_id)

    updated_ids = {
        pid for pid in current_by_id
        if pid in old_by_id and current_by_id[pid] != old_by_id[pid]
    }

    if not added_ids and not removed_ids and not updated_ids:
        print("No changes detected.")
        return

    message = "🎓 *DAAD PROGRAMMES UPDATED*\n\n"

    if added_ids:
        message += "🆕 *Added:*\n"
        for pid in sorted(added_ids):
            p = current_by_id[pid]
            message += f"• {p['courseName']} – {p['academy']} ({p['city']})\n"
        message += "\n"

    if removed_ids:
        message += "❌ *Removed:*\n"
        for pid in sorted(removed_ids):
            p = old_by_id[pid]
            message += f"• {p['courseName']} – {p['academy']}\n"
        message += "\n"

    if updated_ids:
        message += "🔄 *Updated:*\n"
        for pid in sorted(updated_ids):
            p = current_by_id[pid]
            message += f"• {p['courseName']} – {p['academy']}\n"
        message += "\n"

    send_long(message)
    save_current(current)
    print("Changes detected and notification sent.")


if __name__ == "__main__":
    main()
