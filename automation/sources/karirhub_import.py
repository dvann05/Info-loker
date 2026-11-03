import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

API = "https://api.kemnaker.go.id/karirhub/vacancy/v2/published-industrial-vacancies"
PORTAL = "https://karirhub.kemnaker.go.id/"
SUPABASE = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

LIMIT = 5
LATEST_PAGES = 20
ARCHIVE_PAGES = 20
STATE_URL = SUPABASE + "/rest/v1/automation_state"


def headers(extra=None):
    result = {
        "apikey": KEY,
        "Authorization": "Bearer " + KEY
    }
    if extra:
        result.update(extra)
    return result


def request(url, method="GET", data=None, extra_headers=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers(extra_headers),
        method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            body = response.read().decode()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        print("HTTP ERROR:", error.code)
        print("URL:", url)
        print("DETAIL SERVER:", detail)
        raise


def epoch(value):
    try:
        return datetime.fromtimestamp(
            int(value), timezone.utc
        ).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def clean(value):
    return str(value or "").strip()



REGION_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "karirhub_regions.json"
)

with open(REGION_FILE, encoding="utf-8") as f:
    REGION_MAP = json.load(f)


def fetch_page(page):
    url = API + "?" + urllib.parse.urlencode({
        "page": page,
        "limit": LIMIT
    })
    result = request(
        url,
        extra_headers={"User-Agent": "Mozilla/5.0"}
    )
    time.sleep(0.2)
    return result


def convert(item, now):
    title = clean(item.get("title"))
    company = clean(item.get("company_name"))
    job_id = clean(item.get("id"))

    if not title or not company or not job_id:
        return None
    if title.lower() in ("ok", "test", "testing"):
        return None
    if item.get("canceled") or item.get("rejected"):
        return None

    published = epoch(item.get("published_at"))
    expires = epoch(item.get("expires_at"))

    if not published:
        return None

    published_dt = datetime.fromisoformat(published)
    if published_dt > now:
        return None

    deadline = None
    if expires:
        expires_dt = datetime.fromisoformat(expires)
        if expires_dt <= now:
            return None
        deadline = expires_dt.date().isoformat()

    skills = item.get("skills") or []
    if not isinstance(skills, list):
        skills = []
    skills = [clean(x) for x in skills if clean(x)]

    details = [
        "Ringkasan lowongan berdasarkan data publik Karirhub Kemnaker.",
        "Periksa tautan melamar untuk informasi tugas dan persyaratan lengkap."
    ]

    job_function = clean(item.get("job_function_name"))
    industry = clean(item.get("industry_name"))
    quota = item.get("available_quota") or item.get("quota")

    if job_function:
        details.append("Bidang pekerjaan: " + job_function)
    if industry:
        details.append("Industri: " + industry)
    if quota:
        details.append("Kuota tersedia menurut sumber: " + str(quota))
    if skills:
        details.append("Keahlian: " + ", ".join(skills))

    def positive_amount(value):
        try:
            amount = int(value)
            return amount if amount > 0 else None
        except (TypeError, ValueError):
            return None

    return {
        "slug": "karirhub-" + job_id,
        "title": title,
        "company_name": company,
        "company_logo": item.get("company_logo_uri"),
        "location": (
            next(
                (
                    REGION_MAP[loc.split(":", 1)[1]]["city"]
                    for loc in (item.get("locations") or [])
                    if isinstance(loc, str)
                    and loc.startswith("city:")
                    and loc.split(":", 1)[1] in REGION_MAP
                ),
                clean(item.get("city_name")) or "Lokasi belum dicantumkan"
            )
        ),
        "province": (
            next(
                (
                    REGION_MAP[loc.split(":", 1)[1]]["province"]
                    for loc in (item.get("locations") or [])
                    if isinstance(loc, str)
                    and loc.startswith("city:")
                    and loc.split(":", 1)[1] in REGION_MAP
                ),
                "Belum dicantumkan"
            )
        ),
        "employment_type": clean(item.get("job_type_name")) or "Tidak dicantumkan",
        "description": "\\n\\n".join(details),
        "requirements": skills,
        "salary_min": positive_amount(item.get("min_salary_amount")),
        "salary_max": positive_amount(item.get("max_salary_amount")),
        "source_url": PORTAL,
        "apply_url": clean(item.get("platform_link")) or None,
        "published_at": published,
        "deadline": deadline,
        "status": "draft"
    }


