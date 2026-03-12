import asyncio
from aiogram import Bot, Dispatcher
from aiogram import types
from aiogram.filters import Command
from config import BOT_TOKEN
from database import init_database
from handlers import router
from errors import errors_handler

async def main():
    # Initialize database
    init_database()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    # Register global error handler
    dp.errors.register(errors_handler)

    print("🚀 Bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
