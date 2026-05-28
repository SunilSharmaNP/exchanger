import logging
from aiogram import Bot
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


async def errors_handler(event: ErrorEvent, bot: Bot):
    """Global error handler — aiogram 3.x uses ErrorEvent."""
    exception = event.exception
    update = event.update

    logger.exception("Exception when handling update %s: %s", update, exception)

    try:
        if update.message:
            await update.message.answer(
                "⚠️ An internal error occurred. Our team has been notified."
            )
        elif update.callback_query:
            await update.callback_query.answer(
                "⚠️ An internal error occurred. Our team has been notified.",
                show_alert=True,
            )
    except Exception as e:
        logger.exception("Failed to notify user about error: %s", e)

    return True
