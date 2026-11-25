import os
from datetime import timedelta, timezone
from pathlib import Path
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AI_COMPANY_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = AI_COMPANY_ROOT / "data"
REPORTS_DIR = AI_COMPANY_ROOT / "reports"
PUBLIC_IMAGES_DIR = PROJECT_ROOT / "public" / "images" / "berita"

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
PUBLIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Zona waktu standar operasional Indonesia Barat (WIB / UTC+7)
WIB_TIMEZONE = timezone(timedelta(hours=7))

# Load env variables from .env
env_file = PROJECT_ROOT / ".env"
_env_vals = dotenv_values(env_file) if env_file.exists() else {}


def get_env(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    if value is not None and value != "":
        return value
    file_val = _env_vals.get(key)
    if file_val is not None and file_val != "":
        return file_val
    return default


SUPABASE_URL = get_env("SUPABASE_URL", get_env("PUBLIC_SUPABASE_URL", "")).rstrip("/")
SUPABASE_ANON_KEY = get_env("PUBLIC_SUPABASE_ANON_KEY", get_env("SUPABASE_ANON_KEY", ""))
SUPABASE_SERVICE_ROLE_KEY = get_env("SUPABASE_SERVICE_ROLE_KEY", "")

# Effective key for server/backend operations
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY

# AI & LLM settings
GEMINI_API_KEY = get_env("GEMINI_API_KEY", get_env("GOOGLE_API_KEY", ""))
GEMINI_MODEL = get_env("GEMINI_MODEL", "gemini-2.5-flash")
MAX_AI_COST_LIMIT_USD = float(get_env("MAX_AI_COST_LIMIT_USD", "10.0"))

# Security — wajib dikonfigurasi melalui environment variable CEO_SECRET_PIN (tanpa PIN bawaan)
CEO_SECRET_PIN = get_env("CEO_SECRET_PIN", "").strip()
AI_COMPANY_HOST = get_env("AI_COMPANY_HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = int(get_env("AI_COMPANY_PORT", "8787"))

_default_origins = ",".join([
    "https://infolokerkita.web.id",
    "https://www.infolokerkita.web.id",
    "http://localhost:4321",
    "http://127.0.0.1:4321",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
])
ALLOWED_ORIGINS = frozenset(
    origin.strip().rstrip("/")
    for origin in get_env("AI_COMPANY_ALLOWED_ORIGINS", _default_origins).split(",")
    if origin.strip()
)

# SQLite database for task management, audit logs, and agent states
LOCAL_DB_PATH = DATA_DIR / "company.db"
