import hmac
import json
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

from automation.ai_company.agents.data_manager import ai_data_manager
from automation.ai_company.agents.manager import ai_manager
from automation.ai_company.core.config import (
    AI_COMPANY_HOST,
    ALLOWED_ORIGINS,
    CEO_SECRET_PIN,
    PORT,
    WIB_TIMEZONE,
)
from automation.ai_company.core.database import local_db, supabase_client
from automation.ai_company.core.task_queue import task_queue
from automation.ai_company.scheduler import automation_center

MAX_BODY_BYTES = 1024 * 1024  # 1 MB
ALLOWED_AGENT_STATUSES = frozenset({"active", "standby", "paused"})
ALLOWED_CYCLES = frozenset({"all", "0500", "0700", "0800"})


class AICompanyAPIHandler(BaseHTTPRequestHandler):
    """HTTP JSON API Handler for CEO Headquarters Dashboard."""

    def _get_allowed_origin(self) -> Optional[str]:
        origin = (self.headers.get("Origin") or "").strip().rstrip("/")
        if origin and origin in ALLOWED_ORIGINS:
            return origin
        return None

    def _set_security_and_cors_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Vary", "Origin")

        allowed_origin = self._get_allowed_origin()
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CEO-PIN")
            self.send_header("Access-Control-Max-Age", "600")

    def _send_json(self, status_code: int, data: Any) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_security_and_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        origin = (self.headers.get("Origin") or "").strip().rstrip("/")
        if origin and origin not in ALLOWED_ORIGINS:
            self._send_json(403, {"error": "Origin tidak diizinkan oleh kebijakan CORS."})
            return

        self.send_response(204)
        self._set_security_and_cors_headers()
        self.end_headers()

    def _extract_pin(self) -> str:
        header_pin = (self.headers.get("X-CEO-PIN") or "").strip()
        if header_pin:
            return header_pin

        auth_header = (self.headers.get("Authorization") or "").strip()
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()

        return ""

    def _require_auth(self) -> bool:
        if not CEO_SECRET_PIN:
            self._send_json(
                503,
                {"error": "Layanan belum siap: CEO_SECRET_PIN belum dikonfigurasi di server."},
            )
            return False

        origin = (self.headers.get("Origin") or "").strip().rstrip("/")
        if origin and origin not in ALLOWED_ORIGINS:
            self._send_json(403, {"error": "Origin tidak diizinkan oleh kebijakan CORS."})
            return False

        provided_pin = self._extract_pin()
        if not provided_pin or not hmac.compare_digest(provided_pin, CEO_SECRET_PIN):
            self._send_json(
                401,
                {"error": "Akses ditolak: PIN CEO tidak valid atau belum disertakan pada header X-CEO-PIN."},
            )
            return False

        return True

    def _read_json_body(self) -> Optional[dict]:
        raw_len = self.headers.get("Content-Length", "0")
        try:
            content_len = int(raw_len)
        except ValueError:
            self._send_json(400, {"error": "Header Content-Length tidak valid."})
            return None

        if content_len < 0 or content_len > MAX_BODY_BYTES:
            self._send_json(413, {"error": "Ukuran payload melebihi batas maksimum."})
            return None

        if content_len == 0:
            return {}

        body = self.rfile.read(content_len).decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Body permintaan harus berupa JSON yang valid."})
            return None

        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Payload JSON harus berupa objek."})
            return None

        return payload

    def do_GET(self) -> None:
        if not self._require_auth():
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            if path == "/api/auth/verify":
                self._send_json(200, {
                    "authenticated": True,
                    "timestamp": datetime.now(WIB_TIMEZONE).isoformat(),
                })

            elif path == "/api/status":
                today_wib = datetime.now(WIB_TIMEZONE).date().isoformat()
                jobs_count = supabase_client.get_count(
                    "jobs",
                    f"status=eq.published&deadline=gte.{today_wib}",
                )
                news_count = supabase_client.get_count("news", "status=eq.published")

                with local_db.get_connection() as conn:
                    tasks_count = conn.execute("SELECT count(*) as c FROM ai_tasks").fetchone()["c"]
                    completed_tasks = conn.execute(
                        "SELECT count(*) as c FROM ai_tasks WHERE status='completed'"
                    ).fetchone()["c"]
                    agents = [
                        dict(r)
                        for r in conn.execute(
                            "SELECT name, role, department, status, description, total_tasks, success_tasks FROM ai_agents"
                        ).fetchall()
                    ]
                    recent_logs = [
                        dict(r)
                        for r in conn.execute(
                            "SELECT * FROM ai_logs ORDER BY id DESC LIMIT 10"
                        ).fetchall()
                    ]

                self._send_json(200, {
                    "status": "online",
                    "timestamp": datetime.now(WIB_TIMEZONE).isoformat(),
                    "metrics": {
                        "jobs_in_supabase": jobs_count,
                        "news_in_supabase": news_count,
                        "total_tasks_processed": tasks_count,
                        "completed_tasks": completed_tasks,
                        "active_agents_count": len([a for a in agents if a["status"] == "active"]),
                        "total_agents_count": len(agents),
                    },
                    "agents": agents,
                    "recent_logs": recent_logs,
                })

            elif path == "/api/agents":
                with local_db.get_connection() as conn:
                    agents = [dict(r) for r in conn.execute("SELECT * FROM ai_agents").fetchall()]
                self._send_json(200, {"agents": agents})

            elif path == "/api/tasks":
                tasks = task_queue.list_tasks(limit=30)
                self._send_json(200, {"tasks": tasks})

            elif path == "/api/reports/daily":
                with local_db.get_connection() as conn:
                    reports = [
                        dict(r)
                        for r in conn.execute(
                            "SELECT * FROM ai_reports ORDER BY id DESC LIMIT 7"
                        ).fetchall()
                    ]
                self._send_json(200, {"reports": reports})

            elif path == "/api/audit":
                from automation.ai_company.agents.auditor import ai_auditor
                audit_res = ai_auditor.run_full_audit()
                self._send_json(200, audit_res)

            elif path == "/api/financial":
                with local_db.get_connection() as conn:
                    records = [
                        dict(r)
                        for r in conn.execute(
                            "SELECT * FROM financial_records ORDER BY id DESC LIMIT 20"
                        ).fetchall()
                    ]
                self._send_json(200, {
                    "records": records,
                    "monetization_channels": [
                        {"name": "Google AdSense", "status": "Ready for Setup", "estimated_rpm_idr": 15000},
                        {"name": "Lowongan Kerja Sponsor", "status": "Tersedia", "rate_idr": 250000},
                        {"name": "Artikel Advertorial / Industri", "status": "Tersedia", "rate_idr": 500000},
                        {"name": "Afiliasi Pelatihan & Sertifikasi", "status": "Tersedia", "commission_pct": "20%"},
                    ],
                })

            else:
                self._send_json(404, {"error": "Endpoint tidak ditemukan."})
        except Exception as exc:
            local_db.log("api_server", f"Error GET {path}: {exc}", level="ERROR")
            self._send_json(500, {"error": "Terjadi kesalahan internal pada server API."})

    def do_POST(self) -> None:
        if not self._require_auth():
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        payload = self._read_json_body()
        if payload is None:
            return

        try:
            if path == "/api/ceo/command":
                command = str(payload.get("command") or "").strip()
                if not command:
                    self._send_json(400, {"error": "Perintah CEO tidak boleh kosong."})
                    return
                result = ai_manager.execute_ceo_command(command)
                self._send_json(200, {"status": "success", "result": result})

            elif path == "/api/automation/trigger":
                cycle = str(payload.get("cycle") or "all").strip()
                if cycle not in ALLOWED_CYCLES:
                    self._send_json(400, {"error": f"Siklus tidak valid. Gunakan: {', '.join(sorted(ALLOWED_CYCLES))}."})
                    return

                if cycle == "0500":
                    res = automation_center.run_morning_recruitment_cycle()
                elif cycle == "0700":
                    res = automation_center.run_morning_newsroom_cycle()
                elif cycle == "0800":
                    res = automation_center.run_morning_audit_cycle()
                else:
                    res = automation_center.run_full_daily_cycle()
                self._send_json(200, {"status": "success", "result": res})

            elif path == "/api/data/cleanup-expired":
                res = ai_data_manager.cleanup_expired_jobs()
                self._send_json(200, {"status": "success", "result": res})

            elif path == "/api/agents/toggle":
                agent_name = str(payload.get("agent_name") or "").strip()
                new_status = str(payload.get("status") or "active").strip().lower()
                if not agent_name or new_status not in ALLOWED_AGENT_STATUSES:
                    self._send_json(400, {"error": "Parameter agent_name atau status tidak valid."})
                    return

                with local_db.get_connection() as conn:
                    cursor = conn.execute(
                        "UPDATE ai_agents SET status = ? WHERE name = ?",
                        (new_status, agent_name),
                    )
                    conn.commit()
                    if cursor.rowcount == 0:
                        self._send_json(404, {"error": f"Agen '{agent_name}' tidak ditemukan."})
                        return

                local_db.log("ai_manager", f"CEO mengubah status agen {agent_name} menjadi {new_status}")
                self._send_json(200, {"status": "success", "agent": agent_name, "new_status": new_status})

            elif path == "/api/tasks/approve":
                task_id = str(payload.get("task_id") or "").strip()
                if not task_id:
                    self._send_json(400, {"error": "task_id wajib diisi."})
                    return
                success = task_queue.approve_task(task_id)
                self._send_json(200, {"status": "success" if success else "failed", "task_id": task_id})

            elif path == "/api/tasks/reject":
                task_id = str(payload.get("task_id") or "").strip()
                if not task_id:
                    self._send_json(400, {"error": "task_id wajib diisi."})
                    return
                reason = str(payload.get("reason") or "Ditolak CEO").strip()
                success = task_queue.reject_task(task_id, reason)
                self._send_json(200, {"status": "success" if success else "failed", "task_id": task_id})

            else:
                self._send_json(404, {"error": "Endpoint POST tidak ditemukan."})
        except Exception as exc:
            local_db.log("api_server", f"Error POST {path}: {exc}", level="ERROR")
            self._send_json(500, {"error": "Terjadi kesalahan internal pada server API."})

    def do_PUT(self) -> None:
        self._send_json(405, {"error": "Metode HTTP tidak diizinkan."})

    def do_PATCH(self) -> None:
        self._send_json(405, {"error": "Metode HTTP tidak diizinkan."})

    def do_DELETE(self) -> None:
        self._send_json(405, {"error": "Metode HTTP tidak diizinkan."})


def run_server(host: str = AI_COMPANY_HOST, port: int = PORT) -> None:
    if not CEO_SECRET_PIN or len(CEO_SECRET_PIN) < 8:
        raise RuntimeError(
            "CEO_SECRET_PIN wajib diatur di environment/.env dengan panjang minimal 8 karakter sebelum menjalankan server."
        )

    server_address = (host, port)
    httpd = HTTPServer(server_address, AICompanyAPIHandler)
    print(f"InfoLokerKita AI Company Server berjalan di http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
