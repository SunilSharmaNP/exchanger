import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))

# Optional API / Owner / Updater settings (can be set via .env)
API_ID = os.getenv("API_ID", "")
API_HASH = os.getenv("API_HASH", "")
# Owner/Admin ID (optional)
OWNER_ID = int(os.getenv("OWNER_ID")) if os.getenv("OWNER_ID") else None

# Updater / remote config
MONGO_URI = os.getenv("MONGO_URI", "")
UPSTREAM_REPO = os.getenv("UPSTREAM_REPO", "")
UPSTREAM_BRANCH = os.getenv("UPSTREAM_BRANCH", "main")
UPDATE_PKGS = os.getenv("UPDATE_PKGS", "True")

# Exchange Rates (Default values)
DEFAULT_INR_TO_NPR_RATE = 1.60
DEFAULT_NPR_TO_INR_RATE = 0.625

# Payment Details
UPI_ID = os.getenv("UPI_ID", "business@upi")
ESEWA_ID = os.getenv("ESEWA_ID", "esewa_merchant@123")

# Limits
MIN_EXCHANGE_AMOUNT = 100
MAX_EXCHANGE_AMOUNT = 100000
SERVICE_FEE_PERCENTAGE = 2.5  # 2.5% fee

# Database
DATABASE_PATH = "database/exchange_bot.db"

# Image URLs (Optional - Can be replaced with local paths)
BANNER_IMAGE_URL = "https://via.placeholder.com/1280x720?text=Currency+Exchange+Bot"
PAYMENT_IMAGE_URL = "https://via.placeholder.com/800x400?text=Payment+Instructions"

# Features
ENABLE_REFERRAL = True
ENABLE_BROADCAST = True
ANTI_SPAM_LIMIT = 5  # Max requests per hour
ANTI_SPAM_WINDOW = 3600  # 1 hour in seconds

# Referral bonus default (percent)
REFERRAL_BONUS_PERCENT = float(os.getenv("REFERRAL_BONUS_PERCENT", "1.0"))
