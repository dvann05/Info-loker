import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from automation.ai_company.core.database import supabase_client, local_db
from automation.ai_company.core.llm import llm_engine

NEWS_FEEDS = [
    {
        "name": "ANTARA News Ekonomi & Bisnis",
        "url": "https://www.antaranews.com/rss/ekonomi-bisnis.xml",
        "category": "Industri & Manufaktur"
    },
    {
        "name": "ANTARA News Tekno & Industri",
        "url": "https://www.antaranews.com/rss/tekno.xml",
        "category": "Teknologi Industri"
    },
    {
        "name": "ANTARA News Terkini",
        "url": "https://www.antaranews.com/rss/terkini.xml",
        "category": "Industri & Ketenagakerjaan"
    }
]

INDUSTRY_KEYWORDS = (
    "industri", "manufaktur", "pabrik", "investasi", "ekspor", "otomotif",
    "elektronik", "kawasan industri", "hilirisasi", "tenaga kerja", "pekerja",
    "buruh", "kemnaker", "kemenperin", "bumn", "korporasi", "perusahaan",
    "produksi", "logistik", "energi", "tambang", "smelter", "tekstil",
    "farmasi", "pangan", "semikonduktor", "baterai", "kendaraan listrik",
    "ekonomi", "bisnis", "lowongan", "rekrutmen", "upah", "ump", "umk",
    "pelabuhan", "infrastruktur", "digital", "ai", "otomatisasi",
)

