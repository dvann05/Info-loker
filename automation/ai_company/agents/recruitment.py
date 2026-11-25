import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple
from automation.ai_company.core.config import PROJECT_ROOT
from automation.ai_company.core.database import local_db, supabase_client

API_KARIRHUB = "https://api.kemnaker.go.id/karirhub/vacancy/v2/published-industrial-vacancies"
REGION_FILE = PROJECT_ROOT / "automation" / "data" / "karirhub_regions.json"


class AIRecruitmentAgent:
    """Divisi AI Recruitment: Mencari lowongan terpercaya dari Karirhub dan sumber resmi."""

    def __init__(self):
        self.name = "ai_recruitment"
        self.role = "Spesialis Rekrutmen & Kurasi Loker"
        self._regions_cache: Dict[str, Dict[str, str]] = {}

    def _load_regions(self) -> Dict[str, Dict[str, str]]:
        if self._regions_cache:
            return self._regions_cache
        try:
            with open(REGION_FILE, encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    self._regions_cache = data
        except Exception as exc:
            local_db.log(self.name, f"Gagal memuat karirhub_regions.json: {exc}", level="WARN")
        return self._regions_cache

    def _resolve_location(self, item: Dict[str, Any]) -> Tuple[str, str]:
        city = str(item.get("city_name") or "").strip()
        province = str(item.get("province_name") or "").strip()

        if not city or not province:
            regions = self._load_regions()
            for entry in item.get("locations") or []:
                if not isinstance(entry, str):
                    continue
                region_id = entry.split(":", 1)[1].strip() if entry.startswith("city:") else entry.strip()
                region = regions.get(region_id)
                if isinstance(region, dict):
                    if not city and region.get("city"):
                        city = str(region["city"]).strip()
                    if not province and region.get("province"):
                        province = str(region["province"]).strip()
                    if city and province:
                        break

        return (
            city or "Lokasi belum dicantumkan",
            province or "Belum dicantumkan",
        )

    def fetch_karirhub_page(self, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{API_KARIRHUB}?page={page}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 InfoLoker/2.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("data") or []
        except Exception as e:
            local_db.log(self.name, f"Gagal mengambil data Karirhub hal {page}: {e}", level="WARN")
            return []

    def get_existing_records(self) -> Tuple[set, set]:
        """Mengambil seluruh slug dan pasangan (judul, perusahaan) yang sudah ada untuk mencegah duplikasi."""
        slugs = set()
        pairs = set()
        offset = 0
        page_size = 1000

        try:
            while True:
                query = urllib.parse.urlencode({
                    "select": "slug,title,company_name",
                    "order": "created_at.desc",
                    "limit": page_size,
                    "offset": offset,
                })
                rows = supabase_client.query_rows("jobs", query)
                if not rows:
                    break
                for r in rows:
                    if r.get("slug"):
                        slugs.add(r["slug"])
                    if r.get("title") and r.get("company_name"):
                        pairs.add((
                            re.sub(r"[^a-z0-9]", "", str(r["title"]).lower()),
                            re.sub(r"[^a-z0-9]", "", str(r["company_name"]).lower()),
                        ))
                if len(rows) < page_size:
                    break
                offset += len(rows)
            return slugs, pairs
        except Exception as e:
            local_db.log(self.name, f"Gagal memuat data eksisting: {e}", level="WARN")
            return slugs, pairs

    def discover_vacancies(self, target_count: int = 20, max_pages: int = 5) -> Dict[str, Any]:
        """Menjalankan proses pencarian lowongan kerja terpercaya."""
        start_time = time.time()
        local_db.log(self.name, f"Memulai pencarian lowongan kerja (target: {target_count})...")

        existing_slugs, existing_pairs = self.get_existing_records()
        discovered = []
        skipped_duplicate = 0
        pages_checked = 0
        company_batch_counts: Dict[str, int] = {}

        for page in range(1, max_pages + 1):
            pages_checked += 1
            items = self.fetch_karirhub_page(page=page, limit=20)
            if not items:
                break

            for item in items:
                title = str(item.get("title") or "").strip()
                company = str(item.get("company_name") or "").strip()
                job_id = str(item.get("id") or "").strip()

                if not title or not company or not job_id:
                    continue

                norm_title = re.sub(r"[^a-z0-9]", "", title.lower())
                norm_company = re.sub(r"[^a-z0-9]", "", company.lower())
                pair_key = (norm_title, norm_company)

                # 1. Anti-Flood: Maksimal 2 lowongan per perusahaan dalam satu batch
                if company_batch_counts.get(norm_company, 0) >= 2:
                    skipped_duplicate += 1
                    continue

                # 2. Anti-Duplicate: Jika judul dan perusahaan yang sama persis sudah ada di database
                if pair_key in existing_pairs:
                    skipped_duplicate += 1
                    continue

                raw_slug = f"{title}-{company}".lower()
                clean_slug = re.sub(r"[^a-z0-9]+", "-", raw_slug).strip("-") + f"-{job_id}"

                if clean_slug in existing_slugs:
                    skipped_duplicate += 1
                    continue

                city, province = self._resolve_location(item)

                company_batch_counts[norm_company] = company_batch_counts.get(norm_company, 0) + 1
                existing_pairs.add(pair_key)
                existing_slugs.add(clean_slug)

                discovered.append({
                    "raw_id": job_id,
                    "title": title,
                    "company_name": company,
                    "company_logo_uri": item.get("company_logo_uri"),
                    "city": city,
                    "province": province,
                    "job_type": item.get("job_type_name") or "Full-time",
                    "platform_link": item.get("platform_link"),
                    "min_salary": item.get("min_salary_amount"),
                    "max_salary": item.get("max_salary_amount"),
                    "published_at": item.get("published_at"),
                    "expires_at": item.get("expires_at"),
                    "skills": item.get("skills") or [],
                    "job_function": item.get("job_function_name"),
                    "industry": item.get("industry_name"),
                    "quota": item.get("available_quota") or item.get("quota"),
                    "slug": clean_slug,
                })

                if len(discovered) >= target_count:
                    break

            if len(discovered) >= target_count:
                break

        duration = round(time.time() - start_time, 2)
        local_db.log(
            self.name,
            f"Pencarian selesai dalam {duration}s. Ditemukan {len(discovered)} kandidat baru, {skipped_duplicate} duplikat diabaikan."
        )

        return {
            "status": "success",
            "candidates_found": len(discovered),
            "skipped_duplicates": skipped_duplicate,
            "pages_scanned": pages_checked,
            "duration_seconds": duration,
            "candidates": discovered,
        }


ai_recruitment = AIRecruitmentAgent()
