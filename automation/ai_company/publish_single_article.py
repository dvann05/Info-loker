import os
import sys
import json
from datetime import datetime, timezone
from automation.ai_company.core.database import supabase_client, local_db

ARTICLE_DATA = {
    "slug": "kemenaker-matangkan-formula-ump-2026-kenaikan-upah-minimum-buruh",
    "title": "Kemenaker dan Dewan Pengupahan Matangkan Formula UMP 2026: Proyeksi Kenaikan Upah Minimum dan Perlindungan Buruh",
    "excerpt": "Kementerian Ketenagakerjaan bersama Dewan Pengupahan Nasional (Depenas) memasuki tahap akhir perumusan formula penetapan Upah Minimum Provinsi (UMP) 2026, menyeimbangkan inflasi, pertumbuhan ekonomi, dan daya beli pekerja.",
    "content": """
Jakarta — Kementerian Ketenagakerjaan (Kemnaker) bersama Dewan Pengupahan Nasional (Depenas) terus mematangkan formula penghitungan Upah Minimum Provinsi (UMP) 2026. Pembahasan intensif dilakukan guna merumuskan skema pengupahan yang adil dan berimbang antara perlindungan daya beli pekerja serta kelangsungan dunia usaha di tengah dinamika ekonomi nasional.

Menteri Ketenagakerjaan Yassierli menegaskan bahwa pemerintah berkomitmen mendengarkan masukan dari serikat pekerja, asosiasi pengusaha (Apindo), dan pakar ekonomi independen agar regulasi turunan mengenai pengupahan dapat diterbitkan tepat waktu sebelum batas akhir penetapan UMP oleh para gubernur di seluruh Indonesia.

**Komponen Utama dalam Formula Penetapan UMP 2026**

Penetapan UMP 2026 dirancang dengan mempertimbangkan sejumlah variabel ekonomi makro dan karakteristik ketenagakerjaan daerah:

1. **Pertumbuhan Ekonomi Daerah:** Mengukur kinerja output ekonomi tiap provinsi sebagai dasar penyesuaian kenaikan batas upah.
2. **Laju Inflasi Daerah:** Menjadi bantalan utama agar kenaikan biaya hidup pekerja tidak menggerus upah riil yang diterima setiap bulan.
3. **Variabel Kontribusi Tenaga Kerja (Alpha):** Koefisien pengali yang merefleksikan kontribusi produktivitas tenaga kerja terhadap pertumbuhan ekonomi wilayah.
4. **Keseimbangan Sektor Padat Karya:** Kebijakan ini juga memperhatikan daya saing sektor industri manufaktur padat karya seperti tekstil, garmen, dan alas kaki yang menyerap jutaan tenaga kerja.

**Jadwal dan Mekanisme Pengumuman Resmi**

Sesuai regulasi ketenagakerjaan yang berlaku, penetapan Upah Minimum dilakukan secara bertahap:
- **Pengumuman UMP:** Ditetapkan dan diumumkan secara resmi oleh masing-masing Gubernur paling lambat akhir November.
- **Pengumuman UMK (Upah Minimum Kabupaten/Kota):** Ditetapkan oleh Gubernur berdasarkan rekomendasi bupati/wali kota dan dewan pengupahan daerah pada awal Desember.
- **Mulai Berlaku Efektif:** Seluruh ketentuan upah minimum baru akan mulai berlaku efektif per 1 Januari 2026.

**Apa Artinya bagi Pencari Kerja dan Karyawan?**

Bagi masyarakat pencari kerja dan karyawan aktif di berbagai sektor, penyesuaian UMP 2026 membawa implikasi penting:
- Standar penawaran gaji pokok (entry-level) untuk lowongan kerja baru per 2026 akan disesuaikan dengan ketentuan UMP/UMK yang baru di wilayah masing-masing.
- Perusahaan berkewajiban menyusun struktur dan skala upah (SUSU) bagi pekerja dengan masa kerja di atas satu tahun agar upah proporsional dengan kompetensi dan masa pengabdian.
- Pencari kerja disarankan untuk memeriksa standar upah minimum di wilayah yang dilamar agar dapat memperkirakan negosiasi gaji secara realistis.

**Peringatan Resmi InfoLoker:** Seluruh proses rekrutmen kerja resmi dari instansi pemerintah maupun korporasi terpercaya tidak pernah memungut biaya seleksi atau meminta transfer uang. Tetap waspada terhadap lowongan fiktif yang mencatut isu UMP untuk menarik calon korban penipuan.

*Sumber rujukan: Kementerian Ketenagakerjaan RI, Dewan Pengupahan Nasional, dan Kantor Berita ANTARA.*
""".strip(),
    "image_url": "/images/berita/kemenaker-matangkan-formula-ump-2026-kenaikan-upah-minimum-buruh.jpg",
    "image_alt": "Ilustrasi penetapan Upah Minimum Provinsi (UMP) 2026 Kementerian Ketenagakerjaan Republik Indonesia",
    "category": "Ketenagakerjaan",
    "source_name": "Kementerian Ketenagakerjaan RI dan ANTARA News",
    "source_url": "https://www.kemnaker.go.id/news",
    "status": "published",
    "is_featured": True,
    "published_at": datetime.now(timezone.utc).isoformat()
}

