import json
import sys
import urllib.parse
from datetime import datetime
from automation.ai_company.core.config import WIB_TIMEZONE
from automation.ai_company.core.database import local_db, supabase_client


def sync_staged_records() -> dict:
    """Sinkronisasi seluruh antrean staged_news dan staged_jobs dari SQLite ke Supabase."""
    synced_news = 0
    synced_jobs = 0
    now_iso = datetime.now(WIB_TIMEZONE).isoformat()

    with local_db.get_connection() as conn:
        news_rows = conn.execute(
            "SELECT id, slug, data_json FROM staged_news WHERE status='staged'"
        ).fetchall()
        for r in news_rows:
            data = json.loads(r["data_json"])
            slug = r["slug"]
            query = urllib.parse.urlencode({"select": "slug", "slug": f"eq.{slug}"})
            existing = supabase_client.query_rows("news", query)
            if existing:
                conn.execute("UPDATE staged_news SET status='synced' WHERE id=?", (r["id"],))
                conn.commit()
                continue
            try:
                data.setdefault("updated_at", now_iso)
                supabase_client.insert_rows("news", [data], ignore_duplicates=True, on_conflict="slug")
                conn.execute("UPDATE staged_news SET status='synced' WHERE id=?", (r["id"],))
                conn.commit()
                synced_news += 1
            except Exception as e:
                print(f"Gagal sync berita [{slug}]: {e}")

        job_rows = conn.execute(
            "SELECT id, slug, data_json FROM staged_jobs WHERE status='staged'"
        ).fetchall()
        for r in job_rows:
            data = json.loads(r["data_json"])
            slug = r["slug"]
            query = urllib.parse.urlencode({"select": "slug", "slug": f"eq.{slug}"})
            existing = supabase_client.query_rows("jobs", query)
            if existing:
                conn.execute("UPDATE staged_jobs SET status='synced' WHERE id=?", (r["id"],))
                conn.commit()
                continue
            try:
                data.setdefault("updated_at", now_iso)
                supabase_client.insert_rows("jobs", [data], ignore_duplicates=True, on_conflict="slug")
                conn.execute("UPDATE staged_jobs SET status='synced' WHERE id=?", (r["id"],))
                conn.commit()
                synced_jobs += 1
            except Exception as e:
                print(f"Gagal sync lowongan [{slug}]: {e}")

    return {"synced_news": synced_news, "synced_jobs": synced_jobs}


def main():
    if "--sync-staged" in sys.argv:
        result = sync_staged_records()
        print(
            f"Sinkronisasi staging selesai: {result['synced_news']} berita, "
            f"{result['synced_jobs']} lowongan."
        )
        return

    print("Gunakan flag --sync-staged untuk menyinkronkan antrean staging lokal ke Supabase.")


if __name__ == "__main__":
    main()
