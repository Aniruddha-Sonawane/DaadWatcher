import requests
import json
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------- CONFIG ----------------

BASE_API = "https://www2.daad.de/deutschland/studienangebote/international-programmes/api/solr/en/search.json"
DATA_FILE = "daad_programs.json"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

LIMIT = 100


# ---------------- SESSION ----------------

def create_session():
    session = requests.Session()

    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Full browser-like headers
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www2.daad.de/deutschland/studienangebote/international-programmes/en/result/?q=",
        "Origin": "https://www2.daad.de",
        "Connection": "keep-alive"
    })

    return session


session = create_session()


# ---------------- FETCH ALL PROGRAMS ----------------

def fetch_all_programs():
    all_programs = []
    offset = 0
    total = None

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
            "isSep": "",
            "wt": "json"
        }

        try:
            response = session.get(BASE_API, params=params, timeout=(10, 60))
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print("Fetch failed:", e)
            return None

        solr_response = data.get("response", {})
        docs = solr_response.get("docs", [])
        total = solr_response.get("numFound", 0)

        if not docs:
            break

        for p in docs:
            all_programs.append({
                "id": p.get("id"),
                "title": p.get("title"),
                "university": p.get("university"),
                "degree": p.get("degree"),
                "city": p.get("city"),
                "language": p.get("language")
            })

        offset += LIMIT

        if offset >= total:
            break

    print(f"Fetched {len(all_programs)} programs (Total reported: {total}).")
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
        print("Telegram send failed:", e)


def send_long_message(text):
    MAX = 4000
    for i in range(0, len(text), MAX):
        send_telegram(text[i:i + MAX])


# ---------------- CATEGORIZATION ----------------

def categorize_by_degree(programs):
    categories = {}
    for p in programs:
        degree = p.get("degree") or "Other"
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

    message = "🎓 *DAAD PROGRAMMES UPDATED*\n\n"

    if added:
        message += "🆕 *New Programmes:*\n"
        categorized = categorize_by_degree(added)

        for degree, items in categorized.items():
            message += f"\n*{degree}*\n"
            for p in items:
                message += f"• {p['title']} – {p['university']} ({p['city']})\n"

    if removed:
        message += "\n❌ *Removed Programmes:*\n"
        for p in removed:
            message += f"• {p['title']} – {p['university']}\n"

    send_long_message(message)
    save_current(current)


if __name__ == "__main__":
    main()
