import os
import re
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional
from automation.ai_company.core.config import PUBLIC_IMAGES_DIR
from automation.ai_company.core.database import local_db

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class AIDesignerAgent:
    """Divisi AI Designer: Resolusi logo perusahaan dan pembuatan thumbnail berita 16:9."""

    def __init__(self):
        self.name = "ai_designer"
        self.role = "Desainer Grafis & Aset Visual"
        PUBLIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    def resolve_company_logo(self, company_name: str, official_domain: Optional[str] = None) -> str:
        """Mengambil URL logo/favicon resmi perusahaan, bukan logo agregator."""
        if not official_domain:
            # Saring nama perusahaan untuk tebakan domain yang masuk akal
            clean_name = re.sub(r"\b(pt|tbk|persero|indonesia|group)\b", "", company_name.lower())
            clean_name = re.sub(r"[^a-z0-9]", "", clean_name).strip()
            if clean_name:
                official_domain = f"{clean_name}.co.id"
            else:
                official_domain = "infolokerkita.web.id"

        return f"https://www.google.com/s2/favicons?domain={official_domain}&sz=128"

    def create_news_thumbnail_svg(self, slug: str, title: str, category: str = "Dunia Kerja") -> str:
        """Membuat thumbnail berita rasio 16:9 dalam format SVG modern dan tajam."""
        filename = f"{slug}.svg"
        target_path = PUBLIC_IMAGES_DIR / filename

        # Escape special XML chars
        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        safe_title = escape_xml(title)
        safe_cat = escape_xml(category)

        # Wrap title words into max 3 lines
        words = safe_title.split()
        lines = []
        cur_line = []
        for w in words:
            if len(" ".join(cur_line + [w])) <= 34:
                cur_line.append(w)
            else:
                if cur_line:
                    lines.append(" ".join(cur_line))
                cur_line = [w]
        if cur_line:
            lines.append(" ".join(cur_line))
        lines = lines[:3]

        svg_lines = ""
        y_offset = 320
        for i, line in enumerate(lines):
            svg_lines += f'<text x="80" y="{y_offset + (i * 68)}" font-family="system-ui, -apple-system, sans-serif" font-size="46" font-weight="bold" fill="#ffffff">{line}</text>\n'

        svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0b0f19" />
      <stop offset="100%" stop-color="#050811" />
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="100%" stop-color="#22c55e" />
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="1280" height="720" fill="url(#bg)" />

  <!-- Grid decoration lines -->
  <line x1="80" y1="0" x2="80" y2="720" stroke="#1f293d" stroke-width="1" stroke-opacity="0.4" />
  <line x1="1200" y1="0" x2="1200" y2="720" stroke="#1f293d" stroke-width="1" stroke-opacity="0.4" />
  <line x1="0" y1="120" x2="1280" y2="120" stroke="#1f293d" stroke-width="1" stroke-opacity="0.4" />
  <line x1="0" y1="620" x2="1280" y2="620" stroke="#1f293d" stroke-width="1" stroke-opacity="0.4" />

  <!-- Top bar accent -->
  <rect x="0" y="0" width="1280" height="6" fill="url(#accent)" />

  <!-- Category badge -->
  <rect x="80" y="160" width="220" height="44" rx="22" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5" />
  <text x="190" y="188" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="600" fill="#38bdf8" text-anchor="middle">{safe_cat}</text>

  <!-- Title Text -->
  {svg_lines}

  <!-- Footer Branding -->
  <text x="80" y="650" font-family="system-ui, -apple-system, sans-serif" font-size="20" font-weight="700" fill="#64748b">
    INFOLOKERKITA <tspan fill="#38bdf8">MEDIA</tspan>
  </text>
  <text x="1200" y="650" font-family="system-ui, -apple-system, sans-serif" font-size="18" fill="#475569" text-anchor="end">
    infolokerkita.web.id
  </text>
</svg>"""

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        local_db.log(self.name, f"Thumbnail SVG 16:9 berhasil dibuat: {filename}")
        return f"/images/berita/{filename}"

    def generate_thumbnail_for_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Membuat aset gambar 16:9 untuk artikel dan memasangkan path-nya."""
        slug = article.get("slug", "berita-terbaru")
        title = article.get("title", "Informasi Dunia Kerja")
        cat = article.get("category", "Dunia Kerja")

        img_url = self.create_news_thumbnail_svg(slug, title, cat)
        article["image_url"] = img_url
        article["image_alt"] = f"Ilustrasi {title} — Info Loker Kita"
        return article


ai_designer = AIDesignerAgent()
