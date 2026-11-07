import requests
import re
import json
from pathlib import Path

URL = "https://karirhub.kemnaker.go.id/"

OUTPUT = Path.home() / "storage/downloads/Karirhub_Config_Findings.json"

response = requests.get(
    URL,
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=30
)

html = response.text

patterns = [
    r'"apiUrl"\s*:\s*"([^"]+)"',
    r'"api_url"\s*:\s*"([^"]+)"',
    r'apiUrl\s*:\s*"([^"]+)"',
    r'apiUrl\s*=\s*"([^"]+)"',
    r'https?://[^"\'\s<>]+'
]

results = {
    "http_status": response.status_code,
    "page_url": response.url,
    "findings": []
}

for pattern in patterns:
    matches = re.findall(pattern, html, re.I)

    for match in matches:
        results["findings"].append(match)

results["findings"] = list(set(results["findings"]))

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

OUTPUT.write_text(
    json.dumps(results, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("Audit selesai")
print("HTTP:", response.status_code)
print("Temuan:", len(results["findings"]))
print("File:", OUTPUT)
