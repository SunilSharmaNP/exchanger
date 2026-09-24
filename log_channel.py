import logging
import html
from datetime import datetime
from config import LOG_CHANNEL_ID

logger = logging.getLogger(__name__)


def _esc(val):
    if val is None:
        return ""
    return html.escape(str(val))


def _ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def _fmt(event_type: str, **kw) -> str:
    ts = _ts()
    uid = kw.get('user_id', '?')
    uname = _esc(kw.get('username', '?'))

    if event_type == "user_start":
        tag = "🆕 <b>New User Joined</b>" if kw.get("is_new") else "👋 <b>User Returned</b>"
        return (
            f"{tag}\n"
            f"<blockquote>"
            f"User: <a href='tg://user?id={uid}'>@{uname}</a> (<code>{uid}</code>)\n"
            f"Name: {_esc(kw.get('first_name', ''))} {_esc(kw.get('last_name', ''))}\n"
            f"Referrer: <code>{_esc(kw.get('referred_by', 'None'))}</code>\n"
            f"🕐 {ts}"
            f"</blockquote>"
        )

    elif event_type == "exchange_instant":
        return (
            f"⚡ <b>Instant Wallet Swap Completed — #{kw.get('request_id', '?')}</b>\n"
            f"<blockquote>"
            f"User: <a href='tg://user?id={uid}'>@{uname}</a> (<code>{uid}</code>)\n"
            f"Sent: <b>{_esc(kw.get('sent'))}</b> → Received: <b>{_esc(kw.get('received'))}</b>\n"
            f"Fee: {_esc(kw.get('fee'))}\n"
            f"🕐 {ts}"
            f"</blockquote>"
        )

    elif event_type == "wallet_load_request":
        return (
            f"📥 <b>New Deposit Request — #{kw.get('request_id', '?')}</b>\n"
            f"<blockquote>"
            f"User: <a href='tg://user?id={uid}'>@{uname}</a> (<code>{uid}</code>)\n"
            f"Amount: <b>{_esc(kw.get('amount'))}</b>\n"
            f"Txn ID: <code>{_esc(kw.get('txn_id', '?'))}</code>\n"
            f"🕐 {ts}"
            f"</blockquote>"
        )

    elif event_type == "request_approved":
        return (
            f"✅ <b>Order Approved — #{kw.get('request_id', '?')}</b>\n"
            f"<blockquote>"
            f"User: <code>{uid}</code>\n"
            f"Amount: <b>{_esc(kw.get('amount', '?'))}</b>\n"
            f"Admin: <code>{kw.get('admin_id', '?')}</code>\n"
            f"🕐 {ts}"
            f"</blockquote>"
        )

    elif event_type == "request_rejected":
        return (
            f"❌ <b>Order Rejected — #{kw.get('request_id', '?')}</b>\n"
            f"<blockquote>"
            f"Order ID: #{kw.get('request_id', '?')}\n"
            f"User: <code>{uid}</code>\n"
            f"Reason: <i>{_esc(kw.get('reason', '?'))}</i>\n"
            f"Admin: <code>{kw.get('admin_id', '?')}</code>\n"
            f"🕐 {ts}"
            f"</blockquote>"
        )

    return ""


async def log_event(bot, event_type: str, **kwargs):
    """Send a structured log message to the log channel. Never raises."""
    if not LOG_CHANNEL_ID:
        return
    text = _fmt(event_type, **kwargs)
    if not text:
        return
    try:
        await bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning("[log_channel] %s: %s", event_type, e)