def sync_staged_news_records():
    """Sync all staged news records from SQLite to Supabase if service role key is available."""
    with local_db.get_connection() as conn:
        rows = conn.execute("SELECT id, slug, data_json FROM staged_news WHERE status='staged'").fetchall()
        if not rows:
            print("Tidak ada artikel berita di antrean staging lokal.")
            return 0

        synced = 0
        for r in rows:
            data = json.loads(r["data_json"])
            slug = r["slug"]
            # check existing in Supabase
            existing = supabase_client.query_rows("news", f"select=slug&slug=eq.{slug}")
            if existing:
                print(f"Artikel [{slug}] sudah ada di Supabase. Menandai selesai di staging.")
                conn.execute("UPDATE staged_news SET status='synced' WHERE id=?", (r["id"],))
                conn.commit()
                continue

            try:
                supabase_client.insert_rows("news", [data])
                conn.execute("UPDATE staged_news SET status='synced' WHERE id=?", (r["id"],))
                conn.commit()
                synced += 1
                print(f"✓ Berhasil sync artikel ke Supabase: [{slug}]")
            except Exception as e:
                print(f"✗ Gagal sync [{slug}]: {e}")
        return synced

def publish_article_data():
    print("=" * 60)
    print(" PUBLIKASI ARTIKEL BERITA TREN KE SUPABASE")
    print("=" * 60)
    print(f"Judul : {ARTICLE_DATA['title']}")
    print(f"Slug  : {ARTICLE_DATA['slug']}")
    print(f"Gambar: {ARTICLE_DATA['image_url']}")

    # Cek apakah artikel sudah ada di Supabase
    existing = supabase_client.query_rows("news", f"select=slug&slug=eq.{ARTICLE_DATA['slug']}")
    if existing:
        print("\n✓ Artikel ini sudah ada di database Supabase!")
        return

    try:
        supabase_client.insert_rows("news", [ARTICLE_DATA])
        print("\n🚀 BERHASIL! Artikel berhasil di-upload dan dipublikasikan langsung ke Supabase!")
    except Exception as e:
        print(f"\n[DEBUG ERROR DETAIL]: {e}")
        err = str(e).lower()
        if "row-level security" in err or "401" in err or "403" in err:
            print("\n⚠️ Supabase RLS aktif (kunci Anon tidak diizinkan INSERT).")
            print("Menyimpan artikel ke Staging Database Lokal (SQLite)...")
            now_str = datetime.now(timezone.utc).isoformat()
            with local_db.get_connection() as conn:
                conn.execute("""
                INSERT OR REPLACE INTO staged_news (slug, data_json, status, created_at)
                VALUES (?, ?, 'staged', ?)
                """, (ARTICLE_DATA["slug"], json.dumps(ARTICLE_DATA), now_str))
                conn.commit()
            print("✓ Disimpan di staging lokal. Akan di-sync otomatis via GitHub Actions Runner yang memiliki SERVICE ROLE KEY.")
        else:
            print(f"\n❌ Gagal upload: {e}")
            raise

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--sync-staged":
        count = sync_staged_news_records()
        print(f"Total synced from SQLite: {count}")

    publish_article_data()

if __name__ == "__main__":
    main()
