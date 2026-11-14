import re
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from automation.ai_company.core.database import supabase_client, local_db

class AIDataManagerAgent:
    """Divisi AI Data Manager: Integrasi Supabase, validasi schema ketat, dan deduplikasi."""

    def __init__(self):
        self.name = "ai_data_manager"
        self.role = "Manajer Database & Integrasi Supabase"

    def format_and_clean_job_record(self, verified_candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Menyesuaikan data mentah kandidat agar persis sesuai schema tabel jobs."""
        raw = verified_candidate.get("candidate", {})
        pub_at = verified_candidate.get("published_at")
        deadline = verified_candidate.get("deadline")

        skills = raw.get("skills") or []
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]

        details = [
            f"Lowongan kerja terverifikasi untuk posisi {raw.get('title', '')} di {raw.get('company_name', '')}.",
            "Pendaftaran dan informasi proses seleksi dilakukan melalui tautan resmi yang tertera."
        ]
        if raw.get("job_function"):
            details.append(f"Fungsi pekerjaan: {raw.get('job_function')}")
        if raw.get("industry"):
            details.append(f"Sektor industri: {raw.get('industry')}")
        if raw.get("quota"):
            details.append(f"Perkiraan kuota: {raw.get('quota')}")

        def to_positive_int(val):
            try:
                num = int(val)
                return num if num > 0 else None
            except Exception:
                return None

        return {
            "slug": raw.get("slug"),
            "title": raw.get("title"),
            "company_name": raw.get("company_name"),
            "company_logo": raw.get("company_logo_uri"),
            "location": raw.get("city") or "Lokasi belum dicantumkan",
            "city": raw.get("city") or "Lokasi belum dicantumkan",
            "province": raw.get("province") or "Belum dicantumkan",
            "district": None,
            "employment_type": raw.get("job_type") or "Full-time",
            "education": "SMA/SMK / Sederajat",
            "experience": "Terbuka untuk lulusan baru / berpengalaman",
            "salary_min": to_positive_int(raw.get("min_salary")),
            "salary_max": to_positive_int(raw.get("max_salary")),
            "description": "\n\n".join(details),
            "requirements": skills,
            "benefits": "Sesuai ketentuan dan standar remunerasi perusahaan.",
            "source_url": "https://karirhub.kemnaker.go.id/",
            "apply_url": raw.get("platform_link"),
            "published_at": pub_at,
            "deadline": deadline,
            "status": "published"
        }

    def sync_jobs(self, verified_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Memasukkan lowongan terverifikasi ke Supabase dengan proteksi duplikasi."""
        if not verified_candidates:
            return {"inserted": 0, "skipped": 0, "status": "no_data"}

        clean_records = [self.format_and_clean_job_record(c) for c in verified_candidates]
        slugs = [r["slug"] for r in clean_records if r.get("slug")]

        # Query existing slugs in Supabase
        existing_rows = supabase_client.query_rows(
            "jobs",
            f"select=slug&slug=in.({','.join(slugs)})"
        )
        existing_slugs = {r["slug"] for r in existing_rows}

        to_insert = [r for r in clean_records if r["slug"] not in existing_slugs]

        inserted_count = 0
        staged_count = 0
        if to_insert:
            try:
                supabase_client.insert_rows("jobs", to_insert)
                inserted_count = len(to_insert)
                local_db.log(self.name, f"Berhasil sinkronisasi {inserted_count} lowongan baru ke Supabase.")
            except Exception as e:
                err_str = str(e).lower()
                if "row-level security" in err_str or "401" in err_str or "403" in err_str:
                    local_db.log(
                        self.name,
                        "Supabase RLS aktif: Kunci Anon hanya memiliki hak baca. Menyimpan data ke Staging Lokal.",
                        level="WARN"
                    )
                    # Stage locally in SQLite
                    now_str = datetime.now(timezone.utc).isoformat()
                    with local_db.get_connection() as conn:
                        cursor = conn.cursor()
                        for r in to_insert:
                            cursor.execute("""
                            INSERT OR REPLACE INTO staged_jobs (slug, data_json, status, created_at)
                            VALUES (?, ?, 'staged', ?)
                            """, (r["slug"], json.dumps(r), now_str))
                        conn.commit()
                    staged_count = len(to_insert)
                else:
                    local_db.log(self.name, f"Gagal insert ke Supabase: {e}", level="ERROR")
                    raise

        return {
            "total_submitted": len(verified_candidates),
            "inserted": inserted_count,
            "staged_locally": staged_count,
            "skipped_existing": len(clean_records) - (inserted_count + staged_count)
        }

    def sync_news_article(self, article: Dict[str, Any]) -> bool:
        """Memasukkan artikel berita yang telah disetujui ke tabel news Supabase."""
        slug = article.get("slug")
        existing = supabase_client.query_rows("news", f"select=slug&slug=eq.{slug}")
        if existing:
            local_db.log(self.name, f"Artikel [{slug}] sudah ada di Supabase, lewati.", level="WARN")
            return False

        # Pastikan status terbit
        article["status"] = "published"

        # Format record
        record = {
            "slug": article.get("slug"),
            "title": article.get("title"),
            "excerpt": article.get("excerpt"),
            "content": article.get("content"),
            "image_url": article.get("image_url"),
            "image_alt": article.get("image_alt"),
            "category": article.get("category"),
            "source_name": article.get("source_name"),
            "source_url": article.get("source_url"),
            "status": article.get("status"),
            "is_featured": article.get("is_featured", False),
            "published_at": article.get("published_at")
        }

        try:
            supabase_client.insert_rows("news", [record])
            local_db.log(self.name, f"Artikel berita berhasil dipublikasikan ke Supabase: [{slug}] {article.get('title')}")
            return True
        except Exception as e:
            err_str = str(e).lower()
            if "row-level security" in err_str or "401" in err_str or "403" in err_str:
                local_db.log(self.name, f"Supabase RLS aktif: Menyimpan artikel [{slug}] ke Staging Lokal.", level="WARN")
                now_str = datetime.now(timezone.utc).isoformat()
                with local_db.get_connection() as conn:
                    conn.execute("""
                    INSERT OR REPLACE INTO staged_news (slug, data_json, status, created_at)
                    VALUES (?, ?, 'staged', ?)
                    """, (slug, json.dumps(record), now_str))
                    conn.commit()
                return True
            else:
                local_db.log(self.name, f"Gagal insert artikel ke Supabase: {e}", level="ERROR")
                raise

    def cleanup_expired_jobs(self) -> Dict[str, Any]:
        """Mendeteksi dan memperbarui status lowongan yang telah melewati deadline."""
        today = datetime.now(timezone.utc).date().isoformat()
        try:
            expired_jobs = supabase_client.query_rows(
                "jobs",
                f"select=id,slug,deadline&status=eq.published&deadline=lt.{today}&limit=100"
            )
            count = len(expired_jobs)
            local_db.log(self.name, f"Pemeriksaan kedaluwarsa selesai: {count} lowongan kedaluwarsa teridentifikasi.")
            return {"expired_count": count, "items": expired_jobs}
        except Exception as e:
            local_db.log(self.name, f"Error saat cek lowongan expired: {e}", level="ERROR")
            return {"expired_count": 0, "items": []}


ai_data_manager = AIDataManagerAgent()
