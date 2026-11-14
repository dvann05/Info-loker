import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, List
from automation.ai_company.core.database import supabase_client, local_db
from automation.ai_company.core.config import PROJECT_ROOT

class AIAuditorAgent:
    """Divisi AI Auditor: Pemeriksaan 404 URL, link expired, gambar mati, dan integritas sistem."""

    def __init__(self):
        self.name = "ai_auditor"
        self.role = "Auditor Sistem & Kualitas Data"

    def check_url_health(self, url: str) -> bool:
        """Memeriksa apakah URL eksternal atau internal merespons dengan status HTTP < 400."""
        if not url or not url.startswith("http"):
            return False
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) InfoLokerAuditor/1.0"},
                method="HEAD"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status < 400
        except urllib.error.HTTPError as e:
            # Some platforms return 403 or 405 for HEAD, try GET with byte range
            if e.code in (403, 405):
                return True
            return False
        except Exception:
            return False

    def audit_jobs_database(self, sample_limit: int = 20) -> Dict[str, Any]:
        """Pemeriksaan kesehatan data lowongan: duplikasi, expired, field kosong."""
        jobs = supabase_client.query_rows(
            "jobs",
            f"select=id,slug,title,company_name,deadline,apply_url,status&limit={sample_limit}&order=created_at.desc"
        )
        today = datetime.now(timezone.utc).date().isoformat()

        expired = []
        missing_apply_url = []
        seen_slugs = set()
        duplicates = []

        for j in jobs:
            slug = j.get("slug")
            if slug in seen_slugs:
                duplicates.append(slug)
            seen_slugs.add(slug)

            deadline = j.get("deadline")
            if deadline and deadline < today:
                expired.append(slug)

            if not j.get("apply_url"):
                missing_apply_url.append(slug)

        issues_count = len(duplicates) + len(expired) + len(missing_apply_url)
        return {
            "sample_size": len(jobs),
            "duplicates_found": len(duplicates),
            "expired_found": len(expired),
            "missing_apply_url": len(missing_apply_url),
            "healthy": issues_count == 0,
            "details": {
                "duplicates": duplicates,
                "expired": expired,
                "missing_apply_url": missing_apply_url
            }
        }

    def audit_news_database(self, sample_limit: int = 15) -> Dict[str, Any]:
        """Pemeriksaan kesehatan berita: gambar hilang, konten terlalu pendek."""
        news_items = supabase_client.query_rows(
            "news",
            f"select=id,slug,title,image_url,content,status&limit={sample_limit}&order=created_at.desc"
        )

        broken_images = []
        short_articles = []

        for n in news_items:
            slug = n.get("slug")
            img = n.get("image_url") or ""
            content = n.get("content") or ""

            # Check if internal image file actually exists
            if img.startswith("/images/berita/"):
                img_path = PROJECT_ROOT / "public" / img.lstrip("/")
                if not img_path.exists():
                    broken_images.append(slug)

            # Check content length
            if len(content) < 200:
                short_articles.append(slug)

        return {
            "sample_size": len(news_items),
            "broken_images": len(broken_images),
            "short_articles": len(short_articles),
            "healthy": (len(broken_images) + len(short_articles)) == 0,
            "details": {
                "broken_images": broken_images,
                "short_articles": short_articles
            }
        }

    def run_full_audit(self) -> Dict[str, Any]:
        """Menjalankan audit sistem secara menyeluruh dan mencatat temuan."""
        local_db.log(self.name, "Memulai pemeriksaan audit kesehatan sistem menyeluruh...")
        start_time = datetime.now(timezone.utc)

        jobs_audit = self.audit_jobs_database(sample_limit=25)
        news_audit = self.audit_news_database(sample_limit=20)

        # Audit error logs in local DB
        with local_db.get_connection() as conn:
            err_rows = conn.execute("""
            SELECT count(*) as count FROM ai_logs 
            WHERE level = 'ERROR' AND created_at >= datetime('now', '-24 hours')
            """).fetchone()
            errors_last_24h = err_rows["count"] if err_rows else 0

        overall_healthy = jobs_audit["healthy"] and news_audit["healthy"] and (errors_last_24h < 5)

        summary = f"Audit selesai. Status: {'SEHAT' if overall_healthy else 'PERHATIAN DIPERLUKAN'}. "
        summary += f"Loker sample: {jobs_audit['sample_size']} ({jobs_audit['expired_found']} expired), "
        summary += f"Berita sample: {news_audit['sample_size']} ({news_audit['broken_images']} gambar bermasalah), "
        summary += f"Error 24 jam terakhir: {errors_last_24h}."

        local_db.log(self.name, summary, level="INFO" if overall_healthy else "WARN")

        return {
            "timestamp": start_time.isoformat(),
            "overall_healthy": overall_healthy,
            "summary": summary,
            "errors_last_24h": errors_last_24h,
            "jobs_audit": jobs_audit,
            "news_audit": news_audit
        }


ai_auditor = AIAuditorAgent()
