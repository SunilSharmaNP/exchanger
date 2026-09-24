import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")


def _parse_admin_ids(raw: str) -> list:
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            # Gracefully log warning instead of crashing on empty placeholder
            continue
        ids.append(int(part))
    return ids or [123456789]


ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", "123456789"))

# Optional API / Owner / Updater settings (can be set via .env)
API_ID = os.getenv("API_ID", "")
API_HASH = os.getenv("API_HASH", "")
OWNER_ID = int(os.getenv("OWNER_ID")) if os.getenv("OWNER_ID") and os.getenv("OWNER_ID").isdigit() else None

# Exchange Rates (Default values)
DEFAULT_INR_TO_NPR_RATE = 1.60
DEFAULT_NPR_TO_INR_RATE = 0.625

# Payment Details
UPI_ID = os.getenv("UPI_ID", "merchant@okaxis")
ESEWA_ID = os.getenv("ESEWA_ID", "9801234567")

# Limits
MIN_EXCHANGE_AMOUNT = float(os.getenv("MIN_EXCHANGE_AMOUNT", "100"))
MAX_EXCHANGE_AMOUNT = float(os.getenv("MAX_EXCHANGE_AMOUNT", "100000"))
SERVICE_FEE_PERCENTAGE = float(os.getenv("SERVICE_FEE_PERCENTAGE", "2.5"))  # 2.5% fee

# Database Configuration
DATABASE_DIR = Path("database")
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_NAME = str(DATABASE_DIR / "exchange_bot.db")
DATABASE_PATH = DATABASE_NAME

# Image URLs
BANNER_IMAGE_URL = os.getenv("BANNER_IMAGE_URL", "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1200&q=80")
PAYMENT_IMAGE_URL = os.getenv("PAYMENT_IMAGE_URL", "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?w=1200&q=80")

# Log Channel (optional — set to your Telegram channel ID, e.g. -1001234567890)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0")) if os.getenv("LOG_CHANNEL_ID", "0").lstrip("-").isdigit() else 0

# Features
ENABLE_REFERRAL = os.getenv("ENABLE_REFERRAL", "True").lower() in ("true", "1", "yes")
ENABLE_BROADCAST = os.getenv("ENABLE_BROADCAST", "True").lower() in ("true", "1", "yes")
ENABLE_DYNAMIC_QR = os.getenv("ENABLE_DYNAMIC_QR", "True").lower() in ("true", "1", "yes")
ANTI_SPAM_LIMIT = int(os.getenv("ANTI_SPAM_LIMIT", "8"))  # Max requests per window
ANTI_SPAM_WINDOW = int(os.getenv("ANTI_SPAM_WINDOW", "3600"))  # 1 hour in seconds

# Referral bonus default (percent)
REFERRAL_BONUS_PERCENT = float(os.getenv("REFERRAL_BONUS_PERCENT", "1.0"))
