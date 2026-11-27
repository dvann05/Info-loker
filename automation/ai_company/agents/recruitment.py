import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple
from automation.ai_company.core.config import PROJECT_ROOT
from automation.ai_company.core.database import local_db, supabase_client

API_KARIRHUB = "https://api.kemnaker.go.id/karirhub/vacancy/v2/published-industrial-vacancies"
REGION_FILE = PROJECT_ROOT / "automation" / "data" / "karirhub_regions.json"

# Daftar perusahaan bonafit / multinasional / manufaktur besar / BUMN / Tbk prioritas utama
BONAFIDE_BRANDS = (
    "mattel", "epson", "yamaha", "honda", "toyota", "astra", "daihatsu", "suzuki",
    "mitsubishi", "hino", "kawasaki", "denso", "aisin", "panasonic", "samsung",
    "lg electronics", "sony", "sharp", "canon", "omron", "schneider", "siemens",
    "bosch", "hitachi", "bridgestone", "goodyear", "hankook", "gajah tunggal",
    "unilever", "indofood", "mayora", "wings", "nestle", "danone", "kalbe",
    "dexa medica", "bio farma", "kimia farma", "pertamina", "pln", "telkom",
    "bank mandiri", "bri", "bni", "bca", "btn", "freeport", "vale", "antam",
    "bukit asam", "krakatau steel", "semen indonesia", "gudang garam", "djarum",
    "sampoerna", "sinarmas", "sinar mas", "wilmar", "charoen pokphand", "japfa",
    "paragon", "alfamart", "indomarco", "indomaret", "jne", "pos indonesia",
    "garuda indonesia", "kereta api", "pelindo", "angkasa pura", "pupuk indonesia",
    "pindad", "dirgantara indonesia", "pal indonesia", "komatsu", "united tractors",
    "pamapersada", "adaro", "medco", "chandra asri", "barito", "hyundai", "wuling",
    "byd", "michelin", "yazaki", "sumitomo", "kyb", "kayaba", "showa", "ntn",
    "nsk", "nikon", "fujitsu", "toshiba", "daikin", "sanyo", "polytron", "miyako",
    "chiyoda", "jfe", "nippon", "mitsui", "marubeni", "itochu", "ajinomoto",
    "yakult", "pocari", "amerta indah otsuka", "otsuka", "kao", "shiseido",
    "l'oreal", "loreal", "procter", "p&g", "reckitt", "mondelez", "kraft",
    "coca-cola", "pepsico", "frisian flag", "ultramilk", "ultrajaya", "garudafood",
    "nabati", "kaldu sari nabati", "sido muncul", "combiphar", "sanbe", "soho",
    "nutrifood", "torabika", "kapal api", "santos jaya", "tirta investama",
    "aqua", "cleopure", "mandom", "kino", "unicharm", "softex", "kimberly",
    "app sinarmas", "indah kiat", "pabrik kertas tjiwi", "april group", "riau andalan",
    "muliaglass", "asahimas", "nippon paint", "avian", "dulux", "akzonobel",
    "holcim", "indocement", "solusi bangun", "wijaya karya", "wika", "adhi karya",
    "pp persero", "hutama karya", "waskita", "jasa marga", "pegadaian", "taspen",
    "bpjs", "asuransi jasindo", "bumn",
)

BONAFIDE_CORPORATE_KEYWORDS = (
    "tbk", "persero", "manufacturing", "motor", "electronics", "precision",
    "industrial", "industries", "automotive", "pharma", "pharmaceutical",
    "chemical", "steel", "energy", "mining", "logistics", "telekomunikasi",
    "bank ", "perbankan", "asuransi", "teknologi", "semiconductor", "automation",
)

EXCLUDED_SMALL_ENTITIES = (
    "cv ", "cv.", "ud ", "ud.", "toko ", "warung ", "kedai ", "kios ",
    "warkop", "laundry", "barbershop", "salon ", "counter ", "konter ",
    "outlet ", "umkm", "perorangan", "rumahan",
)


