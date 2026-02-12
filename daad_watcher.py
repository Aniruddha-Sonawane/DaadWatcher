import requests
import json
import os

BASE_API = "https://www2.daad.de/deutschland/studienangebote/international-programmes/api/solr/en/search.json"
BASE_LINK = "https://www2.daad.de"

DATA_FILE = "daad_programs.json"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

LIMIT = 100


# ---------------- SAFE HELPERS ----------------

def safe_list(value):
    return value if isinstance(value, list) else []


def safe_str(value):
    return "" if value is None else str(value)


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


# ---------------- NORMALIZATION ----------------

def normalize_program(p):

    dates = []
    for d in safe_list(p.get("date")):
        dates.append({
            "start": safe_str(d.get("start")),
            "end": safe_str(d.get("end")),
            "registrationDeadline": safe_str(d.get("registrationDeadline")),
            "costs": safe_str(d.get("costs")),
        })

    return {
        "courseName": safe_str(p.get("courseName")),
        "academy": safe_str(p.get("academy")),
        "city": safe_str(p.get("city")),
        "languages": sorted(safe_list(p.get("languages"))),
        "subject": safe_str(p.get("subject")),
        "programmeDuration": safe_str(p.get("programmeDuration")),
        "date": sorted(dates, key=lambda x: (x["start"], x["end"]))
    }


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
            "disable_web_page_preview": False
        }
    )


def send_long(text):
    MAX = 4000
    for i in range(0, len(text), MAX):
        send_telegram(text[i:i + MAX])


# ---------------- FORMAT ----------------

def format_program(p):

    name = safe_str(p.get("courseName"))
    university = safe_str(p.get("academy"))
    city = safe_str(p.get("city"))

    languages = ", ".join(safe_list(p.get("languages"))) or "Not specified"
    german_level = ", ".join(safe_list(p.get("languageLevelGerman")))
    english_level = ", ".join(safe_list(p.get("languageLevelEnglish")))

    subject = safe_str(p.get("subject")) or "Not specified"
    duration = safe_str(p.get("programmeDuration")) or "Not specified"

    date_info = ""
    for d in safe_list(p.get("date")):
        start = safe_str(d.get("start")) or "N/A"
        end = safe_str(d.get("end")) or "N/A"
        cost = safe_str(d.get("costs")) or "N/A"
        deadline = safe_str(d.get("registrationDeadline")) or "N/A"

        date_info += (
            f"Course Dates: {start} → {end}\n"
            f"Cost: €{cost}\n"
            f"Registration Deadline: {deadline}\n"
        )

    tuition = safe_str(p.get("tuitionFees")) or "Not specified"
    mode = "Online Available" if p.get("isCompleteOnlinePossible") else "Onsite"
    financial = safe_str(p.get("financialSupport")) or "Not specified"

    link_path = p.get("link")
    full_link = f"{BASE_LINK}{link_path}" if link_path else "Not available"

    return (
        f"*{name}*\n"
        f"University: {university}\n"
        f"City: {city}\n"
        f"Languages: {languages}\n"
        f"German Level: {german_level}\n"
        f"English Level: {english_level}\n"
        f"Subject: {subject}\n"
        f"Duration: {duration}\n"
        f"{date_info}"
        f"Tuition Fees: {tuition}\n"
        f"Mode: {mode}\n"
        f"Financial Support: {financial}\n"
        f"Link: {full_link}\n"
    )


# ---------------- MAIN ----------------

def main():

    current = fetch_all_programs()
    old = load_old()

    # FIRST RUN
    if old is None:

        message = f"🎓 *DAAD PROGRAMMES INITIAL SNAPSHOT*\n"
        message += f"Total Programmes: {len(current)}\n\n"

        for p in current:
            message += format_program(p) + "\n"

        send_long(message)
        save_current(current)

        print("Initial snapshot saved and sent.")
        return

    # NORMAL RUN
    current_by_id = {p["id"]: p for p in current}
    old_by_id = {p["id"]: p for p in old}

    added = []
    removed = []

    new_ids = set(current_by_id) - set(old_by_id)
    removed_ids = set(old_by_id) - set(current_by_id)

    for pid in new_ids:
        added.append(current_by_id[pid])

    for pid in removed_ids:
        removed.append(old_by_id[pid])

    common_ids = set(current_by_id) & set(old_by_id)

    for pid in common_ids:
        if normalize_program(current_by_id[pid]) != normalize_program(old_by_id[pid]):
            removed.append(old_by_id[pid])
            added.append(current_by_id[pid])

    if not added and not removed:
        print("No changes detected.")
        return

    message = "🎓 *DAAD PROGRAMMES UPDATED*\n\n"

    if added:
        message += "🆕 *Added:*\n\n"
        for p in added:
            message += format_program(p) + "\n"

    if removed:
        message += "❌ *Removed:*\n\n"
        for p in removed:
            message += format_program(p) + "\n"

    send_long(message)
    save_current(current)

    print("Changes detected and notification sent.")


if __name__ == "__main__":
    main()
