"""
Log channel — sends structured event messages to a Telegram log channel.
Screenshots are never forwarded; only text summaries.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def _fmt(event_type: str, **kw) -> str:
    ts = _ts()

    if event_type == "user_start":
        tag = "🆕 New User" if kw.get("is_new") else "👋 User Returned"
        return (
            f"{tag}\n"
            f"User: <a href='tg://user?id={kw['user_id']}'>@{kw.get('username','?')}</a>"
            f" (<code>{kw['user_id']}</code>)\n"
            f"Name: {kw.get('first_name','')} {kw.get('last_name','')}\n"
            f"🕐 {ts}"
        )

    elif event_type == "exchange_instant":
        return (
            f"💱 <b>Instant Exchange Done</b>  #{kw['request_id']}\n"
            f"User: <a href='tg://user?id={kw['user_id']}'>@{kw.get('username','?')}</a>"
            f" (<code>{kw['user_id']}</code>)\n"
            f"Sent: <b>{kw['sent']}</b>  →  Received: <b>{kw['received']}</b>\n"
            f"Fee deducted: {kw['fee']}\n"
            f"🕐 {ts}"
        )

    elif event_type == "wallet_load_request":
        return (
            f"📥 <b>Wallet Load Request</b>  #{kw['request_id']}\n"
            f"User: <a href='tg://user?id={kw['user_id']}'>@{kw.get('username','?')}</a>"
            f" (<code>{kw['user_id']}</code>)\n"
            f"Amount: <b>{kw['amount']}</b>\n"
            f"Txn ID: <code>{kw.get('txn_id','?')}</code>\n"
            f"🕐 {ts}"
        )

    elif event_type == "wallet_credited":
        return (
            f"✅ <b>Wallet Credited</b>  #{kw['request_id']}\n"
            f"User: <a href='tg://user?id={kw['user_id']}'>@{kw.get('username','?')}</a>"
            f" (<code>{kw['user_id']}</code>)\n"
            f"Credited: <b>+{kw['amount']}</b>\n"
            f"Approved by: Admin <code>{kw.get('admin_id','?')}</code>\n"
            f"🕐 {ts}"
        )

    elif event_type == "withdrawal_request":
        return (
            f"💸 <b>Withdrawal Request</b>  #{kw['request_id']}\n"
            f"User: <a href='tg://user?id={kw['user_id']}'>@{kw.get('username','?')}</a>"
            f" (<code>{kw['user_id']}</code>)\n"
            f"Amount: <b>{kw['amount']}</b>\n"
            f"Receiving account: <code>{kw.get('account','?')}</code>\n"
            f"🕐 {ts}"
        )

    elif event_type == "withdrawal_paid":
        return (
            f"✅ <b>Withdrawal Completed</b>  #{kw['request_id']}\n"
            f"User: <a href='tg://user?id={kw['user_id']}'>@{kw.get('username','?')}</a>"
            f" (<code>{kw['user_id']}</code>)\n"
            f"Paid: <b>{kw['amount']}</b>\n"
            f"Processed by: Admin <code>{kw.get('admin_id','?')}</code>\n"
            f"🕐 {ts}"
        )

    elif event_type == "admin_credit":
        uid = kw.get("target_user_id") or kw.get("user_id", "?")
        return (
            f"🔧 <b>Admin Wallet Adjustment</b>\n"
            f"User: <a href='tg://user?id={uid}'><code>{uid}</code></a>\n"
            f"Action: {kw.get('action','?').upper()} {kw.get('amount','?')}\n"
            f"By: Admin <code>{kw.get('admin_id','?')}</code>\n"
            f"🕐 {ts}"
        )

    elif event_type == "load_approved":
        return (
            f"✅ <b>Load Request Approved</b>  #{kw['request_id']}\n"
            f"User: <a href='tg://user?id={kw['user_id']}'>@{kw.get('username','?')}</a>"
            f" (<code>{kw['user_id']}</code>)\n"
            f"Amount: <b>{kw['amount']}</b>\n"
            f"Approved by: Admin <code>{kw.get('admin_id','?')}</code>\n"
            f"🕐 {ts}"
        )

    elif event_type == "request_rejected":
        return (
            f"❌ <b>Request Rejected</b>  #{kw['request_id']}\n"
            f"User: <code>{kw.get('user_id','?')}</code>\n"
            f"Reason: {kw.get('reason','?')}\n"
            f"By: Admin <code>{kw.get('admin_id','?')}</code>\n"
            f"🕐 {ts}"
        )

    return ""


async def log_event(bot, event_type: str, **kwargs):
    """Send a structured log message to the log channel. Never raises."""
    from config import LOG_CHANNEL_ID
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
