import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any
from automation.ai_company.core.config import DATA_DIR
from automation.ai_company.core.database import local_db
from automation.ai_company.agents.manager import ai_manager

LOCK_FILE = DATA_DIR / "ai_scheduler.lock"

class AutomationCenter:
    """Pusat Otomatisasi & Penjadwalan AI Company."""

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
