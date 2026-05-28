import asyncio
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_db_connection, execute_db, get_bot_stats
from config import (
    BOT_TOKEN, ADMIN_IDS, SERVICE_FEE_PERCENTAGE, BANNER_IMAGE_URL,
    ENABLE_REFERRAL, REFERRAL_BONUS_PERCENT
)
from keyboards import (
    get_start_keyboard, get_exchange_confirmation_keyboard,
    get_payment_keyboard, get_admin_approval_keyboard,
    get_admin_menu_keyboard, get_settings_keyboard,
    get_load_wallet_keyboard, get_back_button, get_cancel_button,
    get_reject_reason_keyboard, REJECT_REASONS,
    get_support_keyboard, get_user_support_reply_keyboard,
    get_admin_support_keyboard, get_admin_support_panel_keyboard,
)
from messages import *
from utils import (
    validate_amount, calculate_exchange, get_exchange_rate,
    get_payment_details, check_anti_spam, is_user_banned,
    format_currency, format_timestamp, get_exchange_type_display,
    get_exchange_currencies, validate_transaction_id,
    get_user_info, generate_referral_code
)

router = Router()


# ── States ─────────────────────────────────────────────────────────────────────

class ExchangeStates(StatesGroup):
    entering_amount = State()
    confirming_exchange = State()
    waiting_payment = State()
    uploading_screenshot = State()
    uploading_transaction_id = State()


class AdminStates(StatesGroup):
    setting_rate = State()
    updating_payment = State()
    broadcasting = State()
    messaging_user = State()
    replying_support = State()
    entering_reject_reason = State()


class WalletStates(StatesGroup):
    entering_load_amount = State()


class WithdrawalStates(StatesGroup):
    entering_withdraw_amount = State()
    entering_withdraw_account = State()


class SupportStates(StatesGroup):
    awaiting_message = State()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _safe_edit(callback: CallbackQuery, text: str, **kwargs):
    """Edit message if possible, otherwise send a new one."""
    try:
        await callback.message.edit_text(text, **kwargs)
    except Exception:
        try:
            await callback.message.answer(text, **kwargs)
        except Exception:
            pass


def _build_welcome(inr_to_npr=None, npr_to_inr=None):
    """Build welcome text with live rates."""
    if inr_to_npr is None:
        inr_to_npr = get_exchange_rate("INR_TO_NPR") or "—"
    if npr_to_inr is None:
        npr_to_inr = get_exchange_rate("NPR_TO_INR") or "—"
    return WELCOME_MESSAGE.format(inr_to_npr=inr_to_npr, npr_to_inr=npr_to_inr)


async def notify_admin(user_id, username, data, transaction_id, request_id, bot: Bot):
    """Send notification to all admins about a new exchange/load/withdraw request."""
    admin_msg = ADMIN_REQUEST.format(
        request_id=request_id,
        user_id=user_id,
        username=username,
        exchange_type=get_exchange_type_display(data.get("exchange_type", "")),
        amount=format_currency(data.get("amount", 0), data.get("from_currency", "INR")),
        rate=data.get("exchange_rate", "N/A"),
        final_amount=format_currency(data.get("final_amount", 0), data.get("to_currency", "NPR")),
        to_currency=data.get("to_currency", "NPR"),
        transaction_id=transaction_id,
    )
    for admin_id in ADMIN_IDS:
        try:
            if data.get("screenshot_file_id"):
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=data["screenshot_file_id"],
                    caption=admin_msg,
                    parse_mode="HTML",
                    reply_markup=get_admin_approval_keyboard(request_id),
                )
            else:
                await bot.send_message(
                    chat_id=admin_id,
                    text=admin_msg,
                    parse_mode="HTML",
                    reply_markup=get_admin_approval_keyboard(request_id),
                )
        except Exception as e:
            print(f"[notify_admin] Error sending to admin {admin_id}: {e}")


