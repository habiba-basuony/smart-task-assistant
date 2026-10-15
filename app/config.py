import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app_data/smart_tasks.db")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama-3.3-70b-versatile").strip()

# "Today" for relative dates ("بكرة", "الأحد الجاي") is the date in this time zone.
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Riyadh")

TELEGRAM_LINK_ADMIN_TOKEN = os.getenv(
    "TELEGRAM_LINK_ADMIN_TOKEN", ""
).strip()

TELEGRAM_INTERNAL_TOKEN = os.getenv(
    "TELEGRAM_INTERNAL_TOKEN", ""
).strip()
