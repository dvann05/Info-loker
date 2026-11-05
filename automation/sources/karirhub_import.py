import re
import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

API = "https://api.kemnaker.go.id/karirhub/vacancy/v2/published-industrial-vacancies"
PORTAL = "https://karirhub.kemnaker.go.id/"
SUPABASE = os.environ.get('SUPABASE_URL', '').rstrip('/')
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')


LIMIT = 20
LATEST_PAGES = 20
ARCHIVE_PAGES = 20
STATE_URL = SUPABASE + "/rest/v1/automation_state"


def headers(extra=None):
    result = {}
    if KEY:
        result.update({
            'apikey': KEY,
            'Authorization': 'Bearer ' + KEY
        })
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


# Daftar perusahaan yang disetujui.
# Domain harus sesuai dengan situs resmi perusahaan.
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
    'hiredtoday.com',
    'toploker.com',
    'redy.id',
    'glints.com',
    'kalibrr.id',
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


def approved_official_link(company, url):
    company_name = normalize_company_name(company)

    approved = {
        normalize_company_name(name)
        for name in APPROVED_COMPANIES
    }

    if company_name not in approved or not url:
        return False

    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()

        if parsed.scheme != "https":
            return False

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

    apply_url = clean(item.get("platform_link"))

    if not approved_official_link(company, apply_url):
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

    if not expires:
        return None

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

    def make_job_slug(title, company, job_id):
        text = f"{title} {company}".lower()
        text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
        return f"{text}-{job_id}"

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
        "company_logo": item.get("company_logo_uri"),
        "location": clean(item.get("city_name")) or "Lokasi belum dicantumkan",
        "city": clean(item.get("city_name")) or "Lokasi belum dicantumkan",
        "province": clean(item.get("province_name")) or "Belum dicantumkan",
        "district": None,
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
        "description": "\n\n".join(details),
        "requirements": skills,
        "salary_min": positive_amount(item.get("min_salary_amount")),
        "salary_max": positive_amount(item.get("max_salary_amount")),
        "source_url": PORTAL,
        "apply_url": apply_url,
        "published_at": published,
        "deadline": deadline,
        "status": "published"
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



    return len(known), inserted, updated


def main():
    now = datetime.now(timezone.utc)

    first = fetch_page(1)
    meta = first.get("meta") or {}
    last_page = int(meta.get("last_page") or 1)

    items = list(first.get("data") or [])
    print(f"Halaman 1: {len(items)} data")

    for page in range(2, min(LATEST_PAGES, last_page) + 1):
        result = fetch_page(page)
        page_items = result.get("data") or []
        if not page_items:
            break
        items.extend(page_items)
        print(f"Halaman {page}: {len(page_items)} data")

    valid_rows = []
    for item in items:
        row = convert(item, now)
        if row:
            valid_rows.append(row)

    valid_rows.sort(
        key=lambda row: priority_rank(row.get("company_name", ""))
    )
    valid_rows = valid_rows[:20]

    print()
    print('========== SIMULASI DRY-RUN KARIRHUB ==========')
    print('Data diperiksa :', len(items))
    print('Data lolos filter :', len(valid_rows))
    print('Batas harian : 20 lowongan')
    print('')

    for i, row in enumerate(valid_rows, 1):
        print(f'{i}. {row["company_name"]}')
        print('   Posisi   :', row['title'])
        print('   Lokasi   :', row['location'])
        print('   Deadline :', row['deadline'])
        print('   Lamaran  :', row['apply_url'])
        print('')

    print('SIMULASI SELESAI')
    print('Supabase tidak diubah.')
    print('Tidak ada lowongan yang diterbitkan.')



if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("IMPORT GAGAL:", error)
        raise
