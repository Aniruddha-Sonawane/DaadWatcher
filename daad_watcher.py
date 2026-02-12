import requests
import json
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------- CONFIG ----------------

API_URL = "https://www2.daad.de/deutschland/studienangebote/international-programmes/en/result/?q=&format=json"
DATA_FILE = "daad_programs.json"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# ---------------- SESSION ----------------

def create_session():
    session = requests.Session()

    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({
        "User-Agent": "Mozilla/5.0"
    })

    return session


session = create_session()

# ---------------- FETCH ALL PAGES ----------------

def fetch_all_programs():
    page = 1
    all_programs = []

    while True:
        try:
            r = session.get(API_URL + f"&page={page}", timeout=(10, 60))
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print("Fetch failed:", e)
            return None

        data = r.json()

        programs = data.get("results", [])
        if not programs:
            break

        for p in programs:
            all_programs.append({
                "id": p.get("id"),
                "title": p.get("title"),
                "university": p.get("university"),
                "degree": p.get("degree"),
                "language": p.get("language"),
                "city": p.get("city")
            })

        page += 1

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
    try:
        session.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            },
            timeout=(5, 20)
        )
    except Exception as e:
        print("Telegram failed:", e)


def send_long(text):
    MAX = 4000
    for i in range(0, len(text), MAX):
        send_telegram(text[i:i + MAX])


# ---------------- CATEGORIZE ----------------

def categorize(programs):
    categories = {}

    for p in programs:
        degree = p["degree"] or "Other"
        categories.setdefault(degree, []).append(p)

    return categories


# ---------------- MAIN ----------------

def main():
    current = fetch_all_programs()

    if current is None:
        print("Skipping update due to fetch failure.")
        return

    old = load_old()

    current_ids = {p["id"] for p in current}

    if old is None:
        save_current(current)
        print("Initial snapshot saved.")
        return

    old_ids = {p["id"] for p in old}

    added_ids = current_ids - old_ids
    removed_ids = old_ids - current_ids

    if not added_ids and not removed_ids:
        print("No changes detected.")
        return

    added = [p for p in current if p["id"] in added_ids]
    removed = [p for p in old if p["id"] in removed_ids]

    msg = "🎓 *DAAD PROGRAMMES UPDATED*\n\n"

    if added:
        msg += "🆕 *New Programmes:*\n"
        categorized = categorize(added)

        for degree, items in categorized.items():
            msg += f"\n*{degree}*\n"
            for p in items:
                msg += f"• {p['title']} – {p['university']} ({p['city']})\n"

    if removed:
        msg += "\n❌ *Removed Programmes:*\n"
        for p in removed:
            msg += f"• {p['title']} – {p['university']}\n"

    send_long(msg)
    save_current(current)


if __name__ == "__main__":
    main()
