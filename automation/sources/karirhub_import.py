import ipaddress
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.kemnaker.go.id/karirhub/vacancy/v2/published-industrial-vacancies"
PORTAL = "https://karirhub.kemnaker.go.id/"
SUPABASE = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

WIB = timezone(timedelta(hours=7))
LIMIT = 20
LATEST_PAGES = int(os.environ.get("KARIRHUB_LATEST_PAGES", "20"))
DAILY_IMPORT_LIMIT = int(os.environ.get("KARIRHUB_DAILY_LIMIT", "20"))
BATCH_SIZE = 50
STATE_URL = SUPABASE + "/rest/v1/automation_state"
REGION_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "karirhub_regions.json"
)


def headers(extra=None):
    result = {}
    if KEY:
        result.update({
            "apikey": KEY,
            "Authorization": "Bearer " + KEY,
        })
    if extra:
        result.update(extra)
    return result


def request(url, method="GET", data=None, extra_headers=None):
    payload = json.dumps(data).encode("utf-8") if data is not None else None

    for attempt in range(1, 5):
        req = urllib.request.Request(
            url,
            data=payload,
            headers=headers(extra_headers),
            method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None

        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            print("HTTP ERROR:", error.code)
            print("URL:", url)
            print("DETAIL SERVER:", detail[:1000])

            if error.code not in (408, 425, 429, 500, 502, 503, 504):
                raise

            if attempt == 4:
                raise

        except (TimeoutError, socket.timeout, urllib.error.URLError, ConnectionError) as error:
            print(f"Koneksi gagal ({attempt}/4): {error}")

            if attempt == 4:
                raise

        delay = min(5 * (2 ** (attempt - 1)), 40)
        print(f"Mencoba kembali dalam {delay} detik...")
        time.sleep(delay)

    raise RuntimeError("Request gagal setelah 4 percobaan.")


def epoch_to_wib(value):
    try:
        return datetime.fromtimestamp(int(value), tz=WIB)
    except (TypeError, ValueError, OSError):
        return None


def epoch(value):
    dt = epoch_to_wib(value)
    return dt.isoformat() if dt else None


def clean(value):
    return str(value or "").strip()


def load_regions():
    try:
        with open(REGION_FILE, encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except Exception as error:
        print(f"Peringatan: gagal memuat karirhub_regions.json: {error}")
        return {}


def resolve_location(item, regions):
    city = clean(item.get("city_name"))
    province = clean(item.get("province_name"))

    if not city or not province:
        for entry in item.get("locations") or []:
            if not isinstance(entry, str):
                continue
            region_id = entry.split(":", 1)[1].strip() if entry.startswith("city:") else entry.strip()
            region = regions.get(region_id)
            if isinstance(region, dict):
                if not city and region.get("city"):
                    city = clean(region.get("city"))
                if not province and region.get("province"):
                    province = clean(region.get("province"))
                if city and province:
                    break

    return (
        city or "Lokasi belum dicantumkan",
        province or "Belum dicantumkan",
    )


def _quote_postgrest_in(values):
    escaped = [str(v).replace("\\", "\\\\").replace('"', '\\"') for v in values]
    return ",".join(f'"{v}"' for v in escaped)


# Daftar perusahaan yang disetujui.
APPROVED_COMPANIES = {
    "mattel indonesia": [],
    "musashi auto parts indonesia": [],
    "astra honda motor": [],
    "toyota motor manufacturing indonesia": [],
    "yamaha indonesia motor manufacturing": [],
    "denso indonesia": [],
    "mitsubishi motors krama yudha indonesia": [],
    "hino motors manufacturing indonesia": [],
    "suzuki indomobil motor": [],
    "isuzu astra motor indonesia": [],
    "hyundai motor manufacturing indonesia": [],
    "sgmw motor indonesia": [],
    "kayaba indonesia": [],
    "aisin indonesia automotive": [],
    "astra otoparts": [],
    "federal izumi manufacturing": [],
    "showa indonesia manufacturing": [],
    "nusa keihin indonesia": [],
    "fcc indonesia": [],
    "tokai rubber indonesia": [],
    "indonesia epson industry": [],
    "samsung electronics indonesia": [],
    "lg electronics indonesia": [],
    "panasonic manufacturing indonesia": [],
    "omron manufacturing of indonesia": [],
    "schneider electric indonesia": [],
    "daikin manufacturing indonesia": [],
    "sat nusapersada": [],
    "hartono istana teknologi": [],
    "sharp electronics indonesia": [],
    "indofood sukses makmur": [],
    "indofood cbp sukses makmur": [],
    "mayora indah": [],
    "unilever indonesia": [],
    "nestle indonesia": [],
    "mondelez indonesia": [],
    "coca cola europacific partners indonesia": [],
    "garudafood putra putri jaya": [],
    "wings surya": [],
    "ajinomoto indonesia": [],
    "frisian flag indonesia": [],
    "ultrajaya milk industry": [],
    "nippon indosari corpindo": [],
    "kalbe farma": [],
    "tempo scan pacific": [],
    "chandra asri pacific": [],
    "krakatau steel": [],
    "pupuk indonesia": [],
    "petrokimia gresik": [],
    "semen indonesia": [],
    "indocement tunggal prakarsa": [],
    "pabrik kertas tjiwi kimia": [],
    "fajar surya wisesa": [],
    "pindo deli pulp and paper mills": [],
    "lotte chemical indonesia": [],
    "freeport indonesia": [],
    "aneka tambang": [],
    "bukit asam": [],
    "vale indonesia": [],
    "united tractors": [],
    "kaltim prima coal": [],
    "adaro andalan indonesia": [],
    "pertamina": [],
    "pln": [],
    "medco energi internasional": [],
    "pos indonesia": [],
    "kereta api indonesia": [],
    "pelindo": [],
    "dhl supply chain indonesia": [],
    "linfox logistics indonesia": [],
    "shopee international indonesia": [],
    "spx express": [],
    "sumber alfaria trijaya": [],
    "indomarco prismatama": [],
    "midi utama indonesia": [],
    "niterra mobility indonesia": [],
    "nsk bearings manufacturing indonesia": [],
    "ntn manufacturing indonesia": [],
    "jtekt indonesia": [],
    "robert bosch indonesia": [],
    "schaeffler bearings indonesia": [],
    "bridgestone tire indonesia": [],
    "gajah tunggal": [],
    "multistrada arah sarana": [],
    "goodyear indonesia": [],
    "hankook tire indonesia": [],
    "pako group": [],
    "yutaka manufacturing indonesia": [],
    "astra daihatsu motor": [],
    "nifco indonesia": [],
    "tpr indonesia": [],
    "daido indonesia manufacturing": [],
    "indonesia stanley electric": [],
    "mitsuba indonesia": [],
    "t.rad indonesia": [],
    "panasonic gobel indonesia": [],
    "indonesia thai summit auto": [],
    "jvc electronics indonesia": [],
    "toshiba consumer products indonesia": [],
    "haier electrical appliances indonesia": [],
    "sanken indonesia": [],
    "kawai indonesia": [],
    "yamaha music manufacturing asia": [],
    "volex indonesia": [],
    "monde mahkota biscuit": [],
    "heinz abc indonesia": [],
    "kraft heinz indonesia": [],
    "diamond food indonesia": [],
    "kino indonesia": [],
    "orang tua group": [],
    "siantar top": [],
    "sekar laut": [],
    "campina ice cream industry": [],
    "japfa comfeed indonesia": [],
    "charoen pokphand indonesia": [],
    "malindo feedmill": [],
    "sreeya sewu indonesia": [],
    "santos jaya abadi": [],
    "tirta investama": [],
    "basf indonesia": [],
    "dow indonesia": [],
    "evonik indonesia": [],
    "p&g operations indonesia": [],
    "l'oreal indonesia": [],
    "bayer indonesia": [],
    "otsuka indonesia": [],
    "dexa medica": [],
    "bio farma": [],
    "kimia farma": [],
    "indah kiat pulp and paper": [],
    "app purinusa ekapersada": [],
    "riau andalan pulp and paper": [],
    "asahimas chemical": [],
    "nippon paint indonesia": [],
    "puninar logistics": [],
    "kamadjaja logistics": [],
    "cipta krida bahari": [],
    "jne": [],
    "global jet express": [],
    "yusen logistics indonesia": [],
    "kuehne nagel indonesia": [],
    "maersk indonesia": [],
    "db schenker indonesia": [],
    "nippon express indonesia": [],
    "telkom indonesia": [],
    "indosat": [],
    "xl smart telecom sejahtera": [],
    "bank central asia": [],
    "bank mandiri": [],
    "bank rakyat indonesia": [],
    "bank negara indonesia": [],
    "erajaya swasembada": [],
    "mitra adiperkasa": [],
    "map aktif adiperkasa": [],
}

APPROVED_PLATFORMS = {
    "kemnaker.go.id",
    "karirhub.kemnaker.go.id",
    "hiredtoday.com",
    "toploker.com",
    "redy.id",
    "glints.com",
    "kalibrr.id",
    "kalibrr.com",
    "jobstreet.co.id",
    "jobstreet.com",
    "linkedin.com",
}

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

OFFICIAL_COMPANY_DOMAINS = {
    "mattel indonesia": ["mattel.com"],
    "astra international": ["astra.co.id"],
    "astra honda motor": ["astra-honda.com"],
    "toyota motor manufacturing indonesia": ["toyota.co.id"],
    "yamaha indonesia motor manufacturing": ["yamaha-motor.co.id"],
    "denso indonesia": ["denso.com"],
    "indonesia epson industry": ["epson.co.id"],
    "samsung electronics indonesia": ["samsung.com"],
    "lg electronics indonesia": ["lg.com"],
    "panasonic manufacturing indonesia": ["panasonic.com"],
    "unilever indonesia": ["unilever.co.id"],
    "indofood": ["indofood.com"],
    "indofood sukses makmur": ["indofood.com"],
    "indofood cbp sukses makmur": ["indofoodcbp.com"],
    "mayora indah": ["mayoraindah.co.id"],
    "nestle indonesia": ["nestle.co.id"],
    "kalbe farma": ["kalbe.co.id"],
    "chandra asri pacific": ["chandra-asri.com"],
    "indocement tunggal prakarsa": ["indocement.co.id"],
}


def normalize_company_name(value):
    value = clean(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    words = value.split()

    removable = {"pt", "tbk", "persero", "perseroan"}
    words = [word for word in words if word not in removable]

    return " ".join(words)


def _normalize_dedupe_key(row):
    return (
        re.sub(r"[^a-z0-9]+", "", clean(row.get("title")).lower()),
        re.sub(r"[^a-z0-9]+", "", clean(row.get("company_name")).lower()),
        re.sub(r"[^a-z0-9]+", "", clean(row.get("city")).lower()),
    )


def _is_blocked_or_private_host(host):
    if not host or host == "localhost" or host.endswith(".local") or "." not in host:
        return True
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    except ValueError:
        pass
    return any(host == dom or host.endswith("." + dom) for dom in BLOCKED_DOMAINS)


def sanitize_https_url(url):
    raw = clean(url)
    if not raw:
        return None
    try:
        parsed = urllib.parse.urlparse(raw)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host:
            return None
        if parsed.username or parsed.password:
            return None
        if _is_blocked_or_private_host(host):
            return None
        return parsed.geturl()
    except Exception:
        return None


def approved_official_link(company, url):
    company_name = normalize_company_name(company)

    approved = {
        normalize_company_name(name)
        for name in APPROVED_COMPANIES
    }

    safe_url = sanitize_https_url(url)
    if company_name not in approved or not safe_url:
        return False

    try:
        parsed = urllib.parse.urlparse(safe_url)
        host = (parsed.hostname or "").lower()

        # Periksa domain resmi perusahaan.
        for name, domains in OFFICIAL_COMPANY_DOMAINS.items():
            if normalize_company_name(name) == company_name:
                if any(
                    host == domain or host.endswith("." + domain)
                    for domain in domains
                ):
                    return True

        # Periksa platform rekrutmen yang diizinkan.
        return any(
            host == domain or host.endswith("." + domain)
            for domain in APPROVED_PLATFORMS
        )

    except Exception:
        return False


PRIORITY_COMPANIES = [
    "mattel indonesia",
    "musashi auto parts indonesia",
    "astra honda motor",
    "toyota motor manufacturing indonesia",
    "yamaha indonesia motor manufacturing",
    "astra daihatsu motor",
    "denso indonesia",
    "indonesia epson industry",
    "mitsubishi motors krama yudha indonesia",
    "suzuki indomobil motor",
    "hyundai motor manufacturing indonesia",
    "hino motors manufacturing indonesia",
    "aisin indonesia automotive",
    "astra otoparts",
    "bridgestone tire indonesia",
    "gajah tunggal",
    "samsung electronics indonesia",
    "lg electronics indonesia",
    "panasonic manufacturing indonesia",
    "omron manufacturing of indonesia",
    "schneider electric indonesia",
    "unilever indonesia",
    "indofood sukses makmur",
    "mayora indah",
    "nestle indonesia",
    "charoen pokphand indonesia",
    "japfa comfeed indonesia",
    "kalbe farma",
    "chandra asri pacific",
    "krakatau steel",
    "freeport indonesia",
    "pertamina",
    "pupuk indonesia",
    "indocement tunggal prakarsa",
    "dhl supply chain indonesia",
    "sumber alfaria trijaya",
    "indomarco prismatama",
]


def priority_rank(company):
    normalized = normalize_company_name(company)
    for index, name in enumerate(PRIORITY_COMPANIES):
        if normalized == normalize_company_name(name):
            return index
    return len(PRIORITY_COMPANIES)


def fetch_page(page):
    url = API + "?" + urllib.parse.urlencode({
        "page": page,
        "limit": LIMIT,
    })
    result = request(
        url,
        extra_headers={"User-Agent": "Mozilla/5.0 (compatible; InfoLokerKitaImporter/2.0)"},
    )
    time.sleep(0.2)
    return result


def convert(item, now, regions=None):
    title = clean(item.get("title"))
    company = clean(item.get("company_name"))
    job_id = clean(item.get("id"))

    if not title or not company or not job_id:
        return None

    apply_url = sanitize_https_url(item.get("platform_link"))
    if not apply_url or not approved_official_link(company, apply_url):
        return None

    if title.lower() in ("ok", "test", "testing"):
        return None
    if item.get("canceled") or item.get("rejected"):
        return None

    published_dt = epoch_to_wib(item.get("published_at"))
    expires_dt = epoch_to_wib(item.get("expires_at"))

    if not published_dt or not expires_dt:
        return None

    now_wib = now.astimezone(WIB)
    if published_dt > now_wib:
        return None

    if expires_dt <= now_wib:
        return None

    published = published_dt.isoformat()
    deadline = expires_dt.date().isoformat()
    city, province = resolve_location(item, regions or {})

    skills = item.get("skills") or []
    if not isinstance(skills, list):
        skills = []
    skills = [clean(x) for x in skills if clean(x)]

    details = [
        "Ringkasan lowongan berdasarkan data publik Karirhub Kemnaker.",
        "Periksa tautan melamar untuk informasi tugas dan persyaratan lengkap.",
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

    def make_job_slug(job_title, company_name, raw_id):
        text = f"{job_title} {company_name}".lower()
        text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
        return f"{text}-{raw_id}"

    def positive_amount(value):
        try:
            amount = int(value)
            return amount if amount > 0 else None
        except (TypeError, ValueError):
            return None

    return {
        "slug": make_job_slug(title, company, job_id),
        "title": title,
        "company_name": company,
        "company_logo": sanitize_https_url(item.get("company_logo_uri")),
        "location": city,
        "city": city,
        "province": province,
        "district": None,
        "employment_type": clean(item.get("job_type_name")) or "Tidak dicantumkan",
        "description": "\n\n".join(details),
        "requirements": skills,
        "salary_min": positive_amount(item.get("min_salary_amount")),
        "salary_max": positive_amount(item.get("max_salary_amount")),
        "source_url": PORTAL,
        "apply_url": apply_url,
        "published_at": published,
        "deadline": deadline,
        "updated_at": now_wib.isoformat(),
        "status": "published",
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
        "state_key": "eq.karirhub_archive",
    })
    request(
        STATE_URL + "?" + query,
        method="PATCH",
        data={
            "last_page": page,
            "updated_at": datetime.now(WIB).isoformat(),
        },
        extra_headers={
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )


def archive_expired_jobs(now):
    """Mengarsipkan lowongan berstatus published yang sudah melewati deadline WIB."""
    now_wib = now.astimezone(WIB)
    today_wib = now_wib.date().isoformat()
    query = urllib.parse.urlencode({
        "status": "eq.published",
        "deadline": f"lt.{today_wib}",
    })
    result = request(
        SUPABASE + "/rest/v1/jobs?" + query,
        method="PATCH",
        data={
            "status": "expired",
            "updated_at": now_wib.isoformat(),
        },
        extra_headers={
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )
    return len(result) if isinstance(result, list) else 0


def _fetch_existing_by_slugs(slugs):
    known = {}
    for idx in range(0, len(slugs), BATCH_SIZE):
        chunk = slugs[idx:idx + BATCH_SIZE]
        query = urllib.parse.urlencode({
            "select": "slug,status,deadline,location,province,apply_url,salary_min,salary_max",
            "slug": f"in.({_quote_postgrest_in(chunk)})",
        })
        existing = request(SUPABASE + "/rest/v1/jobs?" + query) or []
        for row in existing:
            if row.get("slug"):
                known[row["slug"]] = row
    return known


def _fetch_active_fingerprints(today_wib):
    fingerprints = set()
    offset = 0
    page_size = 1000
    while True:
        query = urllib.parse.urlencode({
            "select": "title,company_name,city",
            "status": "eq.published",
            "deadline": f"gte.{today_wib}",
            "limit": page_size,
            "offset": offset,
        })
        rows = request(SUPABASE + "/rest/v1/jobs?" + query) or []
        for row in rows:
            fp = _normalize_dedupe_key(row)
            if fp[0] and fp[1]:
                fingerprints.add(fp)
        if len(rows) < page_size:
            break
        offset += len(rows)
    return fingerprints


def import_rows(rows):
    if not rows:
        return 0, 0, 0

    now_wib = datetime.now(WIB)
    now_iso = now_wib.isoformat()
    today_wib = now_wib.date().isoformat()

    # Deduplikasi internal berdasarkan slug dan (title, company_name, city)
    deduped = []
    seen_slugs = set()
    seen_fps = set()
    for row in rows:
        slug = row["slug"]
        fp = _normalize_dedupe_key(row)
        if slug in seen_slugs or (fp[0] and fp[1] and fp in seen_fps):
            continue
        seen_slugs.add(slug)
        if fp[0] and fp[1]:
            seen_fps.add(fp)
        row["updated_at"] = now_iso
        deduped.append(row)

    slugs = [row["slug"] for row in deduped]
    known = _fetch_existing_by_slugs(slugs)
    active_fps = _fetch_active_fingerprints(today_wib)

    to_insert = []
    to_update = []

    for row in deduped:
        slug = row["slug"]
        existing = known.get(slug)
        if existing is None:
            fp = _normalize_dedupe_key(row)
            if fp[0] and fp[1] and fp in active_fps:
                continue
            to_insert.append(row)
            if fp[0] and fp[1]:
                active_fps.add(fp)
        elif existing.get("status") == "published":
            changed = any(
                existing.get(field) != row.get(field)
                for field in ("deadline", "location", "province", "apply_url", "salary_min", "salary_max")
            )
            if changed:
                to_update.append(row)

    inserted = 0
    for idx in range(0, len(to_insert), BATCH_SIZE):
        chunk = to_insert[idx:idx + BATCH_SIZE]
        request(
            SUPABASE + "/rest/v1/jobs?on_conflict=slug",
            method="POST",
            data=chunk,
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "resolution=ignore-duplicates,return=minimal",
            },
        )
        inserted += len(chunk)

    updated = 0
    for row in to_update:
        query = urllib.parse.urlencode({
            "slug": "eq." + row["slug"],
            "status": "eq.published",
        })
        patch_data = {
            "location": row["location"],
            "city": row["city"],
            "province": row["province"],
            "apply_url": row["apply_url"],
            "deadline": row["deadline"],
            "salary_min": row["salary_min"],
            "salary_max": row["salary_max"],
            "company_logo": row["company_logo"],
            "updated_at": now_iso,
        }
        request(
            SUPABASE + "/rest/v1/jobs?" + query,
            method="PATCH",
            data=patch_data,
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )
        updated += 1

    return len(known), inserted, updated


def main():
    if not SUPABASE or not KEY:
        raise RuntimeError("SUPABASE_URL dan SUPABASE_SERVICE_ROLE_KEY wajib diatur.")

    now = datetime.now(WIB)
    regions = load_regions()

    print("MENGARSIPKAN LOWONGAN KEDALUWARSA (WIB)...")
    archived = archive_expired_jobs(now)
    print("Diarsipkan     :", archived)

    print("MENGAMBIL DATA KARIRHUB KEMNAKER")

    first = fetch_page(1)
    meta = first.get("meta") or {}
    last_page = int(meta.get("last_page") or 1)

    items = list(first.get("data") or [])
    print(f"Halaman 1: {len(items)} data")

    max_page = min(LATEST_PAGES, last_page)

    for page in range(2, max_page + 1):
        try:
            result = fetch_page(page)
        except Exception as error:
            print(f"Halaman {page} gagal: {error}")
            print("Menghentikan pengambilan halaman agar data yang sudah didapat tetap bisa diproses.")
            break

        page_items = result.get("data") or []
        if not page_items:
            break

        items.extend(page_items)
        print(f"Halaman {page}: {len(page_items)} data")

    valid_rows = []

    for item in items:
        try:
            row = convert(item, now, regions=regions)
            if row:
                valid_rows.append(row)
        except Exception as error:
            print("Data dilewati:", error)

    # Prioritaskan perusahaan prioritas, lalu tanggal publikasi TERBARU terlebih dahulu
    def _sort_key(row):
        pub_ts = 0.0
        try:
            pub_ts = datetime.fromisoformat(row.get("published_at", "")).timestamp()
        except Exception:
            pub_ts = 0.0
        return (priority_rank(row.get("company_name", "")), -pub_ts)

    valid_rows.sort(key=_sort_key)
    valid_rows = valid_rows[:DAILY_IMPORT_LIMIT]

    print()
    print("========== IMPORT KARIRHUB ==========")
    print("Data diperiksa :", len(items))
    print("Lolos filter   :", len(valid_rows))
    print("Batas harian   :", DAILY_IMPORT_LIMIT)
    print()

    for i, row in enumerate(valid_rows, 1):
        print(f"{i}. {row['company_name']} - {row['title']} ({row['city']}, {row['province']})")

    if not valid_rows:
        print("Tidak ada lowongan yang lolos filter.")
        return

    print()
    print("MENYIMPAN KE SUPABASE...")

    existing, inserted, updated = import_rows(valid_rows)

    print()
    print("========== HASIL IMPORT ==========")
    print("Diarsipkan     :", archived)
    print("Sudah tersedia :", existing)
    print("Berhasil masuk :", inserted)
    print("Diperbarui     :", updated)
    print("Total diproses :", len(valid_rows))
    print("IMPORT SELESAI")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("IMPORT GAGAL:", error)
        raise
