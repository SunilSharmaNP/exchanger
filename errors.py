import logging
from aiogram import Bot
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


async def errors_handler(event: ErrorEvent, bot: Bot):
    """Global error handler for aiogram 3.x."""
    exception = event.exception
    update = event.update

    logger.exception("Exception when handling update: %s", exception)

    try:
        if update and update.message:
            await update.message.answer(
                "⚠️ <b>Internal System Notice</b>\n"
                "A temporary error occurred while processing your request. Please try again shortly or contact support.",
                parse_mode="HTML"
            )
        elif update and update.callback_query:
            await update.callback_query.answer(
                "⚠️ Temporary system error. Please retry.",
                show_alert=True,
            )
    except Exception as e:
        logger.error("Failed to notify user about error: %s", e)

    return True
