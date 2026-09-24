import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault

try:
    from aiogram.client.default import DefaultBotProperties
except ImportError:
    DefaultBotProperties = None

from config import BOT_TOKEN
from database import init_db
from handlers import router
from errors import errors_handler

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    """Register menu commands with modern emojis and clean English descriptions in Telegram."""
    commands = [
        BotCommand(command="start", description="🚀 Start / Main Menu"),
        BotCommand(command="home", description="🏠 Home Dashboard"),
        BotCommand(command="calc", description="🔢 Rate Calculator"),
        BotCommand(command="wallet", description="💼 My Wallet & Balances"),
        BotCommand(command="history", description="📜 Transaction History"),
        BotCommand(command="profile", description="👤 Profile & Referrals"),
        BotCommand(command="status", description="🔍 Track Order Status"),
        BotCommand(command="help", description="❓ Help & User Guide"),
        BotCommand(command="about", description="ℹ️ About Our Platform"),
        BotCommand(command="contact", description="📞 Contact Support Desk"),
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        logger.info("Bot menu commands registered successfully.")
    except Exception as e:
        logger.warning("Could not set bot commands: %s", e)


async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN is not configured! Please provide BOT_TOKEN in .env file.")
        print("\n" + "=" * 60)
        print("❌ CONFIGURATION REQUIRED: BOT_TOKEN is missing in .env")
        print("1. Copy 'sample.env' to '.env'")
        print("2. Set your BOT_TOKEN from @BotFather")
        print("3. Set your Telegram numeric ID in ADMIN_IDS")
        print("=" * 60 + "\n")
        return

    # Initialize SQLite Database tables, WAL mode, and default settings
    logger.info("Initializing database...")
    init_db()

    # Initialize Bot & Dispatcher (compatible with aiogram >= 3.7.0 and older versions)
    if DefaultBotProperties is not None:
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    else:
        bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    # Register error handler
    dp.errors.register(errors_handler)

    # Register handlers router
    dp.include_router(router)

    # Setup menu commands
    await set_bot_commands(bot)

    logger.info("Starting Exchanger Bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
