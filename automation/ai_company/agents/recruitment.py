import re
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from automation.ai_company.core.database import supabase_client, local_db
from automation.ai_company.core.task_queue import task_queue

API_KARIRHUB = "https://api.kemnaker.go.id/karirhub/vacancy/v2/published-industrial-vacancies"

class AIRecruitmentAgent:
    """Divisi AI Recruitment: Mencari lowongan terpercaya dari Karirhub dan sumber resmi."""

    def __init__(self):
        self.name = "ai_recruitment"
        self.role = "Spesialis Rekrutmen & Kurasi Loker"

    def fetch_karirhub_page(self, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{API_KARIRHUB}?page={page}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 InfoLoker/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("data") or []
        except Exception as e:
            local_db.log(self.name, f"Gagal mengambil data Karirhub hal {page}: {e}", level="WARN")
            return []

    def get_existing_records(self) -> Tuple[set, set]:
        """Mengambil slug dan pasangan (judul, perusahaan) yang sudah ada di database untuk mencegah duplikasi konten."""
        try:
            rows = supabase_client.query_rows("jobs", "select=slug,title,company_name&limit=500&order=created_at.desc")
            slugs = {r["slug"] for r in rows if "slug" in r}
            pairs = {
                (re.sub(r"[^a-z0-9]", "", str(r.get("title", "")).lower()), 
                 re.sub(r"[^a-z0-9]", "", str(r.get("company_name", "")).lower()))
                for r in rows if r.get("title") and r.get("company_name")
            }
            return slugs, pairs
        except Exception as e:
            local_db.log(self.name, f"Gagal memuat data eksisting: {e}", level="WARN")
            return set(), set()

    def discover_vacancies(self, target_count: int = 20, max_pages: int = 5) -> Dict[str, Any]:
        """Menjalankan proses pencarian lowongan kerja terpercaya."""
        start_time = time.time()
        local_db.log(self.name, f"Memulai pencarian lowongan kerja (target: {target_count})...")

        existing_slugs, existing_pairs = self.get_existing_records()
        discovered = []
        skipped_duplicate = 0
        pages_checked = 0
        company_batch_counts = {}

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

                # Generate slug preview
                raw_slug = f"{title}-{company}".lower()
                clean_slug = re.sub(r"[^a-z0-9]+", "-", raw_slug).strip("-") + f"-{job_id}"

                if clean_slug in existing_slugs:
                    skipped_duplicate += 1
                    continue

                # Tandai sudah ada agar tidak masuk berulang kali
                company_batch_counts[norm_company] = company_batch_counts.get(norm_company, 0) + 1
                existing_pairs.add(pair_key)
                existing_slugs.add(clean_slug)

                discovered.append({
                    "raw_id": job_id,
                    "title": title,
                    "company_name": company,
                    "company_logo_uri": item.get("company_logo_uri"),
                    "city": item.get("city_name") or "Lokasi belum dicantumkan",
                    "province": item.get("province_name") or "Belum dicantumkan",
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
                    "slug": clean_slug
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
            "candidates": discovered
        }


ai_recruitment = AIRecruitmentAgent()
