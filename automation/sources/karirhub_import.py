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

    description = (
        "Informasi lowongan ini diperoleh dari data publik "
        "Karirhub Kemnaker. Rincian pekerjaan dan persyaratan "
        "lengkap perlu diperiksa kembali melalui sumber lowongan."
    )

    if skills:
        description += "\n\nKeahlian yang tercantum: " + ", ".join(skills)

    return {
        "slug": "karirhub-" + job_id,
        "title": title,
        "company_name": company,
        "company_logo": item.get("company_logo_uri"),
        "location": clean(item.get("city_name")) or "Indonesia",
        "province": "Indonesia",
        "employment_type": clean(item.get("job_type_name")) or "Tidak dicantumkan",
        "description": description,
        "requirements": skills,
        "source_url": PORTAL,
        "apply_url": None,
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
        return 0, 0

    unique_rows = {}
    for row in rows:
        unique_rows[row["slug"]] = row

    rows = list(unique_rows.values())
    slugs = [row["slug"] for row in rows]

    query = urllib.parse.urlencode({
        "select": "slug",
        "slug": "in.(" + ",".join(slugs) + ")"
    })

    existing = request(
        SUPABASE + "/rest/v1/jobs?" + query
    )

    known = {row["slug"] for row in existing or []}
    new_rows = [row for row in rows if row["slug"] not in known]

    if new_rows:
        request(
            SUPABASE + "/rest/v1/jobs",
            method="POST",
            data=new_rows,
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
        )

    return len(known), len(new_rows)


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

    already, inserted = import_rows(valid_rows)

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
    print("Arsip berikutnya  :", next_archive_page)
    print("Status baru       : draft")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("IMPORT GAGAL:", error)
        raise