class AIRecruitmentAgent:
    """Divisi AI Recruitment: Mencari 3-5 lowongan perusahaan bonafit/besar dari Karirhub & sumber resmi."""

    def __init__(self):
        self.name = "ai_recruitment"
        self.role = "Spesialis Rekrutmen & Kurasi Loker Bonafit"
        self._regions_cache: Dict[str, Dict[str, str]] = {}

    @staticmethod
    def score_bonafide_company(company_name: str, item: Dict[str, Any]) -> Tuple[int, str]:
        """Menilai bobot/bonafiditas perusahaan secara deterministik (hemat token AI)."""
        name_clean = str(company_name or "").strip()
        lower = name_clean.lower()

        if not name_clean:
            return 0, "empty"

        for excl in EXCLUDED_SMALL_ENTITIES:
            if lower.startswith(excl) or f" {excl}" in lower:
                return 0, "small_entity"

        score = 0
        tier = "standard"

        # Prioritas 1: Brand multinasional / perusahaan besar / BUMN ternama
        for brand in BONAFIDE_BRANDS:
            if brand in lower:
                score += 100
                tier = "tier1_major_brand"
                break

        # Prioritas 2: Entitas PT / Tbk / Persero / Industri besar
        if lower.startswith("pt ") or lower.startswith("pt.") or " pt " in lower:
            score += 20
        if "tbk" in lower or "(persero)" in lower or "persero" in lower:
            score += 45
            if tier == "standard":
                tier = "tier1_tbk_bumn"

        for kw in BONAFIDE_CORPORATE_KEYWORDS:
            if kw in lower:
                score += 15
                if tier == "standard":
                    tier = "tier2_industrial_corp"
                break

        # Bonus jika punya logo resmi & kuota/gaji jelas
        if item.get("company_logo_uri"):
            score += 10
        if item.get("min_salary_amount") or item.get("max_salary_amount"):
            score += 5

        return score, tier

    def _load_regions(self) -> Dict[str, Dict[str, str]]:
        if self._regions_cache:
            return self._regions_cache
        try:
            with open(REGION_FILE, encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    self._regions_cache = data
        except Exception as exc:
            local_db.log(self.name, f"Gagal memuat karirhub_regions.json: {exc}", level="WARN")
        return self._regions_cache

    def _resolve_location(self, item: Dict[str, Any]) -> Tuple[str, str]:
        city = str(item.get("city_name") or "").strip()
        province = str(item.get("province_name") or "").strip()

        if not city or not province:
            regions = self._load_regions()
            for entry in item.get("locations") or []:
                if not isinstance(entry, str):
                    continue
                region_id = entry.split(":", 1)[1].strip() if entry.startswith("city:") else entry.strip()
                region = regions.get(region_id)
                if isinstance(region, dict):
                    if not city and region.get("city"):
                        city = str(region["city"]).strip()
                    if not province and region.get("province"):
                        province = str(region["province"]).strip()
                    if city and province:
                        break

        return (
            city or "Lokasi belum dicantumkan",
            province or "Belum dicantumkan",
        )

    def fetch_karirhub_page(self, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{API_KARIRHUB}?page={page}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 InfoLoker/2.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("data") or []
        except Exception as e:
            local_db.log(self.name, f"Gagal mengambil data Karirhub hal {page}: {e}", level="WARN")
            return []

    def get_existing_records(self) -> Tuple[set, set]:
        """Mengambil seluruh slug dan pasangan (judul, perusahaan) yang sudah ada untuk mencegah duplikasi."""
        slugs = set()
        pairs = set()
        offset = 0
        page_size = 1000

        try:
            while True:
                query = urllib.parse.urlencode({
                    "select": "slug,title,company_name",
                    "order": "created_at.desc",
                    "limit": page_size,
                    "offset": offset,
                })
                rows = supabase_client.query_rows("jobs", query)
                if not rows:
                    break
                for r in rows:
                    if r.get("slug"):
                        slugs.add(r["slug"])
                    if r.get("title") and r.get("company_name"):
                        pairs.add((
                            re.sub(r"[^a-z0-9]", "", str(r["title"]).lower()),
                            re.sub(r"[^a-z0-9]", "", str(r["company_name"]).lower()),
                        ))
                if len(rows) < page_size:
                    break
                offset += len(rows)
            return slugs, pairs
        except Exception as e:
            local_db.log(self.name, f"Gagal memuat data eksisting: {e}", level="WARN")
            return slugs, pairs

    def discover_vacancies(self, target_count: int = 5, max_pages: int = 12) -> Dict[str, Any]:
        """Menjalankan pencarian lowongan kerja khusus perusahaan bonafit/berbobot (3-5 loker/hari, hemat AI)."""
        start_time = time.time()
        safe_target = max(3, min(int(target_count or 5), 5))
        local_db.log(self.name, f"Memulai pencarian lowongan perusahaan bonafit (target: {safe_target}, max hal: {max_pages})...")

        existing_slugs, existing_pairs = self.get_existing_records()
        scored_candidates: List[Tuple[int, Dict[str, Any]]] = []
        skipped_duplicate = 0
        skipped_non_bonafide = 0
        pages_checked = 0
        company_batch_counts: Dict[str, int] = {}

        for page in range(1, max_pages + 1):
            pages_checked += 1
            items = self.fetch_karirhub_page(page=page, limit=25)
            if not items:
                break

            for item in items:
                title = str(item.get("title") or "").strip()
                company = str(item.get("company_name") or "").strip()
                job_id = str(item.get("id") or "").strip()

                if not title or not company or not job_id:
                    continue

                # 0. Filter ketat perusahaan bonafit / berbobot (minimal skor 35: PT + industri/Tbk/brand besar)
                bonafide_score, bonafide_tier = self.score_bonafide_company(company, item)
                if bonafide_score < 35:
                    skipped_non_bonafide += 1
                    continue

                norm_title = re.sub(r"[^a-z0-9]", "", title.lower())
                norm_company = re.sub(r"[^a-z0-9]", "", company.lower())
                pair_key = (norm_title, norm_company)

                # 1. Anti-Flood: Maksimal 1 lowongan per perusahaan dalam batch harian 3-5 loker agar variatif
                if company_batch_counts.get(norm_company, 0) >= 1:
                    skipped_duplicate += 1
                    continue

                # 2. Anti-Duplicate: Jika judul dan perusahaan yang sama persis sudah ada di database
                if pair_key in existing_pairs:
                    skipped_duplicate += 1
                    continue

                raw_slug = f"{title}-{company}".lower()
                clean_slug = re.sub(r"[^a-z0-9]+", "-", raw_slug).strip("-") + f"-{job_id}"

                if clean_slug in existing_slugs:
                    skipped_duplicate += 1
                    continue

                city, province = self._resolve_location(item)

                company_batch_counts[norm_company] = company_batch_counts.get(norm_company, 0) + 1
                existing_pairs.add(pair_key)
                existing_slugs.add(clean_slug)

                scored_candidates.append((bonafide_score, {
                    "raw_id": job_id,
                    "title": title,
                    "company_name": company,
                    "company_logo_uri": item.get("company_logo_uri"),
                    "city": city,
                    "province": province,
                    "job_type": item.get("job_type_name") or "Full-time",
                    "platform_link": item.get("platform_link"),
                    "min_salary": item.get("min_salary_amount"),
                    "max_salary": item.get("max_salary_amount"),
                    "published_at": item.get("published_at"),
                    "expires_at": item.get("expires_at"),
                    "skills": item.get("skills") or [],
                    "job_function": item.get("job_function_name"),
                    "industry": item.get("industry_name"),
                    "quota": item.get("available_quota") or item.get("quota"),
                    "slug": clean_slug,
                    "bonafide_score": bonafide_score,
                    "bonafide_tier": bonafide_tier,
                }))

            # Jika sudah terkumpul minimal 2x target perusahaan tier-1, hentikan scan lebih awal
            tier1_found = sum(1 for sc, _ in scored_candidates if sc >= 100)
            if tier1_found >= safe_target:
                break

        # Urutkan dari perusahaan paling berbobot/bonafit, ambil tepat 3-5 terbaik
        scored_candidates.sort(key=lambda pair: pair[0], reverse=True)
        discovered = [cand for _, cand in scored_candidates[:safe_target]]

        duration = round(time.time() - start_time, 2)
        local_db.log(
            self.name,
            f"Pencarian loker bonafit selesai dalam {duration}s. Dipilih {len(discovered)} loker terbaik, "
            f"{skipped_non_bonafide} non-bonafit disaring, {skipped_duplicate} duplikat diabaikan."
        )

        return {
            "status": "success",
            "candidates_found": len(discovered),
            "skipped_non_bonafide": skipped_non_bonafide,
            "skipped_duplicates": skipped_duplicate,
            "pages_scanned": pages_checked,
            "duration_seconds": duration,
            "candidates": discovered,
        }


ai_recruitment = AIRecruitmentAgent()