def _apply_referral_bonus(user_id, username, request_id, final_amount, payout_currency, bot):
    """Fire-and-forget referral bonus — errors are swallowed intentionally."""
    async def _do():
        try:
            if not ENABLE_REFERRAL:
                return
            ref = execute_db(
                "SELECT referred_by FROM users WHERE user_id = ?", (user_id,), fetchone=True
            )
            if not (ref and ref[0]):
                return
            referrer_id = ref[0]

            bonus_row = execute_db(
                "SELECT setting_value FROM admin_settings WHERE setting_name = 'referral_bonus_percent'",
                fetchone=True,
            )
            bonus_pct = float(bonus_row[0]) if bonus_row else REFERRAL_BONUS_PERCENT
            bonus = float(final_amount) * (bonus_pct / 100.0)

            if payout_currency == "NPR":
                execute_db(
                    "UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?",
                    (bonus, referrer_id), commit=True,
                )
            else:
                execute_db(
                    "UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) + ? WHERE user_id = ?",
                    (bonus, referrer_id), commit=True,
                )
            execute_db(
                "INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (referrer_id, request_id, "referral_bonus", bonus, payout_currency, "completed"),
                commit=True,
            )
            try:
                await bot.send_message(
                    chat_id=referrer_id,
                    text=(
                        f"🎉 <b>Referral Bonus!</b>\n\n"
                        f"You earned <b>{format_currency(bonus, payout_currency)}</b> "
                        f"because @{username} completed an exchange using your referral link.\n\n"
                        f"<i>Bonus has been added to your wallet.</i>"
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        except Exception as e:
            print(f"[referral_bonus] Error: {e}")

    asyncio.create_task(_do())


def _do_refund(request_id, user_id):
    """Refund any held wallet debit for a request. Call after rejection."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT amount, currency, status FROM transactions"
            " WHERE exchange_request_id = ? AND transaction_type = 'debit'",
            (request_id,),
        )
        row = cur.fetchone()
        if row and row[2] == "held":
            amt, currency = float(row[0]), row[1]
            if currency == "INR":
                cur.execute(
                    "UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) + ? WHERE user_id = ?",
                    (amt, user_id),
                )
            else:
                cur.execute(
                    "UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?",
                    (amt, user_id),
                )
            cur.execute(
                "UPDATE transactions SET status = 'refunded'"
                " WHERE exchange_request_id = ? AND transaction_type = 'debit'",
                (request_id,),
            )
            cur.execute(
                "INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, request_id, "refund", amt, currency, "completed"),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[refund] Error: {e}")


# ── /start and /menu ───────────────────────────────────────────────────────────

@router.message(lambda msg: msg.text and (
    msg.text == "/start" or msg.text.startswith("/start ") or msg.text == "/menu"
))
async def start_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name or "User"
    last_name = message.from_user.last_name or ""

    if is_user_banned(user_id):
        await message.answer(ERROR_MESSAGES["banned"])
        return

    # Parse optional referral code: /start ref_XXXX
    referrer_id = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("ref_"):
        ref_code = parts[1][4:]
        row = execute_db(
            "SELECT user_id FROM users WHERE referral_code = ?", (ref_code,), fetchone=True
        )
        if row and row[0] != user_id:
            referrer_id = row[0]

    existing = execute_db("SELECT user_id FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not existing:
        referral_code = generate_referral_code(user_id)
        execute_db(
            "INSERT INTO users (user_id, username, first_name, last_name, referral_code, referred_by)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, first_name, last_name, referral_code, referrer_id),
            commit=True,
        )
        if referrer_id:
            await message.answer(
                "🎉 <b>Referral Bonus Active!</b>\n\n"
                "You joined via a referral link. Your friend will earn a bonus when your first exchange is approved.",
                parse_mode="HTML",
            )
    else:
        execute_db(
            "UPDATE users SET username = ?, first_name = ?, last_name = ? WHERE user_id = ?",
            (username, first_name, last_name, user_id), commit=True,
        )

    await state.clear()
    welcome = _build_welcome()
    try:
        await message.answer_photo(
            photo=BANNER_IMAGE_URL,
            caption=welcome,
            parse_mode="HTML",
            reply_markup=get_start_keyboard(),
        )
    except Exception:
        await message.answer(welcome, parse_mode="HTML", reply_markup=get_start_keyboard())


# ── /help ──────────────────────────────────────────────────────────────────────

@router.message(lambda msg: msg.text == "/help")
async def help_command(message: Message):
    text = (
        "📚 <b>Help &amp; Commands</b>\n\n"
        "<b>User Commands:</b>\n"
        "/start — Main menu\n"
        "/profile — Your profile &amp; referral link\n"
        "/wallet — Check wallet balances\n"
        "/load — Load wallet funds\n"
        "/history — Transaction history\n"
        "/withdraw — Withdraw funds\n"
        "/help — This help message\n\n"
        "<b>Exchange Flow:</b>\n"
        "1. Load your wallet (INR or NPR)\n"
        "2. Select exchange direction\n"
        "3. Enter amount &amp; review\n"
        "4. Pay via UPI / eSewa\n"
        "5. Upload screenshot + transaction ID\n"
        "6. Admin approves → funds credited ✅\n\n"
        f"<i>Fee: {SERVICE_FEE_PERCENTAGE}% · Min: 100 · Max: 1,00,000</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_start_keyboard())


# ── /profile shortcut ──────────────────────────────────────────────────────────

@router.message(lambda msg: msg.text == "/profile")
async def profile_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    if not user_info:
        await message.answer("⚠️ Profile not found. Use /start to register.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    referred_count = cursor.fetchone()[0]
    conn.close()

    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_info['referral_code'] or ''}"

    text = PROFILE_MESSAGE.format(
        first_name=user_info["first_name"] or "User",
        username=user_info["username"] or "N/A",
        user_id=user_id,
        joined_date=format_timestamp(user_info["joined_date"]),
        wallet_inr=format_currency(user_info["wallet_inr"] or 0, "INR"),
        wallet_npr=format_currency(user_info["wallet_npr"] or 0, "NPR"),
        total_exchanges=user_info["total_exchanges"] or 0,
        total_amount=format_currency(user_info["total_amount"] or 0, "INR"),
        referral_code=user_info["referral_code"] or "N/A",
        referral_link=ref_link,
        referred_count=referred_count,
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_back_button())


# ── /wallet shortcut ───────────────────────────────────────────────────────────

@router.message(lambda msg: msg.text == "/wallet")
async def wallet_command(message: Message):
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    if not user_info:
        await message.answer("⚠️ Profile not found. Use /start to register.")
        return
    text = (
        "💼 <b>Your Wallet</b>\n\n"
        f"💵 INR: <b>{format_currency(user_info.get('wallet_inr') or 0, 'INR')}</b>\n"
        f"₨  NPR: <b>{format_currency(user_info.get('wallet_npr') or 0, 'NPR')}</b>\n\n"
        "<i>Use 'Load Wallet' to add funds.</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_load_wallet_keyboard())


# ── /load shortcut ─────────────────────────────────────────────────────────────

@router.message(lambda msg: msg.text == "/load")
async def load_command(message: Message):
    await message.answer(
        "💰 <b>Load Wallet</b>\n\nSelect which currency to load:",
        parse_mode="HTML",
        reply_markup=get_load_wallet_keyboard(),
    )


# ── /history shortcut ──────────────────────────────────────────────────────────

@router.message(lambda msg: msg.text == "/history")
async def history_command(message: Message):
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT request_id, exchange_type, amount, final_amount, status, created_at"
        " FROM exchange_requests WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,),
    )
    transactions = cursor.fetchall()
    cursor.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM exchange_requests"
        " WHERE user_id = ? AND status = 'completed'",
        (user_id,),
    )
    stats = cursor.fetchone()
    conn.close()

    total = stats[0] or 0
    total_amount = stats[1] or 0

    if not transactions:
        history_text = "<i>No transactions yet. Start your first exchange!</i>"
    else:
        history_text = ""
        for txn in transactions:
            from_c, to_c = get_exchange_currencies(txn[1])
            status_icon = {"completed": "✅", "pending": "⏳", "approved": "🔄", "rejected": "❌"}.get(txn[4], "❓")
            history_text += (
                f"{status_icon} <b>#{txn[0]}</b> — {get_exchange_type_display(txn[1])}\n"
                f"   {format_currency(txn[2], from_c)} → {format_currency(txn[3], to_c)}\n"
                f"   {format_timestamp(txn[5])}\n\n"
            )

    msg = TRANSACTION_HISTORY.format(
        transactions=history_text,
        total=total,
        total_amount=format_currency(total_amount, "INR"),
    )
    await message.answer(msg, parse_mode="HTML", reply_markup=get_back_button())


# ── /withdraw shortcut ─────────────────────────────────────────────────────────

@router.message(lambda msg: msg.text == "/withdraw")
async def withdraw_command(message: Message, state: FSMContext):
    if is_user_banned(message.from_user.id):
        await message.answer(ERROR_MESSAGES["banned"])
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Withdraw INR", callback_data="withdraw_inr")],
        [InlineKeyboardButton(text="₨ Withdraw NPR", callback_data="withdraw_npr")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_start")],
    ])
    await state.clear()
    await message.answer("💸 <b>Withdraw Funds</b>\n\nSelect currency to withdraw:", parse_mode="HTML", reply_markup=kb)


# ── /admin ─────────────────────────────────────────────────────────────────────

@router.message(lambda msg: msg.text and msg.text.startswith("/admin"))
async def admin_panel_cmd(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        return
    await state.clear()
    await message.answer("🔧 <b>Admin Panel</b>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())


# ── /restart ───────────────────────────────────────────────────────────────────

@router.message(lambda msg: msg.text and msg.text.startswith("/restart"))
async def admin_restart(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        return
    await message.answer("🔄 Pulling latest code from upstream…")
    from updater import restart_bot
    ok, msg_text = await restart_bot()
    await message.answer(msg_text)
    if ok:
        try:
            import os, sys
            if os.getenv("IN_DOCKER", "0") == "1":
                await message.answer("♻️ Exiting — container will restart automatically.")
                sys.exit(0)
            else:
                await message.answer("♻️ Restarting bot process…")
                os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            await message.answer(f"⚠️ Restart failed: {e}")


# ── Exchange flow ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "exchange_inr_to_npr")
async def exchange_inr_to_npr(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if is_user_banned(callback.from_user.id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return
    can, wait = check_anti_spam(callback.from_user.id)
    if not can:
        await callback.answer(f"⏱️ Too many requests! Wait {wait} min(s).", show_alert=True)
        return
    await state.set_state(ExchangeStates.entering_amount)
    await state.update_data(exchange_type="INR_TO_NPR")
    await _safe_edit(callback, ENTER_AMOUNT, parse_mode="HTML", reply_markup=get_cancel_button())


@router.callback_query(F.data == "exchange_npr_to_inr")
async def exchange_npr_to_inr(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if is_user_banned(callback.from_user.id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return
    can, wait = check_anti_spam(callback.from_user.id)
    if not can:
        await callback.answer(f"⏱️ Too many requests! Wait {wait} min(s).", show_alert=True)
        return
    await state.set_state(ExchangeStates.entering_amount)
    await state.update_data(exchange_type="NPR_TO_INR")
    await _safe_edit(callback, ENTER_AMOUNT, parse_mode="HTML", reply_markup=get_cancel_button())


@router.message(ExchangeStates.entering_amount)
async def process_amount(message: Message, state: FSMContext):
    is_valid, result = validate_amount(message.text or "")
    if not is_valid:
        await message.answer(f"❌ {result}\n\n<i>Please enter a valid amount.</i>", parse_mode="HTML")
        return

    amount = result
    data = await state.get_data()
    exchange_type = data["exchange_type"]
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    wallet_inr = float(user_info["wallet_inr"] or 0) if user_info else 0
    wallet_npr = float(user_info["wallet_npr"] or 0) if user_info else 0

    if exchange_type == "INR_TO_NPR" and wallet_inr < amount:
        await message.answer(
            f"⚠️ <b>Insufficient INR Balance</b>\n\n"
            f"• You need: {format_currency(amount, 'INR')}\n"
            f"• Your balance: {format_currency(wallet_inr, 'INR')}\n\n"
            "Please load your INR wallet first.",
            parse_mode="HTML",
            reply_markup=get_load_wallet_keyboard(),
        )
        await state.clear()
        return
    if exchange_type == "NPR_TO_INR" and wallet_npr < amount:
        await message.answer(
            f"⚠️ <b>Insufficient NPR Balance</b>\n\n"
            f"• You need: {format_currency(amount, 'NPR')}\n"
            f"• Your balance: {format_currency(wallet_npr, 'NPR')}\n\n"
            "Please load your NPR wallet first.",
            parse_mode="HTML",
            reply_markup=get_load_wallet_keyboard(),
        )
        await state.clear()
        return

    rate = get_exchange_rate(exchange_type)
    if not rate:
        await message.answer("⚠️ Exchange rate not available right now. Please try again later.")
        return

    calculated, fee, final = calculate_exchange(amount, rate)
    from_currency, to_currency = get_exchange_currencies(exchange_type)

    await state.update_data(
        amount=amount,
        exchange_rate=rate,
        calculated_amount=calculated,
        service_fee=fee,
        final_amount=final,
        from_currency=from_currency,
        to_currency=to_currency,
    )

    summary = EXCHANGE_SUMMARY.format(
        amount=format_currency(amount, from_currency),
        from_currency=from_currency,
        rate=rate,
        to_currency=to_currency,
        calculated_amount=format_currency(calculated, to_currency),
        fee_percent=SERVICE_FEE_PERCENTAGE,
        service_fee=format_currency(fee, to_currency),
        final_amount=format_currency(final, to_currency),
    )
    await state.set_state(ExchangeStates.confirming_exchange)
    await message.answer(summary, parse_mode="HTML", reply_markup=get_exchange_confirmation_keyboard())


@router.callback_query(F.data == "confirm_exchange")
async def confirm_exchange(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    upi_id, esewa_id = get_payment_details()
    payment_msg = PAYMENT_INSTRUCTIONS.format(upi_id=upi_id, esewa_id=esewa_id, user_id=user_id)
    await state.set_state(ExchangeStates.waiting_payment)
    await state.update_data(upi_id=upi_id, esewa_id=esewa_id)
    try:
        await callback.message.answer_photo(
            photo=BANNER_IMAGE_URL,
            caption=payment_msg,
            parse_mode="HTML",
            reply_markup=get_payment_keyboard(),
        )
    except Exception:
        await callback.message.answer(payment_msg, parse_mode="HTML", reply_markup=get_payment_keyboard())


@router.callback_query(F.data == "payment_done")
async def payment_done(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ExchangeStates.uploading_screenshot)
    await callback.message.answer(
        "📸 <b>Upload Payment Screenshot</b>\n\n"
        "Please send a <b>clear screenshot</b> of your payment confirmation.\n\n"
        "<i>The screenshot must show the amount, date, and transaction reference.</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(ExchangeStates.uploading_screenshot)
async def receive_screenshot(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer(
            "❌ <b>Image required</b>\n\nPlease send a screenshot image, not text.",
            parse_mode="HTML",
        )
        return
    file_id = message.photo[-1].file_id
    await state.update_data(screenshot_file_id=file_id)
    await state.set_state(ExchangeStates.uploading_transaction_id)
    await message.answer(
        "🔢 <b>Enter Transaction ID</b>\n\n"
        "Please type the transaction / UTR / reference number shown in your payment confirmation.",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(ExchangeStates.uploading_transaction_id)
async def receive_transaction_id(message: Message, state: FSMContext, bot: Bot):
    txn_id = (message.text or "").strip()
    if not validate_transaction_id(txn_id):
        await message.answer(
            "❌ <b>Invalid Transaction ID</b>\n\n"
            "Please enter the transaction / UTR reference (5–50 alphanumeric characters).",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    # Create exchange request row
    request_id = execute_db(
        "INSERT INTO exchange_requests"
        " (user_id, username, exchange_type, amount, exchange_rate, calculated_amount,"
        "  service_fee, final_amount, transaction_id, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id, username, data["exchange_type"], data["amount"], data["exchange_rate"],
            data["calculated_amount"], data["service_fee"], data["final_amount"],
            txn_id, "pending",
        ),
        commit=True,
    )

    # Reserve source wallet funds
    try:
        conn2 = get_db_connection()
        cur2 = conn2.cursor()
        src_amount = float(data.get("amount", 0))
        if data.get("exchange_type") == "INR_TO_NPR":
            cur2.execute(
                "UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) - ? WHERE user_id = ? AND COALESCE(wallet_inr,0) >= ?",
                (src_amount, user_id, src_amount),
            )
            src_currency = "INR"
        else:
            cur2.execute(
                "UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) - ? WHERE user_id = ? AND COALESCE(wallet_npr,0) >= ?",
                (src_amount, user_id, src_amount),
            )
            src_currency = "NPR"

        if cur2.rowcount == 0:
            conn2.close()
            execute_db("DELETE FROM exchange_requests WHERE request_id = ?", (request_id,), commit=True)
            await message.answer(
                "⚠️ <b>Insufficient Balance</b>\n\n"
                "Your wallet balance changed before this request was confirmed. Please try again.",
                parse_mode="HTML",
                reply_markup=get_start_keyboard(),
            )
            await state.clear()
            return

        cur2.execute(
            "INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, request_id, "debit", src_amount, src_currency, "held"),
        )
        conn2.commit()
        conn2.close()
    except Exception as e:
        print(f"[reserve_funds] Error: {e}")

    from_c = data.get("from_currency", "INR")
    to_c = data.get("to_currency", "NPR")

    await message.answer(
        f"✅ <b>Request #{request_id} Submitted!</b>\n\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"Type: <b>{get_exchange_type_display(data.get('exchange_type'))}</b>\n"
        f"You sent: <b>{format_currency(data.get('amount', 0), from_c)}</b>\n"
        f"You'll receive: <b>{format_currency(data.get('final_amount', 0), to_c)}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
        "Our team will verify your payment and process within <b>5–15 minutes</b>.\n"
        "You'll be notified here once done.",
        parse_mode="HTML",
        reply_markup=get_start_keyboard(),
    )

    await notify_admin(user_id, username, data, txn_id, request_id, bot)
    await state.clear()


@router.callback_query(F.data == "cancel_exchange")
async def cancel_exchange(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Cancelled")
    await state.clear()
    await _safe_edit(callback, "❌ Exchange cancelled.\n\n" + _build_welcome(), parse_mode="HTML", reply_markup=get_start_keyboard())


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Cancelled")
    await state.clear()
    await callback.message.answer("❌ Payment cancelled.", reply_markup=get_start_keyboard())


# ── Callbacks: user features ───────────────────────────────────────────────────

@router.callback_query(F.data == "check_rate")
async def check_rate(callback: CallbackQuery):
    await callback.answer()
    inr_to_npr = get_exchange_rate("INR_TO_NPR")
    npr_to_inr = get_exchange_rate("NPR_TO_INR")
    rate_msg = CURRENT_RATE.format(
        inr_to_npr=inr_to_npr or "N/A",
        npr_to_inr=npr_to_inr or "N/A",
        fee=SERVICE_FEE_PERCENTAGE,
    )
    await _safe_edit(callback, rate_msg, parse_mode="HTML", reply_markup=get_back_button())


@router.callback_query(F.data == "wallet_balance")
async def wallet_balance(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return
    user_info = get_user_info(user_id)
    if not user_info:
        await callback.answer("⚠️ Profile not found.", show_alert=True)
        return
    text = (
        "💼 <b>Your Wallet</b>\n\n"
        f"💵 INR: <b>{format_currency(user_info.get('wallet_inr') or 0, 'INR')}</b>\n"
        f"₨  NPR: <b>{format_currency(user_info.get('wallet_npr') or 0, 'NPR')}</b>\n\n"
        "<i>Use 'Load Wallet' to add funds.</i>"
    )
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=get_load_wallet_keyboard())


@router.callback_query(F.data == "transaction_history")
async def show_transaction_history(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT request_id, exchange_type, amount, final_amount, status, created_at"
        " FROM exchange_requests WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,),
    )
    transactions = cursor.fetchall()
    cursor.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM exchange_requests"
        " WHERE user_id = ? AND status = 'completed'",
        (user_id,),
    )
    stats = cursor.fetchone()
    conn.close()

    total = stats[0] or 0
    total_amount = stats[1] or 0

    if not transactions:
        history_text = "<i>No transactions yet. Start your first exchange!</i>"
    else:
        history_text = ""
        for txn in transactions:
            from_c, to_c = get_exchange_currencies(txn[1])
            status_icon = {"completed": "✅", "pending": "⏳", "approved": "🔄", "rejected": "❌"}.get(txn[4], "❓")
            history_text += (
                f"{status_icon} <b>#{txn[0]}</b> — {get_exchange_type_display(txn[1])}\n"
                f"   {format_currency(txn[2], from_c)} → {format_currency(txn[3], to_c)}\n"
                f"   {format_timestamp(txn[5])}\n\n"
            )

    msg = TRANSACTION_HISTORY.format(
        transactions=history_text,
        total=total,
        total_amount=format_currency(total_amount, "INR"),
    )
    await _safe_edit(callback, msg, parse_mode="HTML", reply_markup=get_back_button())


@router.callback_query(F.data == "how_it_works")
async def how_it_works(callback: CallbackQuery):
    await callback.answer()
    await _safe_edit(callback, HOW_IT_WORKS, parse_mode="HTML", reply_markup=get_back_button())


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = callback.from_user.id
    user_info = get_user_info(user_id)
    if not user_info:
        await callback.answer("⚠️ Profile not found.", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    referred_count = cursor.fetchone()[0]
    conn.close()

    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_info['referral_code'] or ''}"

    text = PROFILE_MESSAGE.format(
        first_name=user_info["first_name"] or "User",
        username=user_info["username"] or "N/A",
        user_id=user_id,
        joined_date=format_timestamp(user_info["joined_date"]),
        wallet_inr=format_currency(user_info["wallet_inr"] or 0, "INR"),
        wallet_npr=format_currency(user_info["wallet_npr"] or 0, "NPR"),
        total_exchanges=user_info["total_exchanges"] or 0,
        total_amount=format_currency(user_info["total_amount"] or 0, "INR"),
        referral_code=user_info["referral_code"] or "N/A",
        referral_link=ref_link,
        referred_count=referred_count,
    )
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=get_back_button())


@router.callback_query(F.data == "load_wallet")
async def load_wallet(callback: CallbackQuery):
    await callback.answer()
    await _safe_edit(
        callback,
        "💰 <b>Load Wallet</b>\n\nSelect which currency you want to add funds to:",
        parse_mode="HTML",
        reply_markup=get_load_wallet_keyboard(),
    )


# ── Support chat ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "support")
async def support_menu(callback: CallbackQuery):
    await callback.answer()
    msg = SUPPORT_MENU.format(fee=SERVICE_FEE_PERCENTAGE)
    await _safe_edit(callback, msg, parse_mode="HTML", reply_markup=get_support_keyboard())


@router.callback_query(F.data == "support_new_ticket")
async def support_new_ticket(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if is_user_banned(callback.from_user.id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return
    await state.set_state(SupportStates.awaiting_message)
    await state.update_data(support_ticket_id=None)
    await _safe_edit(
        callback,
        "💬 <b>New Support Ticket</b>\n\n"
        "Please describe your issue or question in detail.\n\n"
        "<i>Type your message and press Send.</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("support_reply_"))
async def support_user_reply(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if is_user_banned(callback.from_user.id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return
    ticket_id = int(callback.data.split("_")[-1])
    await state.set_state(SupportStates.awaiting_message)
    await state.update_data(support_ticket_id=ticket_id)
    await callback.message.answer(
        f"💬 <b>Reply to Ticket #{ticket_id}</b>\n\n"
        "Type your follow-up message and press Send.",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(SupportStates.awaiting_message)
async def support_receive_message(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username or str(user_id)
    text = (message.text or "").strip()

    if not text:
        await message.answer("❌ Please send a text message for your support ticket.")
        return

    if len(text) > 2000:
        await message.answer("❌ Message is too long. Please keep it under 2000 characters.")
        return

    data = await state.get_data()
    ticket_id = data.get("support_ticket_id")

    conn = get_db_connection()
    cur = conn.cursor()

    if ticket_id is None:
        # Check for existing open ticket
        cur.execute(
            "SELECT ticket_id FROM support_tickets WHERE user_id = ? AND status = 'open'"
            " ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        existing = cur.fetchone()
        if existing:
            ticket_id = existing[0]
            cur.execute(
                "UPDATE support_tickets SET last_message_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
                (ticket_id,),
            )
        else:
            # Create new ticket
            subject = text[:80] + ("…" if len(text) > 80 else "")
            cur.execute(
                "INSERT INTO support_tickets (user_id, username, status, subject) VALUES (?, ?, ?, ?)",
                (user_id, username, "open", subject),
            )
            ticket_id = cur.lastrowid

    # Add message to ticket
    cur.execute(
        "INSERT INTO support_messages (ticket_id, sender_type, sender_id, message_text) VALUES (?, ?, ?, ?)",
        (ticket_id, "user", user_id, text),
    )
    cur.execute(
        "UPDATE support_tickets SET last_message_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
        (ticket_id,),
    )
    conn.commit()
    conn.close()

    # Confirm to user
    await message.answer(
        SUPPORT_TICKET_CREATED.format(ticket_id=ticket_id),
        parse_mode="HTML",
        reply_markup=get_user_support_reply_keyboard(ticket_id),
    )
    await state.clear()

    # Notify admins
    admin_notif = SUPPORT_ADMIN_TICKET.format(
        ticket_id=ticket_id,
        user_id=user_id,
        username=username,
        subject=text[:80],
        message_text=text,
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=admin_notif,
                parse_mode="HTML",
                reply_markup=get_admin_support_keyboard(ticket_id),
            )
        except Exception as e:
            print(f"[support] Failed to notify admin {admin_id}: {e}")


@router.callback_query(F.data == "support_my_tickets")
async def support_my_tickets(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT ticket_id, status, subject, last_message_at FROM support_tickets"
        " WHERE user_id = ? ORDER BY last_message_at DESC LIMIT 5",
        (user_id,),
    )
    tickets = cur.fetchall()
    conn.close()

    if not tickets:
        text = (
            "📋 <b>My Support Tickets</b>\n\n"
            "<i>You have no support tickets yet.</i>\n\n"
            "Tap 'Open Support Ticket' to create one."
        )
    else:
        text = "📋 <b>My Support Tickets (last 5)</b>\n\n"
        for t in tickets:
            status_icon = "🟢" if t[1] == "open" else "🔴"
            text += (
                f"{status_icon} <b>Ticket #{t[0]}</b> — {t[1].upper()}\n"
                f"   {t[2] or 'No subject'}\n"
                f"   Last update: {format_timestamp(t[3])}\n\n"
            )

    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=get_support_keyboard())


# ── Admin support panel ────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_support")
async def admin_support_panel(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT ticket_id, user_id, username, subject, last_message_at FROM support_tickets"
        " WHERE status = 'open' ORDER BY last_message_at DESC LIMIT 15",
    )
    tickets = cur.fetchall()
    conn.close()

    if not tickets:
        text = "💬 <b>Support Tickets</b>\n\n<i>No open tickets. ✅</i>"
    else:
        text = f"💬 <b>Open Support Tickets ({len(tickets)})</b>\n\n"
        for t in tickets:
            text += (
                f"🎟️ <b>#{t[0]}</b> — @{t[2]} (<code>{t[1]}</code>)\n"
                f"   {t[3] or 'No subject'}\n"
                f"   {format_timestamp(t[4])}\n\n"
            )

    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=get_admin_support_panel_keyboard())


@router.callback_query(lambda c: c.data and c.data.startswith("admin_support_reply_"))
async def admin_support_reply_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    ticket_id = int(callback.data.split("_")[-1])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username FROM support_tickets WHERE ticket_id = ?", (ticket_id,)
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        await callback.answer("⚠️ Ticket not found.", show_alert=True)
        return

    await state.set_state(AdminStates.replying_support)
    await state.update_data(support_ticket_id=ticket_id, support_user_id=row[0], support_username=row[1])
    await callback.message.answer(
        f"✉️ <b>Reply to Ticket #{ticket_id}</b>\n\n"
        f"User: @{row[1]} (<code>{row[0]}</code>)\n\n"
        "Type your reply and press Send:",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(AdminStates.replying_support)
async def admin_support_reply_send(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ Reply cannot be empty.")
        return

    data = await state.get_data()
    ticket_id = data.get("support_ticket_id")
    user_id = data.get("support_user_id")
    username = data.get("support_username")

    # Save admin reply
    execute_db(
        "INSERT INTO support_messages (ticket_id, sender_type, sender_id, message_text) VALUES (?, ?, ?, ?)",
        (ticket_id, "admin", message.from_user.id, text), commit=True,
    )
    execute_db(
        "UPDATE support_tickets SET last_message_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
        (ticket_id,), commit=True,
    )

    # Send reply to user
    try:
        await bot.send_message(
            chat_id=user_id,
            text=SUPPORT_TICKET_REPLY.format(ticket_id=ticket_id, reply_text=text),
            parse_mode="HTML",
            reply_markup=get_user_support_reply_keyboard(ticket_id),
        )
        await message.answer(f"✅ Reply sent to @{username} (Ticket #{ticket_id}).")
    except Exception as e:
        await message.answer(f"⚠️ Could not deliver reply to user: {e}")

    await state.clear()


@router.callback_query(lambda c: c.data and c.data.startswith("admin_support_close_"))
async def admin_support_close(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    ticket_id = int(callback.data.split("_")[-1])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM support_tickets WHERE ticket_id = ?", (ticket_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        await callback.answer("⚠️ Ticket not found.", show_alert=True)
        return
    user_id = row[0]
    cur.execute("UPDATE support_tickets SET status = 'closed' WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()

    try:
        await bot.send_message(
            chat_id=user_id,
            text=SUPPORT_TICKET_CLOSED.format(ticket_id=ticket_id),
            parse_mode="HTML",
            reply_markup=get_start_keyboard(),
        )
    except Exception:
        pass

    await callback.message.answer(f"✅ Ticket #{ticket_id} closed.")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ── Withdraw flow ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "withdraw")
async def withdraw_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if is_user_banned(callback.from_user.id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Withdraw INR", callback_data="withdraw_inr")],
        [InlineKeyboardButton(text="₨ Withdraw NPR",  callback_data="withdraw_npr")],
        [InlineKeyboardButton(text="🔙 Back",          callback_data="back_to_start")],
    ])
    await _safe_edit(callback, "💸 <b>Withdraw Funds</b>\n\nSelect currency to withdraw:", parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "withdraw_inr")
async def withdraw_inr(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if is_user_banned(callback.from_user.id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return
    user_info = get_user_info(callback.from_user.id)
    balance = format_currency(user_info.get("wallet_inr") or 0, "INR") if user_info else "₹0.00"
    await state.set_state(WithdrawalStates.entering_withdraw_amount)
    await state.update_data(withdraw_currency="INR")
    await _safe_edit(
        callback,
        f"💵 <b>Withdraw INR</b>\n\nYour balance: <b>{balance}</b>\n\nEnter amount to withdraw:",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.callback_query(F.data == "withdraw_npr")
async def withdraw_npr(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if is_user_banned(callback.from_user.id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return
    user_info = get_user_info(callback.from_user.id)
    balance = format_currency(user_info.get("wallet_npr") or 0, "NPR") if user_info else "₨0.00"
    await state.set_state(WithdrawalStates.entering_withdraw_amount)
    await state.update_data(withdraw_currency="NPR")
    await _safe_edit(
        callback,
        f"₨ <b>Withdraw NPR</b>\n\nYour balance: <b>{balance}</b>\n\nEnter amount to withdraw:",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(WithdrawalStates.entering_withdraw_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    is_valid, result = validate_amount(message.text or "")
    if not is_valid:
        await message.answer(f"❌ {result}", parse_mode="HTML")
        return

    amount = result
    data = await state.get_data()
    currency = data.get("withdraw_currency", "INR")
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    wallet_inr = float(user_info["wallet_inr"] or 0) if user_info else 0
    wallet_npr = float(user_info["wallet_npr"] or 0) if user_info else 0

    if currency == "INR" and wallet_inr < amount:
        await message.answer(
            f"⚠️ <b>Insufficient INR Balance</b>\n\n"
            f"• Requested: {format_currency(amount, 'INR')}\n"
            f"• Your balance: {format_currency(wallet_inr, 'INR')}",
            parse_mode="HTML", reply_markup=get_back_button(),
        )
        await state.clear()
        return
    if currency == "NPR" and wallet_npr < amount:
        await message.answer(
            f"⚠️ <b>Insufficient NPR Balance</b>\n\n"
            f"• Requested: {format_currency(amount, 'NPR')}\n"
            f"• Your balance: {format_currency(wallet_npr, 'NPR')}",
            parse_mode="HTML", reply_markup=get_back_button(),
        )
        await state.clear()
        return

    await state.update_data(withdraw_amount=amount)
    await state.set_state(WithdrawalStates.entering_withdraw_account)
    await message.answer(
        "🏦 <b>Receiving Account</b>\n\n"
        "Please send the UPI ID, eSewa number, or bank account details where we should send the funds.",
        parse_mode="HTML", reply_markup=get_cancel_button(),
    )


@router.message(WithdrawalStates.entering_withdraw_account)
async def receive_withdraw_account(message: Message, state: FSMContext, bot: Bot):
    account = (message.text or "").strip()
    if not account or len(account) < 3:
        await message.answer("❌ Please provide a valid account / UPI ID.")
        return

    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    currency = data.get("withdraw_currency", "INR")
    amount = float(data.get("withdraw_amount", 0))

    request_id = execute_db(
        "INSERT INTO exchange_requests"
        " (user_id, username, exchange_type, amount, exchange_rate, calculated_amount,"
        "  service_fee, final_amount, transaction_id, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, f"WITHDRAW_{currency}", amount, 1.0, amount, 0.0, amount, account, "pending"),
        commit=True,
    )

    # Reserve funds
    try:
        conn2 = get_db_connection()
        cur2 = conn2.cursor()
        if currency == "INR":
            cur2.execute(
                "UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) - ? WHERE user_id = ? AND COALESCE(wallet_inr,0) >= ?",
                (amount, user_id, amount),
            )
        else:
            cur2.execute(
                "UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) - ? WHERE user_id = ? AND COALESCE(wallet_npr,0) >= ?",
                (amount, user_id, amount),
            )

        if cur2.rowcount == 0:
            conn2.close()
            execute_db("DELETE FROM exchange_requests WHERE request_id = ?", (request_id,), commit=True)
            await message.answer("⚠️ Could not reserve funds. Please try again.")
            await state.clear()
            return

        cur2.execute(
            "INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, request_id, "debit", amount, currency, "held"),
        )
        conn2.commit()
        conn2.close()
    except Exception as e:
        print(f"[withdraw_reserve] Error: {e}")

    await message.answer(
        f"✅ <b>Withdrawal #{request_id} Submitted</b>\n\n"
        f"• Currency: <b>{currency}</b>\n"
        f"• Amount: <b>{format_currency(amount, currency)}</b>\n"
        f"• Destination: <code>{account}</code>\n\n"
        "Admin will process your withdrawal shortly. You'll be notified.",
        parse_mode="HTML",
        reply_markup=get_start_keyboard(),
    )

    notify_data = {
        "exchange_type": f"WITHDRAW_{currency}",
        "amount": amount,
        "from_currency": currency,
        "to_currency": currency,
        "final_amount": amount,
        "exchange_rate": 1.0,
        "screenshot_file_id": None,
    }
    await notify_admin(user_id, username, notify_data, account, request_id, bot)
    await state.clear()


# ── Load Wallet flow ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "load_inr")
async def load_inr(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if is_user_banned(callback.from_user.id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return
    await state.set_state(WalletStates.entering_load_amount)
    await state.update_data(load_currency="INR")
    await _safe_edit(
        callback,
        "💵 <b>Load INR Wallet</b>\n\nEnter the amount of INR you want to load:",
        parse_mode="HTML", reply_markup=get_cancel_button(),
    )


@router.callback_query(F.data == "load_npr")
async def load_npr(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if is_user_banned(callback.from_user.id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return
    await state.set_state(WalletStates.entering_load_amount)
    await state.update_data(load_currency="NPR")
    await _safe_edit(
        callback,
        "₨ <b>Load NPR Wallet</b>\n\nEnter the amount of NPR you want to load:",
        parse_mode="HTML", reply_markup=get_cancel_button(),
    )


@router.message(WalletStates.entering_load_amount)
async def process_wallet_load_amount(message: Message, state: FSMContext, bot: Bot):
    is_valid, result = validate_amount(message.text or "")
    if not is_valid:
        await message.answer(f"❌ {result}", parse_mode="HTML")
        return

    amount = result
    data = await state.get_data()
    load_currency = data.get("load_currency", "INR")
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    exchange_type = "LOAD_INR" if load_currency == "INR" else "LOAD_NPR"

    await state.update_data(
        exchange_type=exchange_type,
        amount=amount,
        exchange_rate=1.0,
        calculated_amount=amount,
        service_fee=0.0,
        final_amount=amount,
        from_currency=load_currency,
        to_currency=load_currency,
    )

    upi_id, esewa_id = get_payment_details()
    payment_msg = PAYMENT_INSTRUCTIONS.format(upi_id=upi_id, esewa_id=esewa_id, user_id=user_id)

    try:
        await message.answer_photo(
            photo=BANNER_IMAGE_URL,
            caption=payment_msg,
            parse_mode="HTML",
            reply_markup=get_payment_keyboard(),
        )
    except Exception:
        await message.answer(payment_msg, parse_mode="HTML", reply_markup=get_payment_keyboard())

    await state.set_state(ExchangeStates.waiting_payment)


# ── Navigation ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    welcome = _build_welcome()
    try:
        await callback.message.edit_text(welcome, parse_mode="HTML", reply_markup=get_start_keyboard())
    except Exception:
        try:
            await callback.message.answer(welcome, parse_mode="HTML", reply_markup=get_start_keyboard())
        except Exception:
            pass


@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return
    await _safe_edit(callback, "🔧 <b>Admin Panel</b>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())


# ── Admin panel ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_pending")
async def admin_pending(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT request_id, user_id, username, exchange_type, amount, final_amount, created_at"
        " FROM exchange_requests WHERE status = 'pending' ORDER BY created_at ASC LIMIT 15"
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await _safe_edit(
            callback,
            "📋 <b>Pending Requests</b>\n\n✅ No pending requests!",
            parse_mode="HTML",
            reply_markup=get_admin_menu_keyboard(),
        )
        return

    # Build message + per-request action buttons
    text = f"📋 <b>Pending Requests ({len(rows)})</b>\n\n"
    buttons = []
    for r in rows:
        from_c, to_c = get_exchange_currencies(r[3])
        text += (
            f"<b>#{r[0]}</b> @{r[2]} — {get_exchange_type_display(r[3])}\n"
            f"   {format_currency(r[4], from_c)} → {format_currency(r[5], to_c)} | {format_timestamp(r[6])}\n\n"
        )
        buttons.append([
            InlineKeyboardButton(text=f"✅ Approve #{r[0]}", callback_data=f"admin_approve_{r[0]}"),
            InlineKeyboardButton(text=f"❌ Reject #{r[0]}",  callback_data=f"admin_reject_{r[0]}"),
        ])

    buttons.append([InlineKeyboardButton(text="🔙 Admin Panel", callback_data="back_to_admin")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "admin_completed")
async def admin_completed(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT request_id, username, exchange_type, amount, final_amount, completed_at"
        " FROM exchange_requests WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 20"
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await _safe_edit(callback, "<b>No completed requests yet.</b>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())
        return

    text = f"✅ <b>Completed (last {len(rows)})</b>\n\n"
    for r in rows:
        from_c, to_c = get_exchange_currencies(r[2])
        text += (
            f"<b>#{r[0]}</b> @{r[1]} — {get_exchange_type_display(r[2])}\n"
            f"   {format_currency(r[3], from_c)} → {format_currency(r[4], to_c)} | {format_timestamp(r[5])}\n\n"
        )
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT log_id, admin_id, action, request_id, details, created_at"
        " FROM admin_logs ORDER BY created_at DESC LIMIT 20"
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await _safe_edit(callback, "<b>No admin logs yet.</b>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())
        return

    text = "📋 <b>Admin Logs (last 20)</b>\n\n"
    for r in rows:
        req = f"req#{r[3]}" if r[3] else "—"
        text += f"[{format_timestamp(r[5])}] <b>{r[2].upper()}</b> by {r[1]} on {req}\n"
        if r[4]:
            text += f"   <i>{r[4][:80]}</i>\n"
        text += "\n"

    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    s = get_bot_stats()
    text = ADMIN_STATS.format(
        total_users=s["total_users"],
        new_users=s["new_users"],
        active_today=s["active_today"],
        total_transactions=s["total_transactions"],
        completed=s["completed"],
        pending=s["pending"],
        rejected=s["rejected"],
        total_inr=format_currency(s["total_inr"], "INR"),
        total_npr=format_currency(s["total_npr"], "NPR"),
        total_fees=format_currency(s["total_fees"], "INR"),
        inr_to_npr=s["inr_to_npr"],
        npr_to_inr=s["npr_to_inr"],
        open_tickets=s["open_tickets"],
        updated_at=format_timestamp(datetime.now()),
    )
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "admin_settings")
async def admin_settings_menu(callback: CallbackQuery):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return
    await _safe_edit(callback, "⚙️ <b>Settings</b>\n\nChoose what to update:", parse_mode="HTML", reply_markup=get_settings_keyboard())


# ── Admin: approve ─────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("admin_approve_"))
async def admin_approve(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    admin_id = callback.from_user.id
    request_id = int(callback.data.split("_")[-1])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, username, exchange_type, amount, final_amount, status"
        " FROM exchange_requests WHERE request_id = ?",
        (request_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        await callback.answer("⚠️ Request not found.", show_alert=True)
        return

    user_id, username, exchange_type, amount, final_amount, status = row

    if status != "pending":
        await callback.answer(f"⚠️ Already {status}.", show_alert=True)
        return

    from_c, to_c = get_exchange_currencies(exchange_type)

    # Mark approved
    execute_db(
        "UPDATE exchange_requests SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE request_id = ?",
        (request_id,), commit=True,
    )
    execute_db(
        "INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)",
        (admin_id, "approve", request_id, "Approved"), commit=True,
    )

    # Notify user
    try:
        await bot.send_message(
            chat_id=user_id,
            text=APPROVED_MESSAGE.format(
                request_id=request_id,
                final_amount=format_currency(final_amount, to_c),
                to_currency=to_c,
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"[approve] Notify user error: {e}")

    # Wallet-load / exchange: handle differently
    if exchange_type in ("LOAD_INR", "LOAD_NPR"):
        # Immediately credit wallet for load requests
        conn2 = get_db_connection()
        cur2 = conn2.cursor()
        cur2.execute(
            "UPDATE exchange_requests SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE request_id = ?",
            (request_id,),
        )
        if exchange_type == "LOAD_INR":
            cur2.execute(
                "UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) + ? WHERE user_id = ?",
                (final_amount, user_id),
            )
        else:
            cur2.execute(
                "UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?",
                (final_amount, user_id),
            )
        cur2.execute(
            "INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, request_id, "wallet_load", final_amount, to_c, "completed"),
        )
        cur2.execute(
            "INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)",
            (admin_id, "wallet_credit", request_id, "Wallet load credited"),
        )
        conn2.commit()
        conn2.close()

        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        try:
            await bot.send_message(
                chat_id=user_id,
                text=COMPLETED_MESSAGE.format(
                    request_id=request_id,
                    sent_amount=format_currency(final_amount, from_c),
                    from_currency=from_c,
                    received_amount=format_currency(final_amount, to_c),
                    to_currency=to_c,
                    service_fee="0.00",
                    timestamp=timestamp,
                ),
                parse_mode="HTML",
                reply_markup=get_start_keyboard(),
            )
        except Exception:
            pass

        await callback.answer("✅ Wallet load approved & credited.")

    else:
        # For exchanges / withdrawals — give admin a "Mark Paid" button
        try:
            mark_paid_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Mark Paid / Done", callback_data=f"admin_paid_{request_id}"),
                InlineKeyboardButton(text="❌ Reject",           callback_data=f"rr_{request_id}_1"),
            ]])
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    f"✅ <b>Request #{request_id} Approved</b>\n\n"
                    f"Now send the payout to @{username}.\n"
                    f"Click <b>Mark Paid</b> once you've transferred the funds."
                ),
                parse_mode="HTML",
                reply_markup=mark_paid_kb,
            )
        except Exception:
            pass

        await callback.answer("✅ Approved — send payout & mark paid.")
        _apply_referral_bonus(user_id, username, request_id, final_amount, to_c, bot)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ── Admin: mark paid ───────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("admin_paid_"))
async def admin_mark_paid(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    admin_id = callback.from_user.id
    request_id = int(callback.data.split("_")[-1])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, username, exchange_type, final_amount, status"
        " FROM exchange_requests WHERE request_id = ?",
        (request_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        await callback.answer("⚠️ Request not found.", show_alert=True)
        return
    user_id, username, exchange_type, final_amount, status = row
    conn.close()

    if status != "approved":
        await callback.answer(f"⚠️ Request is {status} (must be approved).", show_alert=True)
        return

    try:
        final_amount = float(final_amount)
    except Exception:
        final_amount = 0.0

    from_c, to_c = get_exchange_currencies(exchange_type)

    conn2 = get_db_connection()
    cur2 = conn2.cursor()

    # Credit destination wallet (not for withdrawals)
    if exchange_type == "INR_TO_NPR":
        cur2.execute(
            "UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?",
            (final_amount, user_id),
        )
    elif exchange_type == "NPR_TO_INR":
        cur2.execute(
            "UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) + ? WHERE user_id = ?",
            (final_amount, user_id),
        )

    cur2.execute(
        "UPDATE exchange_requests SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE request_id = ?",
        (request_id,),
    )
    cur2.execute(
        "INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, request_id, "payout", final_amount, to_c, "completed"),
    )
    cur2.execute(
        "INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)",
        (admin_id, "paid", request_id, "Payout confirmed"),
    )
    cur2.execute(
        "UPDATE transactions SET status = 'completed'"
        " WHERE exchange_request_id = ? AND transaction_type = 'debit' AND status = 'held'",
        (request_id,),
    )
    conn2.commit()
    conn2.close()

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    try:
        await bot.send_message(
            chat_id=user_id,
            text=COMPLETED_MESSAGE.format(
                request_id=request_id,
                sent_amount=format_currency(final_amount, from_c),
                from_currency=from_c,
                received_amount=format_currency(final_amount, to_c),
                to_currency=to_c,
                service_fee="0.00",
                timestamp=timestamp,
            ),
            parse_mode="HTML",
            reply_markup=get_start_keyboard(),
        )
    except Exception:
        pass

    try:
        await bot.send_message(
            chat_id=admin_id,
            text=f"✅ Request #{request_id} marked as paid to @{username}.",
        )
    except Exception:
        pass

    await callback.answer("✅ Marked as paid.")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ── Admin: reject (with reason) ────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("admin_reject_"))
async def admin_reject_prompt(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return
    await callback.answer()
    request_id = int(callback.data.split("_")[-1])
    await callback.message.answer(
        f"❌ <b>Reject Request #{request_id}</b>\n\nSelect a reason:",
        parse_mode="HTML",
        reply_markup=get_reject_reason_keyboard(request_id),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("rr_"))
async def admin_reject_reason(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    await callback.answer()
    parts = callback.data.split("_")
    # data format: rr_{request_id}_{code}
    request_id = int(parts[1])
    reason_code = parts[2]

    if reason_code == "6":
        # Custom reason — ask admin to type it
        await state.set_state(AdminStates.entering_reject_reason)
        await state.update_data(reject_request_id=request_id)
        await callback.message.answer(
            "✏️ Type the custom reject reason and press Send:",
            reply_markup=get_cancel_button(),
        )
        return

    reason_text = REJECT_REASONS.get(reason_code, "Unknown reason")
    await _do_reject(request_id, callback.from_user.id, reason_text, bot)
    await callback.message.answer(f"❌ Request #{request_id} rejected. Reason: {reason_text}")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.message(AdminStates.entering_reject_reason)
async def admin_reject_custom_reason(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    reason_text = (message.text or "").strip()
    if not reason_text:
        await message.answer("❌ Reason cannot be empty.")
        return

    data = await state.get_data()
    request_id = data.get("reject_request_id")
    await _do_reject(request_id, message.from_user.id, reason_text, bot)
    await message.answer(f"❌ Request #{request_id} rejected. Reason: {reason_text}")
    await state.clear()


async def _do_reject(request_id: int, admin_id: int, reason: str, bot: Bot):
    """Common reject logic: update DB, refund, and notify user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM exchange_requests WHERE request_id = ?", (request_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
    user_id = row[0]
    cursor.execute(
        "UPDATE exchange_requests SET status = 'rejected', admin_notes = ? WHERE request_id = ?",
        (reason, request_id),
    )
    cursor.execute(
        "INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)",
        (admin_id, "reject", request_id, reason),
    )
    conn.commit()
    conn.close()

    _do_refund(request_id, user_id)

    try:
        await bot.send_message(
            chat_id=user_id,
            text=REJECTED_MESSAGE.format(request_id=request_id, reason=reason),
            parse_mode="HTML",
            reply_markup=get_start_keyboard(),
        )
    except Exception as e:
        print(f"[reject] Notify user error: {e}")


# ── Admin: message user (per request) ─────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("admin_message_"))
async def admin_message_user_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return
    await callback.answer()
    request_id = int(callback.data.split("_")[-1])
    row = execute_db("SELECT user_id FROM exchange_requests WHERE request_id = ?", (request_id,), fetchone=True)
    if not row:
        await callback.answer("⚠️ Request not found.", show_alert=True)
        return
    await state.set_state(AdminStates.messaging_user)
    await state.update_data(target_user=row[0], request_id=request_id)
    await callback.message.answer(
        f"✉️ <b>Message User (Request #{request_id})</b>\n\nType your message:",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(AdminStates.messaging_user)
async def admin_send_message_to_user(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    data = await state.get_data()
    target_user = data.get("target_user")
    request_id = data.get("request_id")
    try:
        await bot.send_message(
            chat_id=target_user,
            text=f"📨 <b>Message from Support (Request #{request_id}):</b>\n\n{message.text}",
            parse_mode="HTML",
        )
        execute_db(
            "INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)",
            (message.from_user.id, "message_user", request_id, (message.text or "")[:200]),
            commit=True,
        )
        await message.answer("✅ Message sent to user.")
    except Exception as e:
        await message.answer(f"⚠️ Failed: {e}")
    await state.clear()


# ── Admin: rate settings ───────────────────────────────────────────────────────

@router.callback_query(F.data == "set_rate")
async def set_rate_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return
    await callback.answer()
    inr_to_npr = get_exchange_rate("INR_TO_NPR") or "?"
    npr_to_inr = get_exchange_rate("NPR_TO_INR") or "?"
    await state.set_state(AdminStates.setting_rate)
    await callback.message.answer(
        f"📈 <b>Update Exchange Rate</b>\n\n"
        f"Current rates:\n• INR→NPR: <b>{inr_to_npr}</b>\n• NPR→INR: <b>{npr_to_inr}</b>\n\n"
        "Send new rate in format:\n"
        "<code>inr_to_npr 1.60</code>  or  <code>npr_to_inr 0.625</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(AdminStates.setting_rate)
async def set_rate_receive(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("❌ Format: <code>inr_to_npr 1.60</code>", parse_mode="HTML")
        return
    name, value = parts[0].lower(), parts[1]
    try:
        float(value)
    except ValueError:
        await message.answer("❌ Rate must be a number.")
        return
    if name not in ("inr_to_npr", "npr_to_inr"):
        await message.answer("❌ Use <code>inr_to_npr</code> or <code>npr_to_inr</code>.", parse_mode="HTML")
        return
    key = name if name.endswith("_rate") else name + "_rate"
    execute_db(
        "INSERT OR REPLACE INTO admin_settings (setting_name, setting_value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, value), commit=True,
    )
    await message.answer(f"✅ Rate updated: <b>{key}</b> = <b>{value}</b>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())
    await state.clear()


# ── Admin: payment settings ────────────────────────────────────────────────────

@router.callback_query(F.data == "update_payment")
async def update_payment_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return
    await callback.answer()
    upi_id, esewa_id = get_payment_details()
    await state.set_state(AdminStates.updating_payment)
    await callback.message.answer(
        f"💳 <b>Update Payment Details</b>\n\n"
        f"Current:\n• UPI: <code>{upi_id}</code>\n• eSewa: <code>{esewa_id}</code>\n\n"
        "Send new details:\n"
        "<code>upi business@upi</code>  or  <code>esewa esewa_id</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(AdminStates.updating_payment)
async def update_payment_receive(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("❌ Format: <code>upi business@upi</code>", parse_mode="HTML")
        return
    name, value = parts[0].lower(), parts[1]
    if name not in ("upi", "esewa"):
        await message.answer("❌ Use <code>upi</code> or <code>esewa</code>.", parse_mode="HTML")
        return
    key = "upi_id" if name == "upi" else "esewa_id"
    execute_db(
        "INSERT OR REPLACE INTO admin_settings (setting_name, setting_value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, value), commit=True,
    )
    await message.answer(f"✅ Updated <b>{key}</b> = <code>{value}</code>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())
    await state.clear()


# ── Admin: broadcast ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return
    await callback.answer()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE is_banned = 0")
    total = cur.fetchone()[0]
    conn.close()
    await state.set_state(AdminStates.broadcasting)
    await callback.message.answer(
        f"📢 <b>Broadcast to {total} users</b>\n\n"
        "Type your message (HTML supported) and press Send.\n\n"
        "<i>Bold: <code>&lt;b&gt;text&lt;/b&gt;</code></i>",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(AdminStates.broadcasting)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    text = message.text or ""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = cursor.fetchall()
    conn.close()

    progress = await message.answer(f"📢 Sending to {len(users)} users…")
    sent, failed = 0, 0
    for u in users:
        try:
            await bot.send_message(chat_id=u[0], text=text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        if (sent + failed) % 20 == 0:
            await asyncio.sleep(0.5)  # Avoid hitting rate limits

    try:
        await progress.delete()
    except Exception:
        pass
    await message.answer(
        f"📢 <b>Broadcast Complete</b>\n\n✅ Sent: {sent}\n❌ Failed: {failed}",
        parse_mode="HTML",
        reply_markup=get_admin_menu_keyboard(),
    )
    await state.clear()


# ── Admin: /credit and /balance ────────────────────────────────────────────────

@router.message(lambda msg: msg.text and msg.text.startswith("/credit"))
async def admin_credit(message: Message, bot: Bot):
    """Usage: /credit add|set <user_id|@username> <INR|NPR> <amount>"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 5:
        await message.answer(
            "❌ Format: <code>/credit add|set &lt;user_id|@username&gt; &lt;INR|NPR&gt; &lt;amount&gt;</code>",
            parse_mode="HTML",
        )
        return

    _, action, target, currency, amt_str = parts
    action, currency = action.lower(), currency.upper()

    if action not in ("add", "set"):
        await message.answer("❌ Action must be <code>add</code> or <code>set</code>.", parse_mode="HTML")
        return
    if currency not in ("INR", "NPR"):
        await message.answer("❌ Currency must be <code>INR</code> or <code>NPR</code>.", parse_mode="HTML")
        return
    try:
        amount = float(amt_str)
        if amount < 0:
            raise ValueError
    except Exception:
        await message.answer("❌ Amount must be a non-negative number.")
        return

    if target.startswith("@"):
        row = execute_db("SELECT user_id FROM users WHERE username = ?", (target[1:],), fetchone=True)
        if not row:
            await message.answer(f"⚠️ User {target} not found.")
            return
        target_user_id = row[0]
    else:
        try:
            target_user_id = int(target)
        except Exception:
            await message.answer("❌ Invalid user ID.")
            return

    if currency == "INR":
        q = "UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) + ? WHERE user_id = ?" if action == "add" else \
            "UPDATE users SET wallet_inr = ? WHERE user_id = ?"
    else:
        q = "UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?" if action == "add" else \
            "UPDATE users SET wallet_npr = ? WHERE user_id = ?"
    execute_db(q, (amount, target_user_id), commit=True)

    detail = f"Admin {action} {currency} {amount} for user {target_user_id}"
    execute_db(
        "INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (target_user_id, None, "admin_credit", amount, currency, "completed"), commit=True,
    )
    execute_db(
        "INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)",
        (message.from_user.id, "admin_credit", None, detail), commit=True,
    )

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT wallet_inr, wallet_npr FROM users WHERE user_id = ?", (target_user_id,))
    bal = cur.fetchone()
    conn.close()
    inr_bal = bal[0] or 0 if bal else 0
    npr_bal = bal[1] or 0 if bal else 0

    await message.answer(
        f"✅ {detail}\n\nNew balances:\n"
        f"• INR: {format_currency(inr_bal, 'INR')}\n"
        f"• NPR: {format_currency(npr_bal, 'NPR')}",
        parse_mode="HTML",
    )
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=(
                f"🔔 <b>Wallet Updated by Admin</b>\n\n"
                f"• {currency} {action}ed: {format_currency(amount, currency)}\n\n"
                f"New balances:\n"
                f"• INR: {format_currency(inr_bal, 'INR')}\n"
                f"• NPR: {format_currency(npr_bal, 'NPR')}"
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(lambda msg: msg.text and msg.text.startswith("/balance"))
async def admin_balance(message: Message):
    """Usage: /balance <user_id|@username>"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("❌ Format: <code>/balance &lt;user_id|@username&gt;</code>", parse_mode="HTML")
        return
    target = parts[1]
    if target.startswith("@"):
        row = execute_db("SELECT user_id FROM users WHERE username = ?", (target[1:],), fetchone=True)
        if not row:
            await message.answer(f"⚠️ User {target} not found.")
            return
        target_user_id = row[0]
    else:
        try:
            target_user_id = int(target)
        except Exception:
            await message.answer("❌ Invalid user ID.")
            return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT username, wallet_inr, wallet_npr, total_exchanges, is_banned FROM users WHERE user_id = ?",
        (target_user_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        await message.answer("⚠️ User not found.")
        return

    username, wallet_inr, wallet_npr, total_exchanges, is_banned = row
    banned_tag = " 🚫 BANNED" if is_banned else ""
    await message.answer(
        f"👤 <b>@{username}</b> (<code>{target_user_id}</code>){banned_tag}\n\n"
        f"💵 INR: <b>{format_currency(wallet_inr or 0, 'INR')}</b>\n"
        f"₨  NPR: <b>{format_currency(wallet_npr or 0, 'NPR')}</b>\n"
        f"📊 Total exchanges: {total_exchanges or 0}",
        parse_mode="HTML",
    )


# ── Admin: /ban and /unban ─────────────────────────────────────────────────────

@router.message(lambda msg: msg.text and msg.text.startswith("/ban "))
async def admin_ban(message: Message, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("❌ Format: <code>/ban &lt;user_id&gt;</code>", parse_mode="HTML")
        return
    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ user_id must be a number.")
        return

    execute_db("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_user_id,), commit=True)
    execute_db(
        "INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)",
        (message.from_user.id, "ban", None, f"Banned user {target_user_id}"), commit=True,
    )
    await message.answer(f"🚫 User <code>{target_user_id}</code> has been banned.", parse_mode="HTML")
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text="🚫 <b>Account Suspended</b>\n\nYour account has been suspended. Please contact support if you believe this is an error.",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(lambda msg: msg.text and msg.text.startswith("/unban "))
async def admin_unban(message: Message, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        return
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("❌ Format: <code>/unban &lt;user_id&gt;</code>", parse_mode="HTML")
        return
    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ user_id must be a number.")
        return

    execute_db("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_user_id,), commit=True)
    execute_db(
        "INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)",
        (message.from_user.id, "unban", None, f"Unbanned user {target_user_id}"), commit=True,
    )
    await message.answer(f"✅ User <code>{target_user_id}</code> has been unbanned.", parse_mode="HTML")
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text="✅ <b>Account Reinstated</b>\n\nYour account suspension has been lifted. Welcome back!",
            parse_mode="HTML",
            reply_markup=get_start_keyboard(),
        )
    except Exception:
        pass


# ── Startup: register bot commands ─────────────────────────────────────────────

@router.startup()
async def set_bot_commands_on_startup(bot: Bot):
    commands = [
        BotCommand(command="start",    description="Main menu"),
        BotCommand(command="help",     description="Help & commands"),
        BotCommand(command="profile",  description="Your profile"),
        BotCommand(command="wallet",   description="Wallet balances"),
        BotCommand(command="load",     description="Load wallet"),
        BotCommand(command="history",  description="Transaction history"),
        BotCommand(command="withdraw", description="Withdraw funds"),
        BotCommand(command="admin",    description="Admin panel (admin only)"),
        BotCommand(command="credit",   description="Adjust wallet (admin only)"),
        BotCommand(command="balance",  description="View user balance (admin only)"),
        BotCommand(command="ban",      description="Ban a user (admin only)"),
        BotCommand(command="unban",    description="Unban a user (admin only)"),
        BotCommand(command="restart",  description="Update & restart (admin only)"),
    ]
    try:
        await bot.set_my_commands(commands)
        print("✅ Bot commands registered.")
    except Exception as e:
        print(f"⚠️ Failed to set commands: {e}")
