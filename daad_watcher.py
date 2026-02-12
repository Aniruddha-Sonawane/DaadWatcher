import requests
import json
import os
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------- CONFIG ----------------

URL = "https://www2.daad.de/deutschland/studienangebote/international-programmes/en/result/?q="
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
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    })

    return session


session = create_session()

# ---------------- FETCH PROGRAMS ----------------

def fetch_all_programs():
    try:
        r = session.get(URL, timeout=(10, 60))
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Fetch failed:", e)
        return None

    html = r.text

    # Extract embedded JSON from page
    match = re.search(
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
        html,
        re.DOTALL
    )

    if not match:
        print("Embedded JSON not found.")
        return None

    json_text = match.group(1)

    try:
        data = json.loads(json_text)
    except Exception as e:
        print("JSON parsing failed:", e)
        return None

    # Navigate safely through structure
    try:
        results = data["search"]["results"]
    except Exception:
        print("Unexpected JSON structure.")
        return None

    programs = []

    for p in results:
        programs.append({
            "id": p.get("id"),
            "title": p.get("title"),
            "university": p.get("universityName"),
            "degree": p.get("degreeName"),
            "city": p.get("city"),
            "language": ", ".join(p.get("languages", []))
        })

    return programs


# ---------------- STORAGE ----------------

def load_old():
    if not os.path.exists(DATA_FILE):
        return None
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


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

    # FIRST RUN
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
