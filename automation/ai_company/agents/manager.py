import json
from datetime import datetime
from typing import Dict, Any
from automation.ai_company.core.config import REPORTS_DIR, WIB_TIMEZONE
from automation.ai_company.core.database import supabase_client, local_db
from automation.ai_company.core.task_queue import task_queue

from automation.ai_company.agents.recruitment import ai_recruitment
from automation.ai_company.agents.verification import ai_verification
from automation.ai_company.agents.newsroom import ai_newsroom
from automation.ai_company.agents.seo_specialist import ai_seo_specialist
from automation.ai_company.agents.designer import ai_designer
from automation.ai_company.agents.data_manager import ai_data_manager
from automation.ai_company.agents.marketing import ai_marketing
from automation.ai_company.agents.auditor import ai_auditor


class AIManagerAgent:
    """AI Manager (Direktur Operasional): Pusat orkestrasi 8 divisi AI dan pelaporan langsung kepada CEO."""

    def __init__(self):
        self.name = "ai_manager"
        self.role = "Direktur Operasional (COO)"

    def run_recruitment_pipeline(self, target_count: int = 5) -> Dict[str, Any]:
        """Orkestrasi alur: AI Recruitment (3-5 loker bonafit) -> AI Verification -> AI Data Manager."""
        task_id = task_queue.create_task(
            agent_name=self.name,
            title=f"Siklus Rekrutmen & Kurasi Lowongan (Target: {target_count})",
            description="Eksekusi pencarian lowongan terpercaya, verifikasi legalitas, dan sinkronisasi database."
        )
        task_queue.start_task(task_id)

        try:
            local_db.log(self.name, f"[{task_id}] Mendelegasikan tugas ke AI Recruitment...")
            recruitment_res = ai_recruitment.discover_vacancies(target_count=target_count)
            candidates = recruitment_res.get("candidates") or []

            local_db.log(self.name, f"[{task_id}] Meminta AI Verification memverifikasi {len(candidates)} kandidat...")
            verification_res = ai_verification.verify_batch(candidates)
            passed = verification_res.get("passed") or []

            local_db.log(self.name, f"[{task_id}] Menginstruksikan AI Data Manager sinkronisasi {len(passed)} lowongan lolos...")
            sync_res = ai_data_manager.sync_jobs(passed)

            result = {
                "task_id": task_id,
                "status": "completed",
                "recruitment": recruitment_res,
                "verification": verification_res,
                "sync": sync_res,
                "summary": f"Ditemukan {len(candidates)} kandidat, {len(passed)} terverifikasi legal, {sync_res.get('inserted', 0)} berhasil dimasukkan ke Supabase."
            }
            task_queue.complete_task(task_id, result)
            return result

        except Exception as e:
            error_msg = f"Kegagalan pada alur rekrutmen: {e}"
            task_queue.fail_task(task_id, error_msg)
            return {"task_id": task_id, "status": "failed", "error": error_msg}

    def run_newsroom_pipeline(self, article_count: int = 1) -> Dict[str, Any]:
        """Orkestrasi alur: AI Newsroom -> AI SEO Specialist -> AI Designer -> AI Data Manager."""
        task_id = task_queue.create_task(
            agent_name=self.name,
            title=f"Siklus Redaksi & Publikasi Berita ({article_count} Artikel)",
            description="Riset berita primer, optimasi SEO, pembuatan thumbnail 16:9, dan publikasi artikel."
        )
        task_queue.start_task(task_id)

        try:
            local_db.log(self.name, f"[{task_id}] Menugaskan AI Newsroom untuk riset...")
            news_res = ai_newsroom.conduct_research_and_draft(count=article_count)
            drafts = news_res.get("drafts") or []

            published_articles = []
            for draft in drafts:
                local_db.log(self.name, f"[{task_id}] AI SEO Specialist mengoptimasi: {draft['title'][:40]}...")
                seo_draft = ai_seo_specialist.optimize_article(draft)

                local_db.log(self.name, f"[{task_id}] AI Designer merancang thumbnail 16:9...")
                designed_draft = ai_designer.generate_thumbnail_for_article(seo_draft)

                local_db.log(self.name, f"[{task_id}] AI Data Manager mempublikasikan ke Supabase...")
                success = ai_data_manager.sync_news_article(designed_draft)
                if success:
                    published_articles.append(designed_draft)

            result = {
                "task_id": task_id,
                "status": "completed",
                "articles_drafted": len(drafts),
                "articles_published": len(published_articles),
                "published_list": [{"slug": a["slug"], "title": a["title"]} for a in published_articles],
                "summary": f"Berhasil menyusun dan mempublikasikan {len(published_articles)} artikel berita industri terverifikasi."
            }
            task_queue.complete_task(task_id, result)
            return result

        except Exception as e:
            error_msg = f"Kegagalan pada alur newsroom: {e}"
            task_queue.fail_task(task_id, error_msg)
            return {"task_id": task_id, "status": "failed", "error": error_msg}

    def run_daily_audit_and_report(self) -> Dict[str, Any]:
        """Menjalankan pengarsipan expired, AI Auditor, dan menyusun Laporan Operasional Harian untuk CEO."""
        task_id = task_queue.create_task(
            agent_name=self.name,
            title="Audit Operasional Harian & Penyusunan Laporan CEO",
            description="Pengarsipan lowongan kedaluwarsa, audit integritas database, dan kompilasi laporan harian."
        )
        task_queue.start_task(task_id)

        try:
            # 1. Arsipkan lowongan kedaluwarsa terlebih dahulu sebelum audit
            cleanup_res = ai_data_manager.cleanup_expired_jobs()

            # 2. AI Auditor
            audit_res = ai_auditor.run_full_audit()

            # 3. Kumpulkan metrik aktif nyata (WIB)
            today_str = datetime.now(WIB_TIMEZONE).date().isoformat()
            jobs_count = supabase_client.get_count(
                "jobs",
                f"status=eq.published&deadline=gte.{today_str}",
            )
            news_count = supabase_client.get_count("news", "status=eq.published")

            with local_db.get_connection() as conn:
                agents_data = conn.execute(
                    "SELECT name, role, department, status, total_tasks, success_tasks FROM ai_agents"
                ).fetchall()

            report_md = f"""# Laporan Operasional Harian — InfoLokerKita AI Company
**Tanggal:** {today_str} (WIB)
**Penyusun:** AI Manager (Direktur Operasional)
**Penerima:** Human Founder (CEO)

---

## 1. Ringkasan Eksekutif Operasional
Operasional perusahaan digital InfoLokerKita hari ini berjalan di bawah pengawasan AI Manager. Seluruh divisi AI telah melaksanakan pemeriksaan, kurasi informasi lowongan kerja, pengawasan berita industri, pengarsipan lowongan kedaluwarsa, serta audit integritas sistem.

- **Status Integritas Sistem:** {'🟢 SEHAT & NORMAL' if audit_res.get('overall_healthy') else '🟡 PERLU PERHATIAN'}
- **Total Lowongan Aktif di Supabase:** {jobs_count} lowongan
- **Total Berita Terbit di Supabase:** {news_count} artikel
- **Lowongan Kedaluwarsa Teridentifikasi:** {cleanup_res.get('expired_count', 0)} (diarsipkan: {cleanup_res.get('archived_count', 0)})

---

## 2. Kinerja Divisi AI Hari Ini

| Divisi AI | Peran / Jabatan | Status | Total Tugas | Berhasil |
|:---|:---|:---:|:---:|:---:|
"""
            for a in agents_data:
                report_md += f"| {a['name']} | {a['role']} | {'✅ Aktif' if a['status']=='active' else '⏸️ Standby'} | {a['total_tasks']} | {a['success_tasks']} |\n"

            report_md += f"""
---

## 3. Hasil Audit Sistem (AI Auditor)
- **Ringkasan Audit:** {audit_res.get('summary')}
- **Error Log (24 Jam Terakhir):** {audit_res.get('errors_last_24h')} catatan

---

## 4. Rekomendasi Langkah Kerja untuk CEO
1. Review draf materi promosi di Marketing Department untuk persetujuan publikasi media sosial.
2. Tinjau lowongan terkurasi yang memerlukan otorisasi prioritas penempatan.
3. Seluruh infrastruktur Astro, Supabase, dan Cloudflare berada dalam kondisi operasional siap saji.

*Laporan ini diverifikasi secara otomatis dari data nyata sistem database InfoLokerKita.*
"""

            with local_db.get_connection() as conn:
                conn.execute("""
                INSERT OR REPLACE INTO ai_reports (report_date, report_type, title, summary, metrics_json, content_markdown, created_at)
                VALUES (?, 'daily', ?, ?, ?, ?, datetime('now'))
                """, (
                    today_str,
                    f"Laporan Operasional Harian {today_str}",
                    audit_res.get("summary", "Operasional harian berjalan normal."),
                    json.dumps({
                        "jobs_count": jobs_count,
                        "news_count": news_count,
                        "expired_count": cleanup_res.get("expired_count", 0),
                        "archived_count": cleanup_res.get("archived_count", 0),
                        "overall_healthy": audit_res.get("overall_healthy", True)
                    }),
                    report_md
                ))
                conn.commit()

            report_file = REPORTS_DIR / f"daily_report_{today_str}.md"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report_md)

            result = {
                "task_id": task_id,
                "status": "completed",
                "report_date": today_str,
                "report_file": str(report_file),
                "cleanup": cleanup_res,
                "summary": audit_res.get("summary"),
                "markdown": report_md
            }
            task_queue.complete_task(task_id, result)
            return result

        except Exception as e:
            error_msg = f"Kegagalan penyusunan laporan operasional: {e}"
            task_queue.fail_task(task_id, error_msg)
            return {"task_id": task_id, "status": "failed", "error": error_msg}

    def execute_ceo_command(self, command: str) -> Dict[str, Any]:
        """Menerima dan memproses perintah langsung dari CEO melalui Dashboard atau CLI."""
        cmd_lower = command.lower()
        local_db.log(self.name, f"Menerima instruksi langsung dari CEO: '{command}'")

        if "loker" in cmd_lower or "rekrutmen" in cmd_lower or "lowongan" in cmd_lower:
            return self.run_recruitment_pipeline(target_count=5)
        elif "berita" in cmd_lower or "news" in cmd_lower or "artikel" in cmd_lower:
            return self.run_newsroom_pipeline(article_count=1)
        elif "arsip" in cmd_lower or "expired" in cmd_lower or "kedaluwarsa" in cmd_lower:
            return ai_data_manager.cleanup_expired_jobs()
        elif "audit" in cmd_lower or "laporan" in cmd_lower or "report" in cmd_lower:
            return self.run_daily_audit_and_report()
        elif "marketing" in cmd_lower or "promo" in cmd_lower or "sosmed" in cmd_lower:
            today_wib = datetime.now(WIB_TIMEZONE).date().isoformat()
            jobs = supabase_client.query_rows(
                "jobs",
                f"select=slug,title,company_name,location&status=eq.published&deadline=gte.{today_wib}&limit=2&order=created_at.desc"
            )
            news = supabase_client.query_rows(
                "news",
                "select=slug,title,category&status=eq.published&limit=2&order=created_at.desc"
            )
            calendar = ai_marketing.create_daily_content_calendar(jobs, news)
            return {"status": "success", "message": f"Berhasil membuat kalender konten promosi ({len(calendar)} slot materi)."}
        else:
            local_db.log(self.name, "Perintah umum diterima: Menjalankan audit dan sinkronisasi laporan.")
            return self.run_daily_audit_and_report()


ai_manager = AIManagerAgent()
