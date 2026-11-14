# InfoLokerKita AI Company — Autonomous AI Employee System

Sistem operasional perusahaan digital berbasis AI mandiri untuk portal [infolokerkita.web.id](https://infolokerkita.web.id).

- **Pemilik Perusahaan (CEO):** Human Founder (Anda)
- **Direktur Operasional (COO):** AI Manager
- **Struktur Operasional:** 8 Divisi AI fungsional nyata

---

## 🏛️ Struktur Organisasi AI

1. **AI Manager (Direktur Operasional):** Pusat koordinasi, pendelegasian tugas, monitoring proses, validasi hasil, dan pelaporan langsung kepada CEO.
2. **AI Recruitment:** Mencari dan mengkurasi lowongan terpercaya dari Karirhub Kemnaker dan portal resmi perusahaan.
3. **AI Verification:** Verifikator legalitas, anti-fraud, keabsahan domain perusahaan, dan batas tanggal lamaran.
4. **AI Newsroom:** Periset berita primer ekonomi dan industri (ANTARA News, Kemnaker) dan penyusun artikel faktual terstruktur.
5. **AI SEO Specialist:** Optimasi keyword, heading, metadata (Title/Description), dan internal linking.
6. **AI Designer:** Penelusur logo resmi perusahaan dan pembuat thumbnail artikel 16:9 orisinal di `public/images/berita/`.
7. **AI Data Manager:** Manajer integrasi Supabase (tabel `jobs` dan `news`), deduplikasi slug, dan penanganan RLS.
8. **AI Marketing:** Pembuat copy promosi multi-platform (Facebook, WhatsApp, Telegram, LinkedIn) dan kalender konten.
9. **AI Auditor:** Auditor integritas sistem, pendeteksi link 404, lowongan kedaluwarsa, dan pelapor anomali.

---

## 🖥️ Akses AI Headquarters Dashboard (CEO)

Dashboard antarmuka khusus CEO dibangun terintegrasi di website:

- **URL Dashboard:** `http://localhost:4321/hq/` (saat local dev) atau `https://infolokerkita.web.id/hq/` (setelah deploy).
- **Autentikasi CEO:** Dilindungi PIN keamanan (default: `infoloker2026`, dapat diubah di `.env` dengan variabel `CEO_SECRET_PIN`).
- **13 Modul Dashboard:**
  1. *Overview:* KPI data real Supabase, status sistem, antrean tugas terbaru.
  2. *AI Employees:* Kartu status dan kinerja 9 divisi AI.
  3. *Recruitment Department:* Kontrol manual scraper dan kurasi lowongan.
  4. *Newsroom Department:* Riset berita primer dan generator artikel berita.
  5. *SEO Department:* Audit dan panduan optimasi SEO on-page.
  6. *Design Department:* Galeri thumbnail 16:9 dan resolusi logo.
  7. *Data Management:* Penjelajah data live Supabase dan pembersih lowongan kedaluwarsa.
  8. *Marketing Department:* Generator draf promosi dan kalender medsos.
  9. *AI Auditor:* Pemeriksaan kesehatan link dan log error 24 jam.
  10. *Task Management:* Antrean koordinasi tugas antar-agen secara real-time.
  11. *Automation Center:* Kontrol siklus otomatis 05:00, 07:00, dan 08:00 WIB.
  12. *Financial Reports:* Laporan potensi AdSense dan slot iklan sponsor.
  13. *System Settings:* Ringkasan konfigurasi sistem dan parameter biaya AI.

---

## ⚡ Perintah Terminal CEO (CLI)

Anda dapat memberikan instruksi langsung kepada AI Manager melalui terminal:

```bash
# 1. Cek status live sistem, database Supabase, dan seluruh divisi AI
python -m automation.ai_company.cli status

# 2. Instruksikan AI Manager untuk menyusun Laporan Operasional Harian
python -m automation.ai_company.cli report

# 3. Berikan perintah bebas dalam bahasa alami ke AI Manager
python -m automation.ai_company.cli exec "Cari 10 loker operator produksi"
python -m automation.ai_company.cli exec "Buat 1 draf artikel berita industri terbaru"
python -m automation.ai_company.cli exec "Buat materi promosi dan kalender marketing"

# 4. Jalankan siklus otomasi manual
python -m automation.ai_company.cli run 0500   # Siklus 05.00 WIB (Loker)
python -m automation.ai_company.cli run 0700   # Siklus 07.00 WIB (Berita)
python -m automation.ai_company.cli run 0800   # Siklus 08.00 WIB (Audit & Report)
python -m automation.ai_company.cli run all    # Jalankan seluruh siklus

# 5. Jalankan server background API daemon untuk dashboard
python -m automation.ai_company.cli server
```

---

## ⏰ Jadwal Otomasi (GitHub Actions)

File workflow terpasang di `.github/workflows/ai-company.yml` dengan jadwal otomatis:

- **05:00 WIB (22:00 UTC):** AI Recruitment -> AI Verification -> AI Data Manager
- **07:00 WIB (00:00 UTC):** AI Newsroom -> AI SEO Specialist -> AI Designer
- **08:00 WIB (01:00 UTC):** AI Auditor -> AI Manager (Penyusunan Laporan Harian)

Workflow ini juga mendukung **Manual Trigger (`workflow_dispatch`)** langsung dari menu Actions di GitHub repository.

---

## 🔒 Konfigurasi & Keamanan Environment

Semua kredensial tersimpan aman di `.env` (tidak pernah diekspos ke publik):

```env
PUBLIC_SUPABASE_URL=https://ucxwxmasnbidzofuoqks.supabase.co
PUBLIC_SUPABASE_ANON_KEY=...
# Opsional untuk izin insert langsung dari mesin lokal:
SUPABASE_SERVICE_ROLE_KEY=...
# Opsional untuk model bahasa eksternal (sistem otomatis fallback jika kosong):
GEMINI_API_KEY=...
# PIN Akses CEO Dashboard:
CEO_SECRET_PIN=infoloker2026
```
