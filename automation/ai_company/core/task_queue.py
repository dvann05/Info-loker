import uuid
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from automation.ai_company.core.database import local_db

class TaskQueue:
    """Manages autonomous inter-agent task queue with state transitions and audit trails."""

    def create_task(
        self,
        agent_name: str,
        title: str,
        description: str = "",
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 1,
        requires_approval: bool = False
    ) -> str:
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()
        initial_status = "needs_approval" if requires_approval else "pending"

        with local_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO ai_tasks (
                task_id, agent_name, title, description, priority,
                status, payload_json, result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}', ?)
            """, (
                task_id, agent_name, title, description, priority,
                initial_status, json.dumps(payload or {}), now
            ))
            conn.commit()

        local_db.log(agent_name, f"Tugas baru dibuat: [{task_id}] {title} (Status: {initial_status})")
        return task_id

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with local_db.get_connection() as conn:
            row = conn.execute("SELECT * FROM ai_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["payload"] = json.loads(data.get("payload_json") or "{}")
            data["result"] = json.loads(data.get("result_json") or "{}")
            return data

    def list_tasks(self, status: Optional[str] = None, agent_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        query = "SELECT * FROM ai_tasks WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with local_db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["payload"] = json.loads(item.get("payload_json") or "{}")
                item["result"] = json.loads(item.get("result_json") or "{}")
                results.append(item)
            return results

    def start_task(self, task_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with local_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE ai_tasks 
            SET status = 'running', started_at = ?
            WHERE task_id = ? AND status IN ('pending', 'needs_approval')
            """, (now, task_id))
            conn.commit()
            updated = cursor.rowcount > 0

        if updated:
            task = self.get_task(task_id)
            if task:
                local_db.log(task["agent_name"], f"Memulai eksekusi tugas [{task_id}] {task['title']}")
        return updated

    def complete_task(self, task_id: str, result: Dict[str, Any]) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with local_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE ai_tasks 
            SET status = 'completed', result_json = ?, completed_at = ?
            WHERE task_id = ?
            """, (json.dumps(result), now, task_id))

            # Update agent stats
            task = self.get_task(task_id)
            if task:
                cursor.execute("""
                UPDATE ai_agents 
                SET total_tasks = total_tasks + 1,
                    success_tasks = success_tasks + 1,
                    last_active = ?
                WHERE name = ?
                """, (now, task["agent_name"]))
            conn.commit()

        if task:
            local_db.log(task["agent_name"], f"Tugas selesai sukses: [{task_id}] {task['title']}")
        return True

    def fail_task(self, task_id: str, error_notes: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with local_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE ai_tasks 
            SET status = 'failed', error_notes = ?, completed_at = ?
            WHERE task_id = ?
            """, (error_notes, now, task_id))

            task = self.get_task(task_id)
            if task:
                cursor.execute("""
                UPDATE ai_agents 
                SET total_tasks = total_tasks + 1,
                    failed_tasks = failed_tasks + 1,
                    last_active = ?
                WHERE name = ?
                """, (now, task["agent_name"]))
            conn.commit()

        if task:
            local_db.log(task["agent_name"], f"Tugas GAGAL: [{task_id}] {error_notes}", level="ERROR")
        return True

    def set_needs_approval(self, task_id: str, preview_result: Dict[str, Any]) -> bool:
        with local_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE ai_tasks 
            SET status = 'needs_approval', result_json = ?
            WHERE task_id = ?
            """, (json.dumps(preview_result), task_id))
            conn.commit()

        task = self.get_task(task_id)
        if task:
            local_db.log(task["agent_name"], f"Tugas [{task_id}] menunggu persetujuan CEO sebelum publikasi/eksekusi.")
        return True

    def approve_task(self, task_id: str) -> bool:
        with local_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE ai_tasks 
            SET status = 'pending'
            WHERE task_id = ? AND status = 'needs_approval'
            """, (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def reject_task(self, task_id: str, reason: str = "Ditolak oleh CEO") -> bool:
        return self.fail_task(task_id, f"Ditolak oleh CEO: {reason}")


task_queue = TaskQueue()
