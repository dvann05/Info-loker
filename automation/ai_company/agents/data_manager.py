import re
import json
import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Set, Tuple
from automation.ai_company.core.config import WIB_TIMEZONE
from automation.ai_company.core.database import supabase_client, local_db


def _normalize_dedupe_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _quote_postgrest_in(values: List[str]) -> str:
    escaped = [v.replace("\\", "\\\\").replace('"', '\\"') for v in values]
    return ",".join(f'"{v}"' for v in escaped)


class AIDataManagerAgent:
    """Divisi AI Data Manager: Integrasi Supabase, validasi schema ketat, deduplikasi, dan arsip."""

    def __init__(self):
        self.name = "ai_data_manager"
        self.role = "Manajer Database & Integrasi Supabase"

    def format_and_clean_job_record(self, verified_candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Menyesuaikan data mentah kandidat agar persis sesuai schema tabel jobs."""
        raw = verified_candidate.get("candidate", {})
        pub_at = verified_candidate.get("published_at")
        deadline = verified_candidate.get("deadline")
        now_iso = datetime.now(WIB_TIMEZONE).isoformat()

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

        city = str(raw.get("city") or "").strip() or "Lokasi belum dicantumkan"
        province = str(raw.get("province") or "").strip() or "Belum dicantumkan"

        return {
            "slug": raw.get("slug"),
            "title": raw.get("title"),
            "company_name": raw.get("company_name"),
            "company_logo": raw.get("company_logo_uri"),
            "location": city,
            "city": city,
            "province": province,
            "district": None,
            "employment_type": raw.get("job_type") or "Full-time",
            "education": "SMA/SMK / Sederajat",
            "experience": "Terbuka untuk lulusan baru / berpengalaman",
            "salary_min": to_positive_int(raw.get("min_salary")),
            "salary_max": to_positive_int(raw.get("max_salary")),
            "description": "\n\n".join(details),
            "requirements": skills,
            "benefits": "Sesuai ketentuan dan standar remunerasi perusahaan.",
            "source_url": raw.get("source_url") or "https://karirhub.kemnaker.go.id/",
            "apply_url": raw.get("platform_link"),
            "published_at": pub_at,
            "deadline": deadline,
            "updated_at": now_iso,
            "status": "published"
        }

    def _fetch_existing_slugs(self, slugs: List[str], chunk_size: int = 50) -> Set[str]:
        existing: Set[str] = set()
        for idx in range(0, len(slugs), chunk_size):
            chunk = slugs[idx:idx + chunk_size]
            query = urllib.parse.urlencode({
                "select": "slug",
                "slug": f"in.({_quote_postgrest_in(chunk)})",
            })
            rows = supabase_client.query_rows("jobs", query)
            existing.update(r["slug"] for r in rows if r.get("slug"))
        return existing

    def _fetch_active_job_fingerprints(self) -> Set[Tuple[str, str, str]]:
        """Mengambil sidik jari (title, company_name, city) lowongan aktif agar tidak terjadi duplikasi konten."""
        today_wib = datetime.now(WIB_TIMEZONE).date().isoformat()
        fingerprints: Set[Tuple[str, str, str]] = set()
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
            rows = supabase_client.query_rows("jobs", query)
            if not rows:
                break
            for row in rows:
                fp = (
                    _normalize_dedupe_text(row.get("title")),
                    _normalize_dedupe_text(row.get("company_name")),
                    _normalize_dedupe_text(row.get("city")),
                )
                if fp[0] and fp[1]:
                    fingerprints.add(fp)
            if len(rows) < page_size:
                break
            offset += len(rows)

        return fingerprints

    def sync_jobs(self, verified_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Memasukkan lowongan terverifikasi ke Supabase dengan proteksi duplikasi slug & konten."""
        if not verified_candidates:
            return {"inserted": 0, "skipped": 0, "status": "no_data"}

        clean_records = [self.format_and_clean_job_record(c) for c in verified_candidates]

        # 1. Deduplikasi internal dalam batch berdasarkan slug dan sidik jari konten
        deduped_batch: List[Dict[str, Any]] = []
        seen_batch_slugs: Set[str] = set()
        seen_batch_fps: Set[Tuple[str, str, str]] = set()

        for record in clean_records:
            slug = str(record.get("slug") or "").strip()
            if not slug or slug in seen_batch_slugs:
                continue
            fp = (
                _normalize_dedupe_text(record.get("title")),
                _normalize_dedupe_text(record.get("company_name")),
                _normalize_dedupe_text(record.get("city")),
            )
            if fp[0] and fp[1] and fp in seen_batch_fps:
                continue
            seen_batch_slugs.add(slug)
            if fp[0] and fp[1]:
                seen_batch_fps.add(fp)
            deduped_batch.append(record)

        # 2. Cek duplikasi terhadap Supabase (berdasarkan slug & konten aktif)
        slugs = [r["slug"] for r in deduped_batch]
        existing_slugs = self._fetch_existing_slugs(slugs)
        active_fps = self._fetch_active_job_fingerprints()

        to_insert: List[Dict[str, Any]] = []
        for record in deduped_batch:
            if record["slug"] in existing_slugs:
                continue
            fp = (
                _normalize_dedupe_text(record.get("title")),
                _normalize_dedupe_text(record.get("company_name")),
                _normalize_dedupe_text(record.get("city")),
            )
            if fp[0] and fp[1] and fp in active_fps:
                continue
            to_insert.append(record)
            if fp[0] and fp[1]:
                active_fps.add(fp)

        inserted_count = 0
        staged_count = 0
        if to_insert:
            try:
                batch_size = 50
                for idx in range(0, len(to_insert), batch_size):
                    chunk = to_insert[idx:idx + batch_size]
                    supabase_client.insert_rows(
                        "jobs",
                        chunk,
                        ignore_duplicates=True,
                        on_conflict="slug",
                    )
                    inserted_count += len(chunk)
                local_db.log(self.name, f"Berhasil sinkronisasi {inserted_count} lowongan baru ke Supabase.")
            except Exception as e:
                err_str = str(e).lower()
                if "row-level security" in err_str or "401" in err_str or "403" in err_str:
                    local_db.log(
                        self.name,
                        "Supabase RLS aktif: Kunci Anon hanya memiliki hak baca. Menyimpan data ke Staging Lokal.",
                        level="WARN"
                    )
                    now_str = datetime.now(WIB_TIMEZONE).isoformat()
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
            "skipped_existing": len(verified_candidates) - (inserted_count + staged_count)
        }

    def sync_news_article(self, article: Dict[str, Any]) -> bool:
        """Memasukkan artikel berita yang telah disetujui ke tabel news Supabase."""
        slug = str(article.get("slug") or "").strip()
        if not slug:
            return False

        query = urllib.parse.urlencode({"select": "slug", "slug": f"eq.{slug}"})
        existing = supabase_client.query_rows("news", query)
        if existing:
            local_db.log(self.name, f"Artikel [{slug}] sudah ada di Supabase, lewati.", level="WARN")
            return False

        now_iso = datetime.now(WIB_TIMEZONE).isoformat()
        article["status"] = "published"

        record = {
            "slug": slug,
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
            "published_at": article.get("published_at") or now_iso,
            "updated_at": now_iso,
        }

        try:
            supabase_client.insert_rows("news", [record], ignore_duplicates=True, on_conflict="slug")
            local_db.log(self.name, f"Artikel berita berhasil dipublikasikan ke Supabase: [{slug}] {article.get('title')}")
            return True
        except Exception as e:
            err_str = str(e).lower()
            if "row-level security" in err_str or "401" in err_str or "403" in err_str:
                local_db.log(self.name, f"Supabase RLS aktif: Menyimpan artikel [{slug}] ke Staging Lokal.", level="WARN")
                with local_db.get_connection() as conn:
                    conn.execute("""
                    INSERT OR REPLACE INTO staged_news (slug, data_json, status, created_at)
                    VALUES (?, ?, 'staged', ?)
                    """, (slug, json.dumps(record), now_iso))
                    conn.commit()
                return True
            else:
                local_db.log(self.name, f"Gagal insert artikel ke Supabase: {e}", level="ERROR")
                raise

    def cleanup_expired_jobs(self) -> Dict[str, Any]:
        """Mendeteksi dan mengarsipkan semua lowongan yang telah melewati deadline WIB."""
        now_wib = datetime.now(WIB_TIMEZONE)
        today_wib = now_wib.date().isoformat()
        now_iso = now_wib.isoformat()

        expired_jobs: List[Dict[str, Any]] = []
        offset = 0
        page_size = 200

        try:
            while True:
                query = urllib.parse.urlencode({
                    "select": "id,slug,deadline",
                    "status": "eq.published",
                    "deadline": f"lt.{today_wib}",
                    "order": "deadline.asc",
                    "limit": page_size,
                    "offset": offset,
                })
                batch = supabase_client.query_rows("jobs", query)
                if not batch:
                    break
                expired_jobs.extend(batch)
                if len(batch) < page_size:
                    break
                offset += len(batch)

            archived_count = 0
            failed_count = 0
            slugs_to_archive = [str(j["slug"]) for j in expired_jobs if j.get("slug")]

            for idx in range(0, len(slugs_to_archive), 50):
                chunk = slugs_to_archive[idx:idx + 50]
                filter_query = urllib.parse.urlencode({
                    "slug": f"in.({_quote_postgrest_in(chunk)})",
                    "status": "eq.published",
                })
                try:
                    updated_rows = supabase_client.update_rows(
                        "jobs",
                        filter_query,
                        {"status": "archived", "updated_at": now_iso},
                    )
                    archived_count += len(updated_rows) if updated_rows else len(chunk)
                except Exception as patch_err:
                    failed_count += len(chunk)
                    local_db.log(
                        self.name,
                        f"Gagal mengarsipkan batch lowongan kedaluwarsa: {patch_err}",
                        level="WARN",
                    )

            local_db.log(
                self.name,
                f"Pengarsipan kedaluwarsa selesai (WIB {today_wib}): {len(expired_jobs)} teridentifikasi, "
                f"{archived_count} diarsipkan, {failed_count} gagal.",
            )
            return {
                "today_wib": today_wib,
                "expired_count": len(expired_jobs),
                "archived_count": archived_count,
                "failed_count": failed_count,
                "items": expired_jobs[:50],
            }
        except Exception as e:
            local_db.log(self.name, f"Error saat pengarsipan lowongan expired: {e}", level="ERROR")
            return {
                "today_wib": today_wib,
                "expired_count": 0,
                "archived_count": 0,
                "failed_count": 0,
                "items": [],
            }


ai_data_manager = AIDataManagerAgent()
