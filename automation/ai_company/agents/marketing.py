from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from automation.ai_company.core.database import local_db
from automation.ai_company.core.llm import llm_engine

class AIMarketingAgent:
    """Divisi AI Marketing: Pembuatan copy promosi media sosial dan penjadwalan konten."""

    def __init__(self):
        self.name = "ai_marketing"
        self.role = "Strategis Pemasaran & Media Sosial"

    def generate_job_promo_copy(self, job: Dict[str, Any], platform: str = "facebook") -> str:
        """Membuat salinan promosi lowongan kerja yang menarik dan persuasif."""
        title = job.get("title", "Lowongan Kerja")
        company = job.get("company_name", "Perusahaan")
        location = job.get("location", "Indonesia")
        slug = job.get("slug", "")
        url = f"https://infolokerkita.web.id/lowongan/detail/?slug={slug}"

        if platform == "facebook":
            return f"""🚨 LOWONGAN KERJA TERBARU: {title.upper()}
🏢 Perusahaan: {company}
📍 Lokasi Penempatan: {location}

Info Loker Kita merilis pembukaan pendaftaran resmi untuk posisi {title}. Kesempatan terbuka bagi Anda yang memenuhi kualifikasi!

ℹ️ Rincian persyaratan lengkap, rentang gaji, dan tautan pendaftaran resmi:
👉 {url}

⚠️ PENTING: Proses rekrutmen ini tidak dipungut biaya apapun (GRATIS). Hati-hati terhadap segala modus penipuan.
Bagikan informasi ini kepada keluarga atau kerabat yang sedang membutuhkan pekerjaan!

#LowonganKerja #LokerTerbaru #InfoLoker #{location.replace(' ', '')} #LokerPabrik"""

        elif platform == "telegram" or platform == "whatsapp":
            return f"""📢 *INFO LOWONGAN RESMI*
*Posisi:* {title}
*Perusahaan:* {company}
*Penempatan:* {location}

🔗 *Link Pendaftaran Resmi:*
{url}

_Catatan: Tidak ada pungutan biaya apapun. Silakan dibagikan._"""

        else: # LinkedIn
            return f"""Peluang karir terbaru untuk posisi {title} di {company} ({location}).

Bagi rekan-rekan profesional atau talenta muda yang memenuhi kualifikasi dan tertarik mengembangkan karir, informasi lengkap kualifikasi dan pendaftaran dapat diakses melalui:
{url}

#Hiring #CareerOpportunity #Recruitment #Indonesia #InfoLokerKita"""

    def generate_news_promo_copy(self, article: Dict[str, Any]) -> str:
        """Membuat salinan promosi berita industri ketenagakerjaan."""
        title = article.get("title", "")
        slug = article.get("slug", "")
        url = f"https://infolokerkita.web.id/berita/{slug}/"

        return f"""📰 UPDATE DUNIA KERJA: {title}

Simak analisis dan perkembangan terbaru sektor industri di Indonesia serta dampaknya bagi peluang penyerapan tenaga kerja.

Baca selengkapnya di portal InfoLokerKita:
👉 {url}

#BeritaIndustri #DuniaKerja #InfoLokerKita #EkonomiIndonesia"""

    def create_daily_content_calendar(self, jobs: List[Dict[str, Any]], news: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Menyusun kalender promosi harian untuk disetujui CEO."""
        calendar = []
        now = datetime.now(timezone.utc)

        # Slot 1: Pagi (08:30 WIB) - Headline Loker
        if jobs:
            top_job = jobs[0]
            copy_fb = self.generate_job_promo_copy(top_job, "facebook")
            calendar.append({
                "target_platform": "Facebook Group & Fanpage",
                "content_type": "Job Promotion",
                "title": f"Loker {top_job.get('title')}",
                "copy_text": copy_fb,
                "scheduled_for": (now + timedelta(hours=1)).isoformat()
            })

        # Slot 2: Siang (12:30 WIB) - Berita Industri / Tips
        if news:
            top_news = news[0]
            copy_news = self.generate_news_promo_copy(top_news)
            calendar.append({
                "target_platform": "Facebook & Telegram",
                "content_type": "News & Industry Update",
                "title": f"Berita: {top_news.get('title')}",
                "copy_text": copy_news,
                "scheduled_for": (now + timedelta(hours=5)).isoformat()
            })

        # Slot 3: Sore (17:30 WIB) - Roundup Loker
        if len(jobs) > 1:
            second_job = jobs[1]
            copy_wa = self.generate_job_promo_copy(second_job, "whatsapp")
            calendar.append({
                "target_platform": "WhatsApp Channel / Broadcast",
                "content_type": "Job Broadcast",
                "title": f"Loker {second_job.get('title')}",
                "copy_text": copy_wa,
                "scheduled_for": (now + timedelta(hours=10)).isoformat()
            })

        # Simpan ke tabel marketing_calendar di local_db
        with local_db.get_connection() as conn:
            cursor = conn.cursor()
            for item in calendar:
                cursor.execute("""
                INSERT INTO marketing_calendar (target_platform, content_type, title, copy_text, status, scheduled_for, created_at)
                VALUES (?, ?, ?, ?, 'draft', ?, datetime('now'))
                """, (item["target_platform"], item["content_type"], item["title"], item["copy_text"], item["scheduled_for"]))
            conn.commit()

        local_db.log(self.name, f"Kalender konten harian berhasil dibuat ({len(calendar)} slot materi promosi).")
        return calendar


ai_marketing = AIMarketingAgent()
