import requests
import json

BASE_API = "https://www2.daad.de/deutschland/studienangebote/international-programmes/api/solr/en/search.json"

LIMIT = 100
OUTPUT_FILE = "daad_programs.json"


def create_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www2.daad.de/deutschland/studienangebote/international-programmes/en/result/?q="
    })
    return session


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


def main():
    programs = fetch_all_programs()

    print(f"Fetched {len(programs)} programs.")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(programs, f, indent=2, ensure_ascii=False)

    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
