import re
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from automation.ai_company.core.database import local_db

SUSPICIOUS_KEYWORDS = [
    "biaya admin", "transfer uang", "uang pendaftaran", "beli tiket", "travel agent",
    "ganti ongkos", "deposit", "uang jaminan", "interview hotel", "hubungi wa admin",
    "tanpa tes langsung kerja", "gaji harian tanpa syarat", "like subscribe youtube"
]

APPROVED_PLATFORMS = {
    'kemnaker.go.id', 'karirhub.kemnaker.go.id', 'jobstreet.co.id', 'jobstreet.com',
    'id.jobstreet.com', 'glints.com', 'kalibrr.com', 'kalibrr.id', 'toploker.com',
    'hiredtoday.com', 'redy.id', 'linkedin.com'
}

class AIVerificationAgent:
    """Divisi AI Verification: Memeriksa legalitas, anti-fraud, keabsahan domain, dan tanggal batas."""

    def __init__(self):
        self.name = "ai_verification"
        self.role = "Verifikator Integritas & Anti-Fraud"

    def verify_apply_url(self, url: str) -> Tuple[bool, str]:
        if not url:
            return False, "URL pendaftaran kosong"
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False, f"Protokol URL tidak valid: {parsed.scheme}"
            hostname = (parsed.hostname or "").lower()
            if not hostname:
                return False, "Domain URL tidak valid"

            # Check if domain is approved platform or standard valid company domain
            is_approved_platform = any(hostname == p or hostname.endswith("." + p) for p in APPROVED_PLATFORMS)
            if is_approved_platform or ("." in hostname and len(hostname.split(".")[-1]) >= 2):
                return True, "URL pendaftaran valid"
            return False, f"Domain tidak dikenal atau tidak aman: {hostname}"
        except Exception as e:
            return False, f"Format URL bermasalah: {e}"

    def check_fraud_indicators(self, title: str, description: str, company: str) -> Tuple[bool, List[str]]:
        text_corpus = f"{title} {description} {company}".lower()
        found_flags = []
        for kw in SUSPICIOUS_KEYWORDS:
            if kw in text_corpus:
                found_flags.append(kw)

        if found_flags:
            return True, found_flags
        return False, []

    def verify_dates(self, published_epoch: Any, expires_epoch: Any) -> Tuple[bool, str, Optional[str], Optional[str]]:
        now = datetime.now(timezone.utc)
        published_dt = None
        expires_dt = None

        if published_epoch:
            try:
                published_dt = datetime.fromtimestamp(int(published_epoch), timezone.utc)
            except Exception:
                pass

        if expires_epoch:
            try:
                expires_dt = datetime.fromtimestamp(int(expires_epoch), timezone.utc)
            except Exception:
                pass

        if expires_dt and expires_dt <= now:
            return False, f"Lowongan sudah kedaluwarsa sejak {expires_dt.date()}", None, None

        pub_iso = published_dt.isoformat() if published_dt else now.isoformat()
        exp_date = expires_dt.date().isoformat() if expires_dt else None
        return True, "Tanggal valid", pub_iso, exp_date

    def verify_vacancy(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Memverifikasi satu kandidat lowongan pekerjaan."""
        title = candidate.get("title", "")
        company = candidate.get("company_name", "")
        apply_url = candidate.get("platform_link", "")

        # 1. Anti-fraud check
        is_fraud, flags = self.check_fraud_indicators(title, str(candidate.get("skills")), company)
        if is_fraud:
            return {
                "verified": False,
                "reason": f"Terdeteksi indikasi penipuan / kata kunci berisiko: {', '.join(flags)}",
                "candidate": candidate
            }

        # 2. URL verification
        url_valid, url_reason = self.verify_apply_url(apply_url)
        if not url_valid:
            return {
                "verified": False,
                "reason": url_reason,
                "candidate": candidate
            }

        # 3. Dates verification
        date_valid, date_reason, pub_iso, exp_date = self.verify_dates(
            candidate.get("published_at"),
            candidate.get("expires_at")
        )
        if not date_valid:
            return {
                "verified": False,
                "reason": date_reason,
                "candidate": candidate
            }

        # Validated candidate ready for formatting
        return {
            "verified": True,
            "reason": "Lolos seluruh pemeriksaan verifikasi identitas, URL, dan anti-fraud.",
            "published_at": pub_iso,
            "deadline": exp_date,
            "candidate": candidate
        }

    def verify_batch(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        passed = []
        rejected = []
        for c in candidates:
            res = self.verify_vacancy(c)
            if res["verified"]:
                passed.append(res)
            else:
                rejected.append(res)

        local_db.log(
            self.name,
            f"Verifikasi selesai: {len(passed)} lowongan disetujui, {len(rejected)} ditolak."
        )

        return {
            "total_evaluated": len(candidates),
            "passed_count": len(passed),
            "rejected_count": len(rejected),
            "passed": passed,
            "rejected": rejected
        }


ai_verification = AIVerificationAgent()
