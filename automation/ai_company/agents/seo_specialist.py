import re
from typing import Dict, Any, List
from automation.ai_company.core.database import local_db

STOPWORDS_ID = {
    "yang", "di", "dan", "dari", "ke", "ini", "itu", "untuk", "pada", "adalah", "dengan",
    "sebagai", "oleh", "dalam", "akan", "dapat", "bagi", "secara", "atau", "juga", "tersebut"
}

class AISEOSpecialistAgent:
    """Divisi AI SEO Specialist: Optimasi metadata, keyword, heading, dan internal link."""

    def __init__(self):
        self.name = "ai_seo_specialist"
        self.role = "Spesialis Optimasi SEO & Metadata"

    def extract_keywords(self, title: str, content: str) -> Dict[str, Any]:
        """Ekstraksi keyword utama dan sekunder tanpa keyword stuffing."""
        words = re.findall(r"\b[a-zA-Z]{4,}\b", f"{title} {content}".lower())
        filtered = [w for w in words if w not in STOPWORDS_ID]

        counts = {}
        for w in filtered:
            counts[w] = counts.get(w, 0) + 1

        sorted_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_words[0][0] if sorted_words else "lowongan"
        secondary = [w for w, c in sorted_words[1:6]]

        return {
            "primary_keyword": primary,
            "secondary_keywords": secondary,
            "keyword_density_ok": True
        }

    def generate_meta_tags(self, title: str, category: str, primary_kw: str) -> Dict[str, str]:
        """Membuat meta title dan description yang ramah mesin pencari."""
        # Meta title ideally 50-60 chars
        meta_title = f"{title[:50]} | Info Loker Kita"

        # Meta description ideally 140-160 chars
        meta_description = (
            f"Informasi lengkap {title[:60]} kualifikasi, rincian industri {category}, "
            f"dan panduan resmi terpercaya di InfoLokerKita."
        )[:160]

        return {
            "meta_title": meta_title,
            "meta_description": meta_description
        }

    def generate_internal_links(self, category: str) -> List[Dict[str, str]]:
        """Memberikan rekomendasi tautan internal yang relevan."""
        links = [
            {"anchor": "Daftar Lowongan Kerja Terbaru", "url": "/lowongan/"},
            {"anchor": "Berita & Perkembangan Industri", "url": "/berita/"}
        ]
        if "Industri" in category:
            links.append({"anchor": "Lowongan Sektor Manufaktur & Pabrik", "url": "/lowongan/?kategori=manufaktur"})
        elif "Karier" in category:
            links.append({"anchor": "Tips Menghadapi Interview & Kerja", "url": "/berita/"})
        return links

    def optimize_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Audit dan optimasi SEO menyeluruh pada artikel berita."""
        title = article.get("title", "")
        content = article.get("content", "")
        category = article.get("category", "Dunia Kerja")

        kw_data = self.extract_keywords(title, content)
        meta = self.generate_meta_tags(title, category, kw_data["primary_keyword"])
        links = self.generate_internal_links(category)

        # Append internal link recommendation to content footer if not present
        optimized_content = content
        if "Tautan Rekomendasi Terkait" not in optimized_content:
            optimized_content += "\n\n**Tautan Rekomendasi Terkait:**\n"
            for link in links:
                optimized_content += f"- [{link['anchor']}]({link['url']})\n"

        article["content"] = optimized_content
        article["meta_title"] = meta["meta_title"]
        article["meta_description"] = meta["meta_description"]
        article["seo_keywords"] = [kw_data["primary_keyword"]] + kw_data["secondary_keywords"]

        local_db.log(self.name, f"Optimasi SEO selesai untuk artikel: {title[:40]}...")
        return article

    def audit_job_seo(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Audit SEO lowongan kerja."""
        title = job.get("title", "")
        company = job.get("company_name", "")
        location = job.get("location", "")
        return {
            "title_tag": f"Lowongan {title} di {company} ({location}) — Info Loker Kita",
            "meta_description": f"Daftar lowongan kerja {title} di {company}, {location}. Simak persyaratan, gaji, dan lamar resmi sekarang.",
            "canonical_slug": job.get("slug", "")
        }


ai_seo_specialist = AISEOSpecialistAgent()
