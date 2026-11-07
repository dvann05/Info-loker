import requests
import json
import re
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "automation/logs/karirhub_inspection.json"
OUTPUT = Path.home() / "storage/downloads/Karirhub_API_Audit.txt"

KEYWORDS = [
    "published-industrial-vacancies",
    "available-micro-vacancies",
    "api-wlkp",
    "baseURL",
    "baseUrl",
    "axios.create",
    "fetch(",
    "vacancy/v2",
    "vacancy/v1",
    "pagination",
    "pageSize"
]

with open(INPUT, encoding="utf-8") as f:
    data = json.load(f)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})

results = []

for url in data["scripts"]:

    if "/_next/static/chunks/" not in url:
        continue

    try:
        response = session.get(url, timeout=25)

        if response.status_code != 200:
            continue

        content = response.text

        for keyword in KEYWORDS:

            for match in list(
                re.finditer(re.escape(keyword), content, re.I)
            )[:5]:

                start = max(0, match.start() - 500)
                end = min(len(content), match.end() + 700)

                results.append(
                    f"\nFILE: {url}\n"
                    f"KEYWORD: {keyword}\n"
                    f"CONTEXT:\n{content[start:end]}\n"
                    + "=" * 80
                )

    except requests.RequestException:
        continue

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

OUTPUT.write_text(
    "\n".join(results),
    encoding="utf-8"
)

print("PEMERIKSAAN SELESAI")
print("Jumlah temuan:", len(results))
print("File:", OUTPUT)
print("Ukuran:", OUTPUT.stat().st_size, "bytes")
