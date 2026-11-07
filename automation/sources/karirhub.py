import requests
import json
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup

BASE_URL = "https://karirhub.kemnaker.go.id/"

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "automation" / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)

def check_karirhub():
    print("=" * 45)
    print("INFOLOKER - KARIRHUB SOURCE CHECKER")
    print("=" * 45)

    result = {
        "source": "Karirhub Kemnaker",
        "url": BASE_URL,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "unknown",
        "http_status": None,
        "title": None,
        "final_url": None,
        "error": None
    }

    try:
        response = requests.get(
            BASE_URL,
            headers={
                "User-Agent": "InfoLokerSourceChecker/1.0",
                "Accept": "text/html"
            },
            timeout=25
        )

        result["http_status"] = response.status_code
        result["final_url"] = response.url

        if response.status_code == 200:
            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            if soup.title:
                result["title"] = soup.title.get_text(
                    strip=True
                )

            result["status"] = "online"

        else:
            result["status"] = "http_error"

    except requests.RequestException as error:
        result["status"] = "connection_error"
        result["error"] = str(error)

    output = LOG_DIR / "karirhub_check.json"

    output.write_text(
        json.dumps(result, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"Status       : {result['status']}")
    print(f"HTTP         : {result['http_status']}")
    print(f"Judul        : {result['title']}")
    print(f"URL          : {result['final_url']}")

    if result["error"]:
        print(f"Error        : {result['error']}")

    print(f"Log          : {output}")
    print("=" * 45)

    return result


if __name__ == "__main__":
    check_karirhub()