class AINewsroomAgent:
    """Divisi AI Newsroom: Riset berita industri berbobot (3x/hari: Pagi, Siang, Sore) + SEO hemat AI."""

    def __init__(self):
        self.name = "ai_newsroom"
        self.role = "Editor Berita Industri & SEO"

    @staticmethod
    def _is_industry_relevant(title: str, desc: str) -> bool:
        text = f"{title} {desc}".lower()
        return any(kw in text for kw in INDUSTRY_KEYWORDS)

    def fetch_primary_news_feed(self, max_items: int = 12) -> List[Dict[str, Any]]:
        """Mengambil berita khusus seputar industri dari sumber primer RSS kredibel."""
        industry_items: List[Dict[str, Any]] = []
        fallback_items: List[Dict[str, Any]] = []
        for feed in NEWS_FEEDS:
            try:
                req = urllib.request.Request(
                    feed["url"],
                    headers={"User-Agent": "Mozilla/5.0 (compatible; InfoLokerNewsBot/1.0)"}
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    xml_content = resp.read()
                    root = ET.fromstring(xml_content)

                    channel = root.find("channel")
                    if channel is not None:
                        for item in channel.findall("item"):
                            title_el = item.find("title")
                            link_el = item.find("link")
                            desc_el = item.find("description")
                            pub_el = item.find("pubDate")

                            title = title_el.text.strip() if title_el is not None and title_el.text else ""
                            link = link_el.text.strip() if link_el is not None and link_el.text else ""
                            desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
                            clean_desc = re.sub(r"<[^>]+>", "", desc).strip()

                            if title and link:
                                record = {
                                    "title": title,
                                    "source_url": link,
                                    "source_name": feed["name"],
                                    "category": feed["category"],
                                    "raw_summary": clean_desc,
                                    "published_at": pub_el.text if pub_el is not None and pub_el.text else ""
                                }
                                if self._is_industry_relevant(title, clean_desc):
                                    industry_items.append(record)
                                elif len(fallback_items) < max_items:
                                    fallback_items.append(record)
                            if len(industry_items) >= max_items:
                                break
            except Exception as e:
                local_db.log(self.name, f"Gagal membaca feed {feed['name']}: {e}", level="WARN")

            if len(industry_items) >= max_items:
                break

        return industry_items if industry_items else fallback_items

    def get_existing_news_records(self) -> tuple:
        try:
            rows = supabase_client.query_rows("news", "select=slug,title&order=published_at.desc&limit=200")
            slugs = {r["slug"] for r in rows if r.get("slug")}
            titles = {re.sub(r"[^a-z0-9]", "", str(r["title"]).lower()) for r in rows if r.get("title")}
            return slugs, titles
        except Exception:
            return set(), set()

    def _compose_seo_industry_content(self, title: str, raw_summary: str, source_name: str, category: str) -> str:
        """Menyusun artikel berita industri berbobot & SEO-friendly dengan 1 panggilan AI hemat token (atau fallback)."""
        if llm_engine.api_key:
            system_prompt = (
                "Anda adalah jurnalis senior ekonomi & industri Indonesia yang ahli SEO. "
                "Tulis artikel berita industri berbahasa Indonesia yang faktual, berbobot, objektif, "
                "tanpa halusinasi, dengan struktur Markdown (H2/H3), kata kunci alami, dan analisis dampak bagi dunia kerja."
            )
            user_prompt = (
                f"Susun 1 artikel berita industri berbobot (450-650 kata) berdasarkan fakta primer berikut:\n"
                f"- Judul rujukan: {title}\n"
                f"- Ringkasan fakta: {raw_summary or title}\n"
                f"- Sumber: {source_name}\n"
                f"- Kategori: {category}\n\n"
                "Format wajib:\n"
                "1. Paragraf pembuka kuat mengandung kata kunci utama.\n"
                "2. ## Fakta Utama & Konteks Industri (poin terstruktur, hanya fakta dari rujukan).\n"
                "3. ## Dampak bagi Sektor Industri & Peluang Kerja di Indonesia.\n"
                "4. ## Strategi & Kesiapan Talenta Kerja (3 langkah praktis).\n"
                "5. Catatan singkat bahwa Info Loker Kita 100% gratis tanpa pungutan.\n"
                "Jangan mengarang angka atau kutipan baru yang tidak ada di fakta."
            )
            generated = llm_engine.generate(user_prompt, system_instruction=system_prompt, temperature=0.25)
            if generated and len(generated) > 350 and "Tugas berhasil diproses" not in generated:
                return generated.strip()

        # Fallback deterministik berbobot & SEO-friendly (0 token AI)
        return f"""
Perkembangan terbaru di sektor **{category.lower()}** Indonesia kembali menjadi sorotan pelaku usaha dan pencari kerja nasional. Mengutip laporan resmi dari **{source_name}**, dinamika mengenai *{title}* mencerminkan arah pertumbuhan industri nasional yang terus beradaptasi terhadap tuntutan efisiensi, investasi, dan kebutuhan sumber daya manusia kompeten.

## Fakta Utama & Konteks Industri

- **Inti Perkembangan:** {raw_summary or title}
- **Sektor Terkait:** {category}, manufaktur, dan ekosistem ketenagakerjaan Indonesia.
- **Sumber Rujukan Primer:** {source_name} (terverifikasi).

## Dampak bagi Sektor Industri & Peluang Kerja di Indonesia

Setiap pergerakan pada sektor industri dan korporasi besar berdampak langsung terhadap rantai pasok, produktivitas pabrik, hingga penyerapan tenaga kerja di kawasan industri utama seperti Cikarang, Karawang, Bekasi, Tangerang, Surabaya, dan Batam. Perusahaan bonafit umumnya membuka peluang karier pada lini operasional, teknik pemeliharaan, quality control (QC), logistik, serta administrasi industri seiring penguatan kapasitas bisnis.

## Strategi & Kesiapan Talenta Kerja

Bagi pencari kerja dan profesional yang ingin menangkap peluang di sektor industri nasional:
1. **Perkuat Kompetensi Teknis & Sertifikasi:** Lengkapi CV dengan pengalaman operasional, keselamatan kerja (K3), atau keahlian digital manufaktur.
2. **Pantau Portal Rekrutmen Resmi:** Selalu verifikasi lowongan kerja perusahaan bonafit melalui kanal resmi atau portal tepercaya.
3. **Waspada Penipuan Rekrutmen:** Perusahaan resmi tidak pernah memungut biaya seleksi, transportasi, atau administrasi dalam bentuk apa pun.

**Catatan Redaksi Info Loker Kita:** Artikel berita industri ini disusun secara faktual merujuk pada {source_name}. Info Loker Kita menyajikan informasi lowongan kerja dan berita industri 100% gratis tanpa pungutan biaya.
""".strip()

    def generate_article_draft(self, news_item: Dict[str, Any]) -> Dict[str, Any]:
        """Menyusun artikel berita industri berbobot & ramah SEO."""
        title = news_item.get("title", "")
        source_name = news_item.get("source_name", "Media Nasional Terpercaya")
        source_url = news_item.get("source_url", "")
        category = news_item.get("category", "Industri & Manufaktur")
        raw_summary = news_item.get("raw_summary", "")

        clean_text = re.sub(r"[^a-zA-Z0-9\s]", "", title).lower()
        words = clean_text.split()[:8]
        slug = "-".join(words) + f"-{int(datetime.now().timestamp()) % 100000}"

        excerpt = raw_summary[:180] + ("..." if len(raw_summary) > 180 else "")
        if not excerpt:
            excerpt = f"Analisis dan berita industri terbaru seputar {title} berdasarkan rujukan resmi {source_name}."

        content = self._compose_seo_industry_content(title, raw_summary, source_name, category)
        now_iso = datetime.now(timezone.utc).isoformat()

        article = {
            "slug": slug,
            "title": title,
            "excerpt": excerpt,
            "content": content,
            "image_url": "https://infolokerkita.web.id/favicon.svg",
            "image_alt": f"Berita industri Indonesia: {title}",
            "category": category,
            "source_name": source_name,
            "source_url": source_url,
            "status": "published",
            "is_featured": False,
            "published_at": now_iso
        }

        local_db.log(self.name, f"Draft berita industri SEO berhasil disusun: [{slug}] {title}")
        return article

    def conduct_research_and_draft(self, count: int = 1) -> Dict[str, Any]:
        """Melakukan riset berita industri (default 1 artikel per slot pagi/siang/sore untuk hemat AI)."""
        feed_items = self.fetch_primary_news_feed(max_items=max(8, count * 4))
        existing_slugs, existing_titles = self.get_existing_news_records()

        drafts = []
        for item in feed_items:
            norm_title = re.sub(r"[^a-z0-9]", "", item.get("title", "").lower())
            if norm_title in existing_titles:
                continue
            draft = self.generate_article_draft(item)
            if draft["slug"] not in existing_slugs:
                drafts.append(draft)
                existing_titles.add(norm_title)
                existing_slugs.add(draft["slug"])
                if len(drafts) >= count:
                    break

        return {
            "status": "success",
            "articles_drafted": len(drafts),
            "drafts": drafts
        }


ai_newsroom = AINewsroomAgent()