def get_archive_page():
    result = request(
        STATE_URL + "?select=last_page&state_key=eq.karirhub_archive"
    )
    if not result:
        raise RuntimeError("Posisi arsip Karirhub tidak ditemukan di Supabase.")
    return max(21, int(result[0]["last_page"]))


def save_archive_page(page):
    query = urllib.parse.urlencode({
        "state_key": "eq.karirhub_archive"
    })
    request(
        STATE_URL + "?" + query,
        method="PATCH",
        data={
            "last_page": page,
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        extra_headers={
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
    )


def import_rows(rows):
    if not rows:
        return 0, 0, 0

    unique_rows = {row["slug"]: row for row in rows}
    rows = list(unique_rows.values())
    slugs = [row["slug"] for row in rows]

    query = urllib.parse.urlencode({
        "select": "slug,status",
        "slug": "in.(" + ",".join(slugs) + ")"
    })

    existing = request(SUPABASE + "/rest/v1/jobs?" + query)
    known = {row["slug"]: row.get("status") for row in existing or []}

    inserted = 0
    updated = 0

    for row in rows:
        slug = row["slug"]

        if slug not in known:
            request(
                SUPABASE + "/rest/v1/jobs",
                method="POST",
                data=[row],
                extra_headers={
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
            )
            inserted += 1

        elif known[slug] == "draft":
            update_data = {
                key: value for key, value in row.items()
                if key not in ("slug", "status")
            }
            filter_query = urllib.parse.urlencode({
                "slug": "eq." + slug,
                "status": "eq.draft"
            })
            request(
                SUPABASE + "/rest/v1/jobs?" + filter_query,
                method="PATCH",
                data=update_data,
                extra_headers={
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
            )
            updated += 1

    return len(known), inserted, updated


def main():
    now = datetime.now(timezone.utc)
    latest_items = []
    archive_items = []

    first = fetch_page(1)
    meta = first.get("meta") or {}
    last_page = int(meta.get("last_page") or 1)

    latest_items.extend(first.get("data") or [])
    print(f"Halaman terbaru 1: {len(first.get('data') or [])} data")

    for page in range(2, min(LATEST_PAGES, last_page) + 1):
        result = fetch_page(page)
        items = result.get("data") or []
        if not items:
            break
        latest_items.extend(items)
        print(f"Halaman terbaru {page}: {len(items)} data")

    archive_start = get_archive_page()
    archive_end = min(
        archive_start + ARCHIVE_PAGES - 1,
        last_page
    )

    next_archive_page = archive_start

    if archive_start <= last_page:
        for page in range(archive_start, archive_end + 1):
            result = fetch_page(page)
            items = result.get("data") or []
            if not items:
                break
            archive_items.extend(items)
            print(f"Halaman arsip {page}: {len(items)} data")
            next_archive_page = page + 1

    else:
        next_archive_page = 21

    valid_rows = []
    for item in latest_items + archive_items:
        row = convert(item, now)
        if row:
            valid_rows.append(row)

    already, inserted, updated = import_rows(valid_rows)

    if archive_items:
        if next_archive_page > last_page:
            next_archive_page = 21
        save_archive_page(next_archive_page)

    print("--------------------------------")
    print("Total halaman API :", last_page)
    print("Data terbaru      :", len(latest_items))
    print("Data arsip        :", len(archive_items))
    print("Data valid        :", len(valid_rows))
    print("Sudah ada         :", already)
    print("Data baru         :", inserted)
    print("Draft diperbarui  :", updated)
    print("Arsip berikutnya  :", next_archive_page)
    print("Status baru       : draft")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("IMPORT GAGAL:", error)
        raise
