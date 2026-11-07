import requests
import re
import json
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://karirhub.kemnaker.go.id/"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "automation" / "logs"

OUTPUT.mkdir(parents=True, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/130.0.0.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml"
}

def inspect():

    print("INFOLOKER - KARIRHUB INSPECTOR")

    response = requests.get(
        BASE_URL,
        headers=headers,
        timeout=30
    )

    print("HTTP:", response.status_code)

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    scripts = []

    for script in soup.find_all("script", src=True):
        url = urljoin(BASE_URL, script["src"])
        scripts.append(url)

    links = []

    for link in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, link["href"])

        if "karirhub.kemnaker.go.id" in href:
            links.append({
                "text": link.get_text(" ", strip=True),
                "url": href
            })

    api_patterns = re.findall(
        r'https?://[^"\'\s<>]+|/api/[A-Za-z0-9_/?=&.-]+',
        html
    )

    result = {
        "http_status": response.status_code,
        "title": soup.title.get_text(strip=True) if soup.title else None,
        "scripts": scripts,
        "links": links,
        "possible_endpoints": sorted(set(api_patterns))
    }

    output_file = OUTPUT / "karirhub_inspection.json"

    output_file.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Jumlah JavaScript:", len(scripts))
    print("Jumlah tautan:", len(links))
    print("Kandidat endpoint:", len(api_patterns))
    print("Hasil:", output_file)

if __name__ == "__main__":
    inspect()
