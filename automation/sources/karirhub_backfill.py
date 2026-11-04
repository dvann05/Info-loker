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
LIMIT = 5

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

    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read().decode()
                return json.loads(raw) if raw else None

        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                delay = min(2 ** attempt, 16)
                print(f"HTTP {exc.code}; percobaan {attempt}/5. Ulangi dalam {delay} detik...", flush=True)
                time.sleep(delay)
                continue
            raise RuntimeError(
                f"HTTP {exc.code} | URL: {exc.url} | DETAIL: {detail}"
            ) from exc

        except urllib.error.URLError as exc:
            if attempt < 5:
                delay = min(2 ** attempt, 16)
                print(f"Koneksi gagal; percobaan {attempt}/5. Ulangi dalam {delay} detik...", flush=True)
                time.sleep(delay)
                continue
            raise RuntimeError(
                f"Koneksi gagal | URL: {url} | DETAIL: {exc}"
            ) from exc


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

    return {
        row["slug"] for row in rows
        if row.get("slug")
    }


def fetch_page(page):
    url = API + "?" + urllib.parse.urlencode({
        "page": page,
        "limit": LIMIT
    })

    return request(
        url,
        extra_headers={"User-Agent": "Mozilla/5.0"}
    )


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
    started = time.time()

    with open(REGION_FILE, encoding="utf-8") as file:
        regions = json.load(file)

    targets = load_drafts()

    print("Draft Karirhub ditemukan:", len(targets), flush=True)

    if not targets:
        print("Tidak ada draft untuk diperbarui.", flush=True)
        return

    matched = {}

    print("Menghubungi API Karirhub...", flush=True)

    first = fetch_page(1)
    meta = first.get("meta") or {}
    api_last_page = int(meta.get("last_page") or 1)

    state_query = urllib.parse.urlencode({
        "select": "last_page",
        "state_key": "eq.karirhub_archive"
    })
    state_rows = request(SUPABASE + "/rest/v1/automation_state?" + state_query)

    if not state_rows:
        raise RuntimeError("Posisi arsip Karirhub tidak ditemukan.")

    archive_next_page = int(state_rows[0].get("last_page") or 21)
    scan_start_page = 281
    scan_end_page = min(api_last_page, scan_start_page + 139)

    print("Total halaman API:", api_last_page, flush=True)
    print("Rentang halaman backfill:", scan_start_page, "-", scan_end_page, flush=True)

    def collect(items):
        for item in items or []:
            job_id = str(item.get("id") or "").strip()
            slug = "karirhub-" + job_id

            if job_id and slug in targets:
                matched[slug] = item

    for page in range(scan_start_page, scan_end_page + 1):
        print(
            f"Memproses halaman {page}/{scan_end_page}...",
            flush=True
        )

        if page == 1:
            result = first
        else:
            result = fetch_page(page)

        items = result.get("data") or []
        collect(items)

        print(
            f"Halaman {page}: {len(items)} data | "
            f"Cocok: {len(matched)}/{len(targets)}",
            flush=True
        )

        if len(matched) >= len(targets):
            print("Semua draft berhasil dicocokkan.", flush=True)
            break

        if not items:
            print("API tidak mengembalikan data lagi.", flush=True)
            break

        time.sleep(0.1)

    print("--------------------------------", flush=True)
    print("Mulai memperbarui Supabase...", flush=True)

    updated = 0
    skipped = 0
    unchanged = 0

    for index, (slug, item) in enumerate(matched.items(), 1):
        patch = make_patch(item, regions)

        if not patch:
            skipped += 1
            continue

        query = urllib.parse.urlencode({
            "select": "slug",
            "slug": "eq." + slug,
            "status": "eq.draft"
        })

        result = request(
            SUPABASE + "/rest/v1/jobs?" + query,
            method="PATCH",
            data=patch,
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
        )

        if result:
            updated += len(result)
        else:
            unchanged += 1

        if index % 25 == 0 or index == len(matched):
            print(
                f"Update Supabase: {index}/{len(matched)} | "
                f"Berhasil: {updated}",
                flush=True
            )

    print("--------------------------------", flush=True)
    print("HASIL BACKFILL KARIRHUB", flush=True)
    print("Total draft ditemukan :", len(targets), flush=True)
    print("Cocok dengan API       :", len(matched), flush=True)
    print("Berhasil diperbarui    :", updated, flush=True)
    print("Data tanpa perubahan   :", skipped, flush=True)
    print("Tidak ter-update       :", unchanged, flush=True)
    print("Belum ditemukan        :", len(targets) - len(matched), flush=True)
    print("Status published       : TIDAK DIUBAH", flush=True)
    print(
        "Waktu proses           : "
        f"{round(time.time() - started, 2)} detik",
        flush=True
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("BACKFILL GAGAL:", error, flush=True)
        raise
