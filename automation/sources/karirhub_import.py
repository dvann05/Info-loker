import os
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

API = "https://api.kemnaker.go.id/karirhub/vacancy/v2/published-industrial-vacancies"
PORTAL = "https://karirhub.kemnaker.go.id/"
SUPABASE = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def request(url, method="GET", data=None, headers=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers or {},
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
        return datetime.fromtimestamp(int(value), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def clean(value):
    return str(value or "").strip()


def main():
    now = datetime.now(timezone.utc)
    candidates = []

    for page in range(1, 21):
        url = API + "?" + urllib.parse.urlencode({
            "page": page,
            "limit": 5
        })
        result = request(url, headers={"User-Agent": "Mozilla/5.0"})
        items = result.get("data", [])

        if not items:
            break

        candidates.extend(items)
        print(f"Halaman {page}: {len(items)} data")

    rows = []

    for item in candidates:
        title = clean(item.get("title"))
        company = clean(item.get("company_name"))
        job_id = clean(item.get("id"))

        if not title or not company or not job_id:
            continue
        if title.lower() in ("ok", "test", "testing"):
            continue
        if item.get("canceled") or item.get("rejected"):
            continue

        published = epoch(item.get("published_at"))
        expires = epoch(item.get("expires_at"))

        if not published:
            continue

        published_dt = datetime.fromisoformat(published)
        if published_dt > now:
            continue

        deadline = None
        if expires:
            expires_dt = datetime.fromisoformat(expires)
            if expires_dt <= now:
                continue
            deadline = expires_dt.date().isoformat()

        skills = item.get("skills") or []
        if not isinstance(skills, list):
            skills = []

        description = (
            "Informasi lowongan ini diperoleh dari data publik "
            "Karirhub Kemnaker. Rincian pekerjaan dan persyaratan "
            "lengkap perlu diperiksa kembali melalui sumber lowongan."
        )

        if skills:
            description += "\n\nKeahlian yang tercantum: " + ", ".join(
                clean(x) for x in skills if clean(x)
            )

        rows.append({
            "slug": "karirhub-" + job_id,
            "title": title,
            "company_name": company,
            "company_logo": item.get("company_logo_uri"),
            "location": clean(item.get("city_name")) or "Indonesia",
            "province": "Indonesia",
            "employment_type": clean(item.get("job_type_name")) or "Tidak dicantumkan",
            "description": description,
            "requirements": [clean(x) for x in skills if clean(x)],
            "source_url": PORTAL,
            "apply_url": None,
            "published_at": published,
            "deadline": deadline,
            "status": "draft"
        })

    if not rows:
        print("Tidak ada data valid untuk diproses.")
        return

    slugs = [row["slug"] for row in rows]
    query = urllib.parse.urlencode({
        "select": "slug",
        "slug": "in.(" + ",".join(slugs) + ")"
    })

    existing = request(
        SUPABASE + "/rest/v1/jobs?" + query,
        headers={
            "apikey": KEY,
            "Authorization": "Bearer " + KEY
        }
    )

    known = {row["slug"] for row in existing or []}
    new_rows = [row for row in rows if row["slug"] not in known]

    if new_rows:
        request(
            SUPABASE + "/rest/v1/jobs",
            method="POST",
            data=new_rows,
            headers={
                "apikey": KEY,
                "Authorization": "Bearer " + KEY,
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
        )

    print("Data diperiksa :", len(candidates))
    print("Data valid     :", len(rows))
    print("Sudah ada      :", len(known))
    print("Data baru      :", len(new_rows))
    print("Status baru    : draft")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("IMPORT GAGAL:", error)
        raise
