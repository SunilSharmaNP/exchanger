import logging
from aiogram.types import Update

logger = logging.getLogger(__name__)

async def errors_handler(update: Update, exception: Exception):
    logger.exception("Exception when handling an update: %s", exception)

    # Try to inform the user gracefully
    try:
        if update.message:
            await update.message.answer("⚠️ An internal error occurred. Our team has been notified.")
        elif update.callback_query:
            await update.callback_query.answer("⚠️ An internal error occurred. Our team has been notified.")
    except Exception as e:
        logger.exception("Failed to notify user about error: %s", e)

    # Return True to indicate the exception was handled
    return True
