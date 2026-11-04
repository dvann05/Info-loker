import os
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

API = "https://api.kemnaker.go.id/karirhub/vacancy/v2/published-industrial-vacancies"
SUPABASE = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
LIMIT = 1
REGION_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "karirhub_regions.json"
)


def request(url, method="GET", data=None, extra_headers=None):
    headers = {
        "apikey": KEY,
        "Authorization": "Bearer " + KEY
    }
    if extra_headers:
        headers.update(extra_headers)

    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        url, data=body, headers=headers, method=method
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def epoch_iso(value):
    try:
        return datetime.fromtimestamp(
            int(value), timezone.utc
        ).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def positive_int(value):
    try:
        number = int(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def load_drafts():
    rows = []
    offset = 0

    while True:
        query = urllib.parse.urlencode({
            "select": "slug,status",
            "status": "eq.draft",
            "slug": "like.karirhub-*",
            "order": "slug.asc",
            "limit": 1000,
            "offset": offset
        })

        batch = request(SUPABASE + "/rest/v1/jobs?" + query)
        rows.extend(batch or [])

        if not batch or len(batch) < 1000:
            break

        offset += len(batch)

    return {row["slug"] for row in rows if row.get("slug")}


def make_patch(item, regions):
    patch = {}

    for value in item.get("locations") or []:
        if isinstance(value, str) and value.startswith("city:"):
            region = regions.get(value.split(":", 1)[1])
            if region and region.get("city") and region.get("province"):
                patch["location"] = region["city"]
                patch["province"] = region["province"]
                break

    apply_url = str(item.get("platform_link") or "").strip()
    if apply_url.startswith(("https://", "http://")):
        patch["apply_url"] = apply_url

    employment = str(item.get("job_type_name") or "").strip()
    if employment:
        patch["employment_type"] = employment

    skills = item.get("skills")
    if isinstance(skills, list):
        skills = [str(x).strip() for x in skills if str(x).strip()]
        if skills:
            patch["requirements"] = skills

    low = positive_int(item.get("min_salary_amount"))
    high = positive_int(item.get("max_salary_amount"))

    if low is not None:
        patch["salary_min"] = low
    if high is not None:
        patch["salary_max"] = high

    published = epoch_iso(item.get("published_at"))
    if published:
        patch["published_at"] = published

    deadline = epoch_iso(item.get("expires_at"))
    if deadline:
        patch["deadline"] = deadline[:10]

    logo = str(item.get("company_logo_uri") or "").strip()
    if logo.startswith(("https://", "http://")):
        patch["company_logo"] = logo

    return patch


def main():
    with open(REGION_FILE, encoding="utf-8") as file:
        regions = json.load(file)

    targets = load_drafts()
    print("Draft Karirhub ditemukan:", len(targets))

    if not targets:
        print("Tidak ada draft untuk diperbarui.")
        return

    matched = {}

    first = request(
        API + "?" + urllib.parse.urlencode({
            "page": 1
        }),
        extra_headers={"User-Agent": "Mozilla/5.0"}
    )

    last_page = int((first.get("meta") or {}).get("last_page") or 1)

    def collect(items):
        for item in items or []:
            job_id = str(item.get("id") or "").strip()
            slug = "karirhub-" + job_id

            if job_id and slug in targets:
                matched[slug] = item

    collect(first.get("data"))
    print(f"Halaman 1/{last_page}: {len(matched)}/{len(targets)} cocok")

    for page in range(2, last_page + 1):
        if len(matched) == len(targets):
            break

        result = request(
            API + "?" + urllib.parse.urlencode({
                "page": page
            }),
            extra_headers={"User-Agent": "Mozilla/5.0"}
        )

        collect(result.get("data"))

        if page % 25 == 0 or len(matched) == len(targets):
            print(
                f"Halaman {page}/{last_page}: "
                f"{len(matched)}/{len(targets)} cocok"
            )

        if not result.get("data"):
            break

        time.sleep(0.15)

    updated = 0
    skipped = 0

    for slug, item in matched.items():
        patch = make_patch(item, regions)

        if not patch:
            skipped += 1
            continue

        query = urllib.parse.urlencode({
            "slug": "eq." + slug,
            "status": "eq.draft"
        })

        request(
            SUPABASE + "/rest/v1/jobs?" + query,
            method="PATCH",
            data=patch,
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
        )

        updated += 1

    print("--------------------------------")
    print("Total draft ditemukan :", len(targets))
    print("Cocok dengan API       :", len(matched))
    print("Berhasil diperbarui    :", updated)
    print("Tidak ada data baru    :", skipped)
    print("Belum ditemukan        :", len(targets) - len(matched))
    print("Hanya status draft yang diperbarui.")
    print("Pendidikan, pengalaman, benefit, dan URL detail")
    print("tidak diisi jika sumber API tidak menyediakannya.")


if __name__ == "__main__":
    main()
