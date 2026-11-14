import os
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

# Load env variables from .env
env_file = PROJECT_ROOT / ".env"
_env_vals = dotenv_values(env_file) if env_file.exists() else {}

def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key) or _env_vals.get(key) or default

SUPABASE_URL = get_env("SUPABASE_URL", get_env("PUBLIC_SUPABASE_URL", "")).rstrip("/")
SUPABASE_ANON_KEY = get_env("PUBLIC_SUPABASE_ANON_KEY", get_env("SUPABASE_ANON_KEY", ""))
SUPABASE_SERVICE_ROLE_KEY = get_env("SUPABASE_SERVICE_ROLE_KEY", "")

# Effective key for server/backend operations
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY

# AI & LLM settings
GEMINI_API_KEY = get_env("GEMINI_API_KEY", get_env("GOOGLE_API_KEY", ""))
GEMINI_MODEL = get_env("GEMINI_MODEL", "gemini-2.5-flash")
MAX_AI_COST_LIMIT_USD = float(get_env("MAX_AI_COST_LIMIT_USD", "10.0"))

# Security
CEO_SECRET_PIN = get_env("CEO_SECRET_PIN", "infoloker2026")
PORT = int(get_env("AI_COMPANY_PORT", "8787"))

# SQLite database for task management, audit logs, and agent states
LOCAL_DB_PATH = DATA_DIR / "company.db"
