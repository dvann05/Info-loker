import sys
import json
from automation.ai_company.core.database import supabase_client, local_db
from automation.ai_company.core.task_queue import task_queue
from automation.ai_company.agents.manager import ai_manager
from automation.ai_company.scheduler import automation_center

def print_banner():
    print("=" * 65)
    print(" 🤖 INFOLOKERKITA AI COMPANY — AUTONOMOUS EMPLOYEE SYSTEM")
    print(" Human Founder & CEO Command Interface")
    print("=" * 65)

def cmd_status():
    print_banner()
    jobs_count = supabase_client.get_count("jobs")
    news_count = supabase_client.get_count("news")

    print(f"\n📊 DATA REAL SUPABASE:")
    print(f"  • Total Lowongan Aktif : {jobs_count}")
    print(f"  • Total Berita Aktif   : {news_count}")

    print(f"\n👥 STATUS DEVISI AI:")
    with local_db.get_connection() as conn:
        agents = conn.execute("SELECT name, role, department, status, total_tasks, success_tasks FROM ai_agents").fetchall()
        for a in agents:
            status_icon = "🟢" if a["status"] == "active" else "⏸️"
            print(f"  {status_icon} [{a['department']:<14}] {a['name']:<18} | {a['role']} ({a['success_tasks']}/{a['total_tasks']} tugas)")

    print(f"\n📋 TUGAS TERAKHIR:")
    tasks = task_queue.list_tasks(limit=5)
    for t in tasks:
        print(f"  • [{t['status'].upper():<9}] [{t['task_id']}] {t['title']}")
    print("=" * 65)

def cmd_report():
    print_banner()
    print("\n📝 MENYUSUN LAPORAN OPERASIONAL HARIAN OLEH AI MANAGER...")
    res = ai_manager.run_daily_audit_and_report()
    print("\n" + res.get("markdown", "Tidak ada konten laporan."))

def cmd_run(cycle: str = "all"):
    print_banner()
    print(f"\n⚡ MENJALANKAN SIKLUS OTOMASI: [{cycle.upper()}]...")
    if cycle == "0500":
        res = automation_center.run_morning_recruitment_cycle()
    elif cycle == "0700":
        res = automation_center.run_newsroom_cycle("Pagi (07.00 WIB)")
    elif cycle == "1200":
        res = automation_center.run_newsroom_cycle("Siang (12.00 WIB)")
    elif cycle == "1700":
        res = automation_center.run_newsroom_cycle("Sore (17.00 WIB)")
    elif cycle == "0800":
        res = automation_center.run_morning_audit_cycle()
    else:
        res = automation_center.run_full_daily_cycle()
    print(f"\n✅ Hasil Eksekusi:")
    print(json.dumps(res, indent=2, ensure_ascii=False))

def cmd_exec(instruction: str):
    print_banner()
    print(f"\n📢 MENGIRIMKAN INSTRUKSI CEO KE AI MANAGER: '{instruction}'...")
    res = ai_manager.execute_ceo_command(instruction)
    print(f"\n✅ Respon AI Manager:")
    print(json.dumps(res, indent=2, ensure_ascii=False))

def main():
    if len(sys.argv) < 2:
        print_banner()
        print("\nPenggunaan CLI:")
        print("  python -m automation.ai_company.cli status           -> Cek status real sistem & agen")
        print("  python -m automation.ai_company.cli report           -> Buat & tampilkan laporan harian CEO")
        print("  python -m automation.ai_company.cli run [0500|0700|0800|all] -> Eksekusi siklus otomatis")
        print("  python -m automation.ai_company.cli exec '<instruksi>' -> Berikan perintah ke AI Manager")
        print("  python -m automation.ai_company.cli server           -> Jalankan API backend daemon")
        return

    cmd = sys.argv[1].lower()
    if cmd == "status":
        cmd_status()
    elif cmd == "report":
        cmd_report()
    elif cmd == "run":
        cycle = sys.argv[2] if len(sys.argv) > 2 else "all"
        cmd_run(cycle)
    elif cmd in ("exec", "command"):
        if len(sys.argv) < 3:
            print("Harap sertakan instruksi. Contoh: python -m automation.ai_company.cli exec 'Cari lowongan'")
            return
        instruction = " ".join(sys.argv[2:])
        cmd_exec(instruction)
    elif cmd == "server":
        from automation.ai_company.server import run_server
        run_server()
    else:
        print(f"Perintah '{cmd}' tidak dikenal. Jalankan tanpa argumen untuk bantuan.")

if __name__ == "__main__":
    main()
