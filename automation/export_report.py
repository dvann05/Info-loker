import json
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]

LOGS = ROOT / "automation" / "logs"

DOWNLOAD = Path.home() / "storage" / "downloads"

DOWNLOAD.mkdir(parents=True, exist_ok=True)

OUTPUT = DOWNLOAD / "InfoLoker_Karirhub_Audit_Lengkap.txt"

files = [
    "karirhub_check.json",
    "karirhub_inspection.json",
    "karirhub_js_findings.json",
    "karirhub_routes.txt"
]

report = []

report.append("=" * 70)
report.append("INFOLOKER - KARIRHUB AUDIT REPORT")
report.append("=" * 70)

report.append(
    "Waktu ekspor: " + datetime.now().astimezone().isoformat()
)

report.append("")

for filename in files:

    path = LOGS / filename

    report.append("\n" + "=" * 70)
    report.append("FILE: " + filename)
    report.append("=" * 70)

    if not path.exists():
        report.append("FILE BELUM TERSEDIA")
        continue

    report.append("")

    try:
        if filename.endswith(".json"):

            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            report.append(
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False
                )
            )

        else:

            with open(path, encoding="utf-8") as f:
                report.append(f.read())

    except Exception as error:

        report.append("GAGAL MEMBACA FILE: " + str(error))

report.append("\n" + "=" * 70)
report.append("AKHIR LAPORAN INFOLOKER")
report.append("=" * 70)

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("\n".join(report))

print("\nBERHASIL!")
print("File:", OUTPUT)
print("Ukuran:", OUTPUT.stat().st_size, "bytes")
