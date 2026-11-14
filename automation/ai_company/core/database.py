import sqlite3
import json
import urllib.request
import urllib.parse
import urllib.error
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from automation.ai_company.core.config import (
    SUPABASE_URL,
    SUPABASE_KEY,
    LOCAL_DB_PATH
)

class SupabaseClient:
    """Supabase REST API Client for reading and writing data."""
    def __init__(self, url: str = SUPABASE_URL, key: str = SUPABASE_KEY):
        self.url = url.rstrip('/') if url else ''
        self.key = key

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }
        if extra:
            headers.update(extra)
        return headers

    def request(self, endpoint: str, method: str = "GET", data: Any = None, extra_headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Any:
        if not self.url or not self.key:
            return None

        url = f"{self.url}/rest/v1/{endpoint.lstrip('/')}"
        payload = json.dumps(data).encode("utf-8") if data is not None else None

        for attempt in range(1, 4):
            req = urllib.request.Request(
                url,
                data=payload,
                headers=self._headers(extra_headers),
                method=method
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    body = response.read().decode("utf-8")
                    content_range = response.headers.get("Content-Range")
                    parsed = json.loads(body) if body else None
                    if extra_headers and extra_headers.get("Prefer") == "count=exact":
                        return {"data": parsed, "count": content_range}
                    return parsed
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                if error.code in (404, 400, 401, 403, 409):
                    raise RuntimeError(f"Supabase HTTP {error.code}: {detail[:500]}")
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
            except Exception as e:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        return None

    def get_count(self, table: str, filter_query: str = "") -> int:
        try:
            extra = filter_query if filter_query.startswith("&") or not filter_query else f"&{filter_query}"
            endpoint = f"{table}?select=id{extra}"
            res = self.request(endpoint, extra_headers={"Range": "0-0", "Prefer": "count=exact"})
            if res and isinstance(res, dict) and "count" in res and res["count"]:
                parts = res["count"].split("/")
                if len(parts) == 2 and parts[1].isdigit():
                    return int(parts[1])
            return 0
        except Exception:
            return 0

    def query_rows(self, table: str, query: str = "") -> List[Dict[str, Any]]:
        try:
            endpoint = f"{table}?{query}" if query else table
            res = self.request(endpoint)
            return res if isinstance(res, list) else []
        except Exception as e:
            return []

    def insert_rows(self, table: str, rows: List[Dict[str, Any]]) -> bool:
        if not rows:
            return True
        try:
            self.request(
                table,
                method="POST",
                data=rows,
                extra_headers={"Prefer": "return=minimal"}
            )
            return True
        except Exception as e:
            raise RuntimeError(f"Gagal memasukkan data ke {table}: {e}")

    def update_row(self, table: str, match_field: str, match_val: str, data: Dict[str, Any]) -> bool:
        try:
            endpoint = f"{table}?{match_field}=eq.{urllib.parse.quote(match_val)}"
            self.request(
                endpoint,
                method="PATCH",
                data=data,
                extra_headers={"Prefer": "return=minimal"}
            )
            return True
        except Exception as e:
            raise RuntimeError(f"Gagal memperbarui {table}: {e}")


class LocalDatabase:
    """SQLite Local Database for AI Organization State, Tasks, and Logs."""
    def __init__(self, db_path=LOCAL_DB_PATH):
        self.db_path = str(db_path)
        self.init_schema()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. AI Agents registry
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_agents (
                name TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                department TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                description TEXT,
                total_tasks INTEGER DEFAULT 0,
                success_tasks INTEGER DEFAULT 0,
                failed_tasks INTEGER DEFAULT 0,
                last_active TEXT,
                config_json TEXT DEFAULT '{}'
            )
            """)

            # 2. Task queue
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                agent_name TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                priority INTEGER DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'pending', -- pending, running, completed, failed, needs_approval
                payload_json TEXT DEFAULT '{}',
                result_json TEXT DEFAULT '{}',
                error_notes TEXT,
                started_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON ai_tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_agent ON ai_tasks(agent_name)")

            # 3. AI Execution Logs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT 'INFO',
                message TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
            """)

            # 4. Daily Reports
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT UNIQUE NOT NULL,
                report_type TEXT NOT NULL DEFAULT 'daily',
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                metrics_json TEXT DEFAULT '{}',
                content_markdown TEXT,
                created_at TEXT NOT NULL
            )
            """)

            # 5. Marketing Calendar & Social Content
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS marketing_calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_platform TEXT NOT NULL,
                content_type TEXT NOT NULL,
                title TEXT NOT NULL,
                copy_text TEXT NOT NULL,
                tags TEXT,
                status TEXT NOT NULL DEFAULT 'draft', -- draft, scheduled, published
                scheduled_for TEXT,
                created_at TEXT NOT NULL
            )
            """)

            # 6. Financial & Metric Records
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_date TEXT NOT NULL,
                revenue_source TEXT NOT NULL, -- adsense, sponsored_vacancy, sponsored_article, affiliate
                amount_idr REAL NOT NULL DEFAULT 0.0,
                notes TEXT,
                verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """)

            # 8. Staged records when waiting for service_role authorization
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS staged_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                data_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'staged',
                created_at TEXT NOT NULL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS staged_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                data_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'staged',
                created_at TEXT NOT NULL
            )
            """)

            # Seed AI Agents if not exists
            default_agents = [
                ("ai_manager", "Direktur Operasional", "Executive", "Pusat koordinasi, delegasi tugas, pengawasan divisi, dan pelaporan CEO."),
                ("ai_recruitment", "Spesialis Rekrutmen & Kurasi Loker", "Recruitment", "Pencarian lowongan kerja terpercaya dari Karirhub dan portal resmi."),
                ("ai_verification", "Verifikator Integritas & Anti-Fraud", "Verification", "Pemeriksaan legalitas perusahaan, domain resmi, dan pendeteksi penipuan."),
                ("ai_newsroom", "Editor Berita Industri & Ketenagakerjaan", "Newsroom", "Riset berita ekonomi, ketenagakerjaan, dan penyusunan artikel orisinal terverifikasi."),
                ("ai_seo_specialist", "Spesialis Optimasi SEO & Metadata", "SEO", "Optimasi keyword, meta title, meta description, heading, dan internal linking."),
                ("ai_designer", "Desainer Grafis & Aset Visual", "Design", "Resolusi logo resmi perusahaan dan pembuatan thumbnail berita 16:9."),
                ("ai_data_manager", "Manajer Database & Integrasi Supabase", "Data Management", "Validasi schema, deduplikasi data, sinkronisasi Supabase, dan manajemen arsip."),
                ("ai_marketing", "Strategis Pemasaran & Media Sosial", "Marketing", "Penyusunan copy Facebook, WhatsApp, Telegram, dan kalender konten promosi."),
                ("ai_auditor", "Auditor Sistem & Kualitas Data", "Audit", "Pemeriksaan 404 URL, link kadaluwarsa, integritas database, dan pelaporan anomali.")
            ]

            for name, role, dept, desc in default_agents:
                cursor.execute("""
                INSERT OR IGNORE INTO ai_agents (name, role, department, status, description, last_active)
                VALUES (?, ?, ?, 'active', ?, datetime('now'))
                """, (name, role, dept, desc))

            conn.commit()

    def log(self, agent_name: str, message: str, level: str = "INFO", details: str = ""):
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.cursor().execute("""
            INSERT INTO ai_logs (agent_name, level, message, details, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (agent_name, level, message, details, now))
            conn.commit()


supabase_client = SupabaseClient()
local_db = LocalDatabase()
