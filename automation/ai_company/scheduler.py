import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any
from automation.ai_company.core.config import DATA_DIR, WIB_TIMEZONE
from automation.ai_company.core.database import local_db, supabase_client
from automation.ai_company.agents.manager import ai_manager

LOCK_FILE = DATA_DIR / "ai_scheduler.lock"
MAX_DAILY_JOBS_RUNS = 1
MAX_DAILY_NEWS_ARTICLES = 3

class AutomationCenter:
    """Pusat Otomatisasi & Penjadwalan AI Company (Mode Hemat Token: hanya jalan di jadwalnya)."""

    @staticmethod
    def _today_wib_date() -> str:
        return datetime.now(WIB_TIMEZONE).date().isoformat()

    @staticmethod
    def _count_today_supabase_news() -> int:
        """Menghitung jumlah berita yang sudah terbit hari ini (WIB) agar tidak melebihi kuota 3x/hari."""
        today_str = datetime.now(WIB_TIMEZONE).date().isoformat()
        try:
            return supabase_client.get_count(
                "news",
                f"status=eq.published&published_at=gte.{today_str}T00:00:00+07:00",
            )
        except Exception:
            return 0

    @staticmethod
    def _count_today_supabase_jobs() -> int:
        """Menghitung jumlah lowongan baru yang di-upload hari ini (WIB) agar maksimal 1x/hari (3-5 loker)."""
        today_str = datetime.now(WIB_TIMEZONE).date().isoformat()
        try:
            return supabase_client.get_count(
                "jobs",
                f"status=eq.published&updated_at=gte.{today_str}T00:00:00+07:00",
            )
        except Exception:
            return 0

    @staticmethod
    def acquire_lock() -> bool:
        """Pencegahan eksekusi ganda (Idempotency Lock)."""
        if LOCK_FILE.exists():
            # Check if lock is stale (older than 30 minutes)
            try:
                mtime = os.path.getmtime(LOCK_FILE)
                if time.time() - mtime > 1800:
                    LOCK_FILE.unlink(missing_ok=True)
                else:
                    return False
            except Exception:
                return False

        try:
            with open(LOCK_FILE, "w") as f:
                f.write(str(os.getpid()))
            return True
        except Exception:
            return False

    @staticmethod
    def release_lock():
        try:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    def run_morning_recruitment_cycle(self) -> Dict[str, Any]:
        """Siklus 05.00 WIB (1x/hari): Recruitment (3-5 loker perusahaan bonafit) -> Verification -> Data Manager."""
        if not self.acquire_lock():
            local_db.log("scheduler", "Eksekusi siklus 05.00 WIB dilewati: Proses lain sedang berjalan.", level="WARN")
            return {"status": "skipped", "reason": "lock_active"}

        try:
            today_jobs = self._count_today_supabase_jobs()
            if today_jobs >= 3:
                local_db.log(
                    "scheduler",
                    f"Hemat Token: Hari ini sudah ada {today_jobs} loker bonafit terbit. Siklus 05.00 WIB dilewati.",
                )
                return {"status": "skipped", "reason": "daily_job_quota_reached", "today_jobs": today_jobs}

            local_db.log("scheduler", "Memulai Siklus Otomatis 05.00 WIB (3-5 Loker Perusahaan Bonafit)...")
            res = ai_manager.run_recruitment_pipeline(target_count=5)
            return res
        finally:
            self.release_lock()

    def run_newsroom_cycle(self, slot_label: str = "Pagi (07.00 WIB)") -> Dict[str, Any]:
        """Siklus Berita Industri (3x/hari: Pagi 07:00, Siang 12:00, Sore 17:00 WIB) — 1 artikel berbobot + SEO."""
        if not self.acquire_lock():
            local_db.log("scheduler", f"Eksekusi siklus berita {slot_label} dilewati: Proses lain sedang berjalan.", level="WARN")
            return {"status": "skipped", "reason": "lock_active"}

        try:
            today_news = self._count_today_supabase_news()
            if today_news >= MAX_DAILY_NEWS_ARTICLES:
                local_db.log(
                    "scheduler",
                    f"Hemat Token: Kuota berita hari ini sudah penuh ({today_news}/{MAX_DAILY_NEWS_ARTICLES}). Slot {slot_label} dilewati.",
                )
                return {"status": "skipped", "reason": "daily_news_quota_reached", "today_news": today_news}

            local_db.log("scheduler", f"Memulai Siklus Berita Industri {slot_label} (1 Artikel SEO Hemat AI)...")
            res = ai_manager.run_newsroom_pipeline(article_count=1)
            return res
        finally:
            self.release_lock()

    def run_morning_newsroom_cycle(self) -> Dict[str, Any]:
        """Alias siklus berita pagi 07.00 WIB."""
        return self.run_newsroom_cycle("Pagi (07.00 WIB)")

    def run_morning_audit_cycle(self) -> Dict[str, Any]:
        """Siklus 08.00 WIB: Auditor -> AI Manager (Laporan Harian CEO)."""
        if not self.acquire_lock():
            local_db.log("scheduler", "Eksekusi siklus 08.00 WIB dilewati: Proses lain sedang berjalan.", level="WARN")
            return {"status": "skipped", "reason": "lock_active"}

        try:
            local_db.log("scheduler", "Memulai Siklus Otomatis 08.00 WIB (Audit Sistem & Laporan Harian)...")
            res = ai_manager.run_daily_audit_and_report()
            return res
        finally:
            self.release_lock()

    def run_full_daily_cycle(self) -> Dict[str, Any]:
        """Menjalankan seluruh siklus harian berurutan."""
        results = {}
        results["recruitment"] = self.run_morning_recruitment_cycle()
        results["newsroom"] = self.run_morning_newsroom_cycle()
        results["audit_and_report"] = self.run_morning_audit_cycle()
        return results


automation_center = AutomationCenter()

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg == "0500":
        automation_center.run_morning_recruitment_cycle()
    elif arg == "0700":
        automation_center.run_morning_newsroom_cycle()
    elif arg == "0800":
        automation_center.run_morning_audit_cycle()
    else:
        automation_center.run_full_daily_cycle()
