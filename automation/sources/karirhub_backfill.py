import ipaddress
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.kemnaker.go.id/karirhub/vacancy/v2/published-industrial-vacancies"
SUPABASE = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
WIB = timezone(timedelta(hours=7))
LIMIT = int(os.environ.get("KARIRHUB_BACKFILL_LIMIT", "20"))
DEFAULT_MAX_PAGES = int(os.environ.get("KARIRHUB_BACKFILL_MAX_PAGES", "140"))

REGION_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "karirhub_regions.json"
)

BLOCKED_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "s.id",
    "cutt.ly",
    "t.co",
    "goo.gl",
    "wa.me",
    "chat.whatsapp.com",
    "t.me",
    "telegram.me",
    "forms.gle",
}


def request(url, method="GET", data=None, extra_headers=None):
    headers = {
        "apikey": KEY,
        "Authorization": "Bearer " + KEY,
    }

    if extra_headers:
        headers.update(extra_headers)

    body = json.dumps(data).encode("utf-8") if data is not None else None

    for attempt in range(1, 6):
        req = urllib.request.Request(
            url, data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read().decode("utf-8")
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


def epoch_wib(value):
    try:
        return datetime.fromtimestamp(int(value), tz=WIB)
    except (TypeError, ValueError, OSError):
        return None


def positive_int(value):
    try:
        number = int(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def sanitize_https_url(url):
    raw = str(url or "").strip()
    if not raw:
        return None
    try:
        parsed = urllib.parse.urlparse(raw)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or "." not in host:
            return None
        if parsed.username or parsed.password:
            return None
        if host == "localhost" or host.endswith(".local"):
            return None
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return None
        except ValueError:
            pass
        if any(host == dom or host.endswith("." + dom) for dom in BLOCKED_DOMAINS):
            return None
        return parsed.geturl()
    except Exception:
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
            "offset": offset,
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
        "limit": LIMIT,
    })

    return request(
        url,
        extra_headers={"User-Agent": "Mozilla/5.0 (compatible; InfoLokerKitaBackfill/2.0)"},
    )


def make_patch(item, regions):
    patch = {}

    city = str(item.get("city_name") or "").strip()
    province = str(item.get("province_name") or "").strip()

    if not city or not province:
        for value in item.get("locations") or []:
            if not isinstance(value, str):
                continue
            region_id = value.split(":", 1)[1].strip() if value.startswith("city:") else value.strip()
            region = regions.get(region_id)
            if isinstance(region, dict):
                if not city and region.get("city"):
                    city = str(region["city"]).strip()
                if not province and region.get("province"):
                    province = str(region["province"]).strip()
                if city and province:
                    break

    if city:
        patch["location"] = city
        patch["city"] = city
    if province:
        patch["province"] = province

    apply_url = sanitize_https_url(item.get("platform_link"))
    if apply_url:
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

    published_dt = epoch_wib(item.get("published_at"))
    if published_dt:
        patch["published_at"] = published_dt.isoformat()

    expires_dt = epoch_wib(item.get("expires_at"))
    if expires_dt:
        patch["deadline"] = expires_dt.date().isoformat()

    logo = sanitize_https_url(item.get("company_logo_uri"))
    if logo:
        patch["company_logo"] = logo

    if patch:
        patch["updated_at"] = datetime.now(WIB).isoformat()

    return patch


def main():
    if not SUPABASE or not KEY:
        raise RuntimeError("SUPABASE_URL dan SUPABASE_SERVICE_ROLE_KEY wajib diatur.")

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
        "state_key": "eq.karirhub_archive",
    })
    state_rows = request(SUPABASE + "/rest/v1/automation_state?" + state_query)
    archive_next_page = int(state_rows[0].get("last_page") or 1) if state_rows else 1

    env_start = os.environ.get("KARIRHUB_BACKFILL_START_PAGE", "").strip()
    scan_start_page = max(1, int(env_start)) if env_start.isdigit() else max(1, archive_next_page)
    scan_end_page = min(api_last_page, scan_start_page + max(1, DEFAULT_MAX_PAGES) - 1)

    print("Total halaman API:", api_last_page, flush=True)
    print("Rentang halaman backfill:", scan_start_page, "-", scan_end_page, flush=True)

    def collect(items):
        for item in items or []:
            job_id = str(item.get("id") or "").strip()
            slug = "karirhub-" + job_id
            if job_id and slug in targets:
                matched[slug] = item

    last_scanned_page = scan_start_page
    for page in range(scan_start_page, scan_end_page + 1):
        last_scanned_page = page
        print(f"Memproses halaman {page}/{scan_end_page}...", flush=True)

        result = first if page == 1 else fetch_page(page)
        items = result.get("data") or []
        collect(items)

        print(
            f"Halaman {page}: {len(items)} data | "
            f"Cocok: {len(matched)}/{len(targets)}",
            flush=True,
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
            "status": "eq.draft",
        })

        result = request(
            SUPABASE + "/rest/v1/jobs?" + query,
            method="PATCH",
            data=patch,
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )

        if result:
            updated += len(result)
        else:
            unchanged += 1

        if index % 25 == 0 or index == len(matched):
            print(
                f"Update Supabase: {index}/{len(matched)} | "
                f"Berhasil: {updated}",
                flush=True,
            )

    # Simpan posisi halaman terakhir jika state tersedia
    if state_rows:
        next_page = 1 if last_scanned_page >= api_last_page else last_scanned_page + 1
        request(
            SUPABASE + "/rest/v1/automation_state?" + urllib.parse.urlencode({"state_key": "eq.karirhub_archive"}),
            method="PATCH",
            data={"last_page": next_page, "updated_at": datetime.now(WIB).isoformat()},
            extra_headers={"Content-Type": "application/json", "Prefer": "return=minimal"},
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
    print(f"Waktu proses           : {round(time.time() - started, 2)} detik", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("BACKFILL GAGAL:", error, flush=True)
        raise
