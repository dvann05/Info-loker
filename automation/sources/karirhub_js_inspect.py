import requests
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "automation/logs/karirhub_inspection.json"
OUTPUT = ROOT / "automation/logs/karirhub_js_findings.json"
RAW_DIR = ROOT / "automation/logs/karirhub_js"
SUMMARY = ROOT / "automation/logs/karirhub_endpoints.txt"

KEYWORDS = [
    "apiUrl",
    "baseURL",
    "baseUrl",
    "vacancy",
    "vacancies",
    "company",
    "location",
    "education",
    "city",
    "detail",
    "published-industrial-vacancies",
    "available-micro-vacancies",
]

ENDPOINT_PATTERN = re.compile(
    r'["\']([^"\']*/(?:karirhub|v[0-9])/[^"\']+)["\']',
    re.IGNORECASE
)


def inspect():
    with open(INPUT, encoding="utf-8") as f:
        data = json.load(f)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*"
    })

    results = []
    endpoints = set()
    saved = 0

    for url in data["scripts"]:
        if "/_next/static/chunks/" not in url:
            continue

        filename = Path(urlparse(url).path).name
        print("Memeriksa:", filename)

        try:
            response = session.get(url, timeout=30)

            if response.status_code != 200:
                print("HTTP:", response.status_code)
                continue

            content = response.text

            # Simpan JavaScript asli
            raw_file = RAW_DIR / filename
            raw_file.write_text(content, encoding="utf-8")
            saved += 1

            # Cari endpoint
            for match in ENDPOINT_PATTERN.finditer(content):
                endpoints.add(match.group(1))

            # Simpan konteks keyword
            for keyword in KEYWORDS:
                pattern = re.compile(
                    re.escape(keyword),
                    re.IGNORECASE
                )

                for match in list(pattern.finditer(content))[:10]:
                    start = max(0, match.start() - 400)
                    end = min(len(content), match.end() + 600)

                    results.append({
                        "file": filename,
                        "keyword": keyword,
                        "context": content[start:end]
                    })

        except requests.RequestException as error:
            print("Gagal:", error)

    OUTPUT.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    SUMMARY.write_text(
        "\n".join(sorted(endpoints)),
        encoding="utf-8"
    )

    print("\n========== SELESAI ==========")
    print("JavaScript tersimpan:", saved)
    print("Jumlah konteks:", len(results))
    print("Jumlah endpoint:", len(endpoints))
    print("Folder JavaScript:", RAW_DIR)
    print("Daftar endpoint:", SUMMARY)
    print("============================")


if __name__ == "__main__":
    inspect()
