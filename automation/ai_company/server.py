import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from typing import Dict, Any

from automation.ai_company.core.config import PORT, CEO_SECRET_PIN
from automation.ai_company.core.database import supabase_client, local_db
from automation.ai_company.core.task_queue import task_queue
from automation.ai_company.agents.manager import ai_manager
from automation.ai_company.scheduler import automation_center

class AICompanyAPIHandler(BaseHTTPRequestHandler):
    """HTTP JSON API Handler for CEO Headquarters Dashboard."""

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PATCH")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CEO-PIN")

    def _send_json(self, status_code: int, data: Any):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def _verify_ceo_pin(self) -> bool:
        pin = self.headers.get("X-CEO-PIN") or ""
        # Also check query param ?pin=
        if not pin and "?" in self.path:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            pin = params.get("pin", [""])[0]
        return pin == CEO_SECRET_PIN

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            jobs_count = supabase_client.get_count("jobs")
            news_count = supabase_client.get_count("news")

            with local_db.get_connection() as conn:
                tasks_count = conn.execute("SELECT count(*) as c FROM ai_tasks").fetchone()["c"]
                completed_tasks = conn.execute("SELECT count(*) as c FROM ai_tasks WHERE status='completed'").fetchone()["c"]
                agents = [dict(r) for r in conn.execute("SELECT name, role, department, status, total_tasks, success_tasks FROM ai_agents").fetchall()]
                recent_logs = [dict(r) for r in conn.execute("SELECT * FROM ai_logs ORDER BY id DESC LIMIT 10").fetchall()]

            self._send_json(200, {
                "status": "online",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": {
                    "jobs_in_supabase": jobs_count,
                    "news_in_supabase": news_count,
                    "total_tasks_processed": tasks_count,
                    "completed_tasks": completed_tasks,
                    "active_agents_count": len([a for a in agents if a["status"] == "active"])
                },
                "agents": agents,
                "recent_logs": recent_logs
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
                reports = [dict(r) for r in conn.execute("SELECT * FROM ai_reports ORDER BY id DESC LIMIT 7").fetchall()]
            self._send_json(200, {"reports": reports})

        elif path == "/api/audit":
            from automation.ai_company.agents.auditor import ai_auditor
            audit_res = ai_auditor.run_full_audit()
            self._send_json(200, audit_res)

        elif path == "/api/financial":
            with local_db.get_connection() as conn:
                records = [dict(r) for r in conn.execute("SELECT * FROM financial_records ORDER BY id DESC LIMIT 20").fetchall()]
            # Estimated metrics based on real views
            self._send_json(200, {
                "records": records,
                "monetization_channels": [
                    {"name": "Google AdSense", "status": "Ready for Setup", "estimated_rpm_idr": 15000},
                    {"name": "Lowongan Kerja Sponsor", "status": "Tersedia", "rate_idr": 250000},
                    {"name": "Artikel Advertorial / Industri", "status": "Tersedia", "rate_idr": 500000},
                    {"name": "Afiliasi Pelatihan & Sertifikasi", "status": "Tersedia", "commission_pct": "20%"}
                ]
            })

        else:
            self._send_json(404, {"error": "Endpoint tidak ditemukan"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Verify CEO Pin for mutating actions
        if not self._verify_ceo_pin():
            self._send_json(401, {"error": "Akses Ditolak: PIN CEO tidak valid atau belum diisi."})
            return

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}

        if path == "/api/ceo/command":
            command = payload.get("command", "")
            if not command:
                self._send_json(400, {"error": "Perintah CEO tidak boleh kosong"})
                return
            result = ai_manager.execute_ceo_command(command)
            self._send_json(200, {"status": "success", "result": result})

        elif path == "/api/automation/trigger":
            cycle = payload.get("cycle", "all")
            if cycle == "0500":
                res = automation_center.run_morning_recruitment_cycle()
            elif cycle == "0700":
                res = automation_center.run_morning_newsroom_cycle()
            elif cycle == "0800":
                res = automation_center.run_morning_audit_cycle()
            else:
                res = automation_center.run_full_daily_cycle()
            self._send_json(200, {"status": "success", "result": res})

        elif path == "/api/agents/toggle":
            agent_name = payload.get("agent_name")
            new_status = payload.get("status", "active")
            with local_db.get_connection() as conn:
                conn.execute("UPDATE ai_agents SET status = ? WHERE name = ?", (new_status, agent_name))
                conn.commit()
            local_db.log("ai_manager", f"CEO mengubah status agen {agent_name} menjadi {new_status}")
            self._send_json(200, {"status": "success", "agent": agent_name, "new_status": new_status})

        elif path == "/api/tasks/approve":
            task_id = payload.get("task_id")
            success = task_queue.approve_task(task_id)
            self._send_json(200, {"status": "success" if success else "failed", "task_id": task_id})

        elif path == "/api/tasks/reject":
            task_id = payload.get("task_id")
            reason = payload.get("reason", "Ditolak CEO")
            success = task_queue.reject_task(task_id, reason)
            self._send_json(200, {"status": "success" if success else "failed", "task_id": task_id})

        else:
            self._send_json(404, {"error": "Endpoint POST tidak ditemukan"})


def run_server(port: int = PORT):
    server_address = ("", port)
    httpd = HTTPServer(server_address, AICompanyAPIHandler)
    print(f"🚀 InfoLokerKita AI Company Server berjalan di http://localhost:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
