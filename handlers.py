import html
import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, URLInputFile, ReplyKeyboardRemove
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import (
    ADMIN_IDS, BANNER_IMAGE_URL,
    DEFAULT_INR_TO_NPR_RATE, DEFAULT_NPR_TO_INR_RATE,
    SERVICE_FEE_PERCENTAGE, REFERRAL_BONUS_PERCENT,
    ENABLE_DYNAMIC_QR, ENABLE_REFERRAL
)
from database import (
    get_db_connection, add_or_update_user, get_user_by_referral_code,
    get_referred_users_count, atomic_deduct_wallet, atomic_add_wallet, search_records
)
from keyboards import (
    get_start_reply_keyboard, get_quick_amount_reply_keyboard,
    get_exchange_confirm_reply_keyboard, get_payment_reply_keyboard,
    get_load_currency_reply_keyboard, get_cancel_reply_keyboard,
    get_admin_approval_keyboard, get_reject_reason_keyboard,
    get_admin_menu_keyboard, get_admin_support_keyboard, REJECT_REASONS
)
from messages import (
    WELCOME_MESSAGE, ENTER_AMOUNT,
    EXCHANGE_SUMMARY, PAYMENT_INSTRUCTIONS, PAYMENT_VERIFICATION,
    PAYMENT_ASK_TXN_ID, ADMIN_REQUEST, APPROVED_MESSAGE,
    REJECTED_MESSAGE, CURRENT_RATE,
    WALLET_MENU, TRANSACTION_HISTORY,
    HOW_IT_WORKS, PROFILE_MESSAGE, SUPPORT_MENU,
    SUPPORT_TICKET_CREATED, ADMIN_STATS, ERROR_MESSAGES,
    ABOUT_US_MESSAGE, CONTACT_US_MESSAGE
)
from utils import (
    safe_html, validate_amount, validate_transaction_id,
    calculate_exchange, get_upi_qr_url, get_exchange_rate,
    get_payment_details, check_anti_spam, is_user_banned,
    format_timestamp, get_exchange_type_display,
    get_exchange_currencies, generate_referral_code, get_user_info
)
from log_channel import log_event

logger = logging.getLogger(__name__)
router = Router()


# ==========================================
# FSM STATES
# ==========================================
class ExchangeState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_confirmation = State()
    waiting_for_screenshot = State()
    waiting_for_transaction_id = State()


class WalletState(StatesGroup):
    waiting_for_load_amount = State()
    waiting_for_load_screenshot = State()
    waiting_for_load_txn_id = State()
    waiting_for_withdraw_amount = State()
    waiting_for_withdraw_details = State()


class SupportState(StatesGroup):
    waiting_for_subject = State()
    waiting_for_message = State()


class AdminState(StatesGroup):
    waiting_for_inr_rate = State()
    waiting_for_npr_rate = State()
    waiting_for_reject_reason = State()
    waiting_for_search_query = State()
    waiting_for_support_reply = State()


class CalcState(StatesGroup):
    waiting_for_calc_amount = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ==========================================
# /START & /HOME COMMAND & REGULAR MENU
# ==========================================
@router.message(CommandStart())
@router.message(Command("home"))
@router.message(F.text.in_(["🏠 Home Menu", "🔙 Back to Home", "🏠 Home", "/start", "/home"]))
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""

    if is_user_banned(user_id):
        await message.answer(ERROR_MESSAGES["banned"])
        return

    # Check for referral payload
    referred_by = None
    args = message.text.split()[1:] if message.text else []
    if args and args[0].startswith("ref_"):
        ref_code = args[0].replace("ref_", "").strip().upper()
        ref_user_id = get_user_by_referral_code(ref_code)
        if ref_user_id and ref_user_id != user_id:
            referred_by = ref_user_id

    user_info = get_user_info(user_id)
    is_new = user_info is None
    referral_code = user_info["referral_code"] if user_info else generate_referral_code(user_id)

    add_or_update_user(user_id, username, first_name, last_name, referral_code, referred_by)

    inr_to_npr = get_exchange_rate("INR_TO_NPR") or DEFAULT_INR_TO_NPR_RATE
    npr_to_inr = get_exchange_rate("NPR_TO_INR") or DEFAULT_NPR_TO_INR_RATE

    welcome_text = WELCOME_MESSAGE.format(
        inr_to_npr=f"{inr_to_npr:.4f}",
        npr_to_inr=f"{npr_to_inr:.4f}",
        fee=f"{SERVICE_FEE_PERCENTAGE:.1f}"
    )

    # Remove any cached reply keyboard from user screen
    try:
        cleanup = await message.answer("⚡", reply_markup=ReplyKeyboardRemove())
        await cleanup.delete()
    except Exception:
        pass

    if BANNER_IMAGE_URL:
        try:
            await message.answer_photo(
                photo=BANNER_IMAGE_URL,
                caption=welcome_text,
                reply_markup=get_start_reply_keyboard(is_admin=is_admin(user_id)),
                parse_mode="HTML"
            )
        except Exception:
            await message.answer(
                welcome_text,
                reply_markup=get_start_reply_keyboard(is_admin=is_admin(user_id)),
                parse_mode="HTML"
            )
    else:
        await message.answer(
            welcome_text,
            reply_markup=get_start_reply_keyboard(is_admin=is_admin(user_id)),
            parse_mode="HTML"
        )

    if is_new:
        await log_event(
            bot, "user_start", is_new=True, user_id=user_id,
            username=username, first_name=first_name, last_name=last_name,
            referred_by=referred_by
        )


# ==========================================
# REGULAR BUTTON: ABOUT US
# ==========================================
@router.message(F.text.in_(["ℹ️ About Us", "ℹ️ About"]))
@router.message(Command("about"))
async def msg_about_us(message: Message):
    await message.answer(ABOUT_US_MESSAGE, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")


# ==========================================
# REGULAR BUTTON: CONTACT US
# ==========================================
@router.message(F.text.in_(["📞 Contact Support", "📞 Contact"]))
@router.message(Command("contact"))
async def msg_contact_us(message: Message):
    await message.answer(CONTACT_US_MESSAGE, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")


# ==========================================
# REGULAR BUTTON: LIVE RATES
# ==========================================
@router.message(F.text.in_(["📊 Live Rates", "📊 Rates"]))
@router.message(Command("rates"))
async def msg_rates(message: Message):
    inr_to_npr = get_exchange_rate("INR_TO_NPR") or DEFAULT_INR_TO_NPR_RATE
    npr_to_inr = get_exchange_rate("NPR_TO_INR") or DEFAULT_NPR_TO_INR_RATE

    text = CURRENT_RATE.format(
        inr_to_npr=f"{inr_to_npr:.4f}",
        npr_to_inr=f"{npr_to_inr:.4f}",
        fee=f"{SERVICE_FEE_PERCENTAGE:.1f}"
    )
    await message.answer(text, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")


# ==========================================
# REGULAR BUTTON: HELP / HOW IT WORKS
# ==========================================
@router.message(F.text.in_(["❓ Help Guide", "❓ Help"]))
@router.message(Command("help"))
async def msg_how_it_works(message: Message):
    await message.answer(HOW_IT_WORKS, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")


# ==========================================
# REGULAR BUTTON: ORDER STATUS
# ==========================================
@router.message(F.text.in_(["🔍 Order Status", "🔍 Status"]))
async def msg_order_status_prompt(message: Message):
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, exchange_type, amount, final_amount, status, created_at
        FROM exchange_requests
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    latest = cursor.fetchone()
    conn.close()

    if latest:
        status_badge = {
            "PENDING": "⏳ Under Review",
            "APPROVED": "✅ Approved / Processing",
            "COMPLETED": "🎉 Completed",
            "REJECTED": "❌ Rejected",
        }.get(latest[4], latest[4])

        resp = (
            f"🔍 <b>Latest Order: #{latest[0]}</b>\n\n"
            f"<blockquote>"
            f"• <b>Type:</b> {get_exchange_type_display(latest[1])}\n"
            f"• <b>Amount:</b> <code>{latest[2]:,.2f}</code> ➔ <b>{latest[3]:,.2f}</b>\n"
            f"• <b>Status:</b> <b>{status_badge}</b>\n"
            f"• <b>Date:</b> <code>{format_timestamp(latest[5])}</code>"
            f"</blockquote>\n\n"
            f"<i>💡 To check any specific order: <code>/status &lt;Order_ID&gt;</code></i>"
        )
        await message.answer(resp, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")
    else:
        await message.answer(
            "🔍 <b>Order Status Tracker</b>\n\n"
            "<blockquote>No recent orders found on your account.</blockquote>\n"
            "<i>To track an order, send: <code>/status &lt;Order_ID&gt;</code> (e.g. <code>/status 102</code>)</i>",
            reply_markup=get_start_reply_keyboard(),
            parse_mode="HTML"
        )


# ==========================================
# REGULAR BUTTON: RATE CALCULATOR
# ==========================================
@router.message(F.text.in_(["🔢 Rate Calculator", "🔢 Calculator"]))
@router.message(Command("calc"))
async def msg_calculator(message: Message, state: FSMContext):
    # Support direct /calc 5000
    parts = message.text.split()
    if len(parts) > 1:
        valid, amount = validate_amount(parts[1])
        if valid:
            rate_inr = get_exchange_rate("INR_TO_NPR") or DEFAULT_INR_TO_NPR_RATE
            gross_npr, fee_npr, final_npr = calculate_exchange(amount, rate_inr)

            rate_npr = get_exchange_rate("NPR_TO_INR") or DEFAULT_NPR_TO_INR_RATE
            gross_inr, fee_inr, final_inr = calculate_exchange(amount, rate_npr)

            resp = (
                f"🔢 <b>Rate Calculator Result</b>\n\n"
                f"🇮🇳 <b>Send ₹{amount:,.2f} INR:</b>\n"
                f"<blockquote>"
                f"• Rate: 1 INR = {rate_inr:.4f} NPR\n"
                f"• Gross: ₨{gross_npr:,.2f}\n"
                f"• Fee ({SERVICE_FEE_PERCENTAGE}%): -₨{fee_npr:,.2f}\n"
                f"👉 <b>You Receive: ₨{final_npr:,.2f} NPR</b>"
                f"</blockquote>\n\n"
                f"🇳🇵 <b>Send ₨{amount:,.2f} NPR:</b>\n"
                f"<blockquote>"
                f"• Rate: 1 NPR = {rate_npr:.4f} INR\n"
                f"• Gross: ₹{gross_inr:,.2f}\n"
                f"• Fee ({SERVICE_FEE_PERCENTAGE}%): -₹{fee_inr:,.2f}\n"
                f"👉 <b>You Receive: ₹{final_inr:,.2f} INR</b>"
                f"</blockquote>"
            )
            await message.answer(resp, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")
            return

    await state.set_state(CalcState.waiting_for_calc_amount)
    await message.answer(
        "🔢 <b>Rate Calculator</b>\n\n"
        "Enter amount to calculate (e.g. <code>2500</code>):",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(CalcState.waiting_for_calc_amount)
async def process_calc_amount(message: Message, state: FSMContext):
    if message.text in ("🔙 Back to Home", "🔙 Back", "🏠 Home Menu"):
        await state.clear()
        await message.answer("Main Menu:", reply_markup=get_start_reply_keyboard())
        return

    valid, amount = validate_amount(message.text)
    if not valid:
        await message.answer(f"❌ {amount}\nPlease enter a valid number:", reply_markup=get_cancel_reply_keyboard())
        return

    await state.clear()
    rate_inr = get_exchange_rate("INR_TO_NPR") or DEFAULT_INR_TO_NPR_RATE
    gross_npr, fee_npr, final_npr = calculate_exchange(amount, rate_inr)

    rate_npr = get_exchange_rate("NPR_TO_INR") or DEFAULT_NPR_TO_INR_RATE
    gross_inr, fee_inr, final_inr = calculate_exchange(amount, rate_npr)

    resp = (
        f"🔢 <b>Rate Calculator Result</b>\n\n"
        f"🇮🇳 <b>Send ₹{amount:,.2f} INR:</b>\n"
        f"<blockquote>"
        f"• Rate: 1 INR = {rate_inr:.4f} NPR\n"
        f"• Gross: ₨{gross_npr:,.2f}\n"
        f"• Fee ({SERVICE_FEE_PERCENTAGE}%): -₨{fee_npr:,.2f}\n"
        f"👉 <b>You Receive: ₨{final_npr:,.2f} NPR</b>"
        f"</blockquote>\n\n"
        f"🇳🇵 <b>Send ₨{amount:,.2f} NPR:</b>\n"
        f"<blockquote>"
        f"• Rate: 1 NPR = {rate_npr:.4f} INR\n"
        f"• Gross: ₹{gross_inr:,.2f}\n"
        f"• Fee ({SERVICE_FEE_PERCENTAGE}%): -₹{fee_inr:,.2f}\n"
        f"👉 <b>You Receive: ₹{final_inr:,.2f} INR</b>"
        f"</blockquote>"
    )
    await message.answer(resp, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")


# ==========================================
# REGULAR BUTTONS: CURRENCY EXCHANGE FLOW
# ==========================================
@router.message(F.text.in_(["🇮🇳 INR → 🇳🇵 NPR", "🇳🇵 NPR → 🇮🇳 INR"]))
async def msg_start_exchange(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if is_user_banned(user_id):
        await message.answer(ERROR_MESSAGES["banned"])
        return

    can_exchange, wait_time = check_anti_spam(user_id)
    if not can_exchange:
        await message.answer(
            ERROR_MESSAGES["anti_spam"].format(wait_time=wait_time),
            reply_markup=get_start_reply_keyboard()
        )
        return

    exchange_type = "INR_TO_NPR" if "INR → 🇳🇵 NPR" in message.text else "NPR_TO_INR"
    from_curr, to_curr = get_exchange_currencies(exchange_type)
    rate = get_exchange_rate(exchange_type) or (DEFAULT_INR_TO_NPR_RATE if exchange_type == "INR_TO_NPR" else DEFAULT_NPR_TO_INR_RATE)

    await state.update_data(exchange_type=exchange_type, rate=rate)
    await state.set_state(ExchangeState.waiting_for_amount)

    info_text = (
        f"💱 <b>Direction: {get_exchange_type_display(exchange_type)}</b>\n\n"
        f"<blockquote>"
        f"• Current Rate: <b>1 {from_curr} = {rate:.4f} {to_curr}</b>\n"
        f"• Service Fee: <b>{SERVICE_FEE_PERCENTAGE}%</b>"
        f"</blockquote>\n\n"
        f"{ENTER_AMOUNT}"
    )

    await message.answer(
        info_text,
        reply_markup=get_quick_amount_reply_keyboard(from_curr),
        parse_mode="HTML"
    )


@router.message(ExchangeState.waiting_for_amount)
async def process_exchange_amount(message: Message, state: FSMContext):
    if message.text in ("🔙 Back to Home", "🔙 Back", "🏠 Home Menu"):
        await state.clear()
        await message.answer("Main Menu:", reply_markup=get_start_reply_keyboard())
        return

    raw_text = message.text.replace("₹", "").replace("₨", "").strip()
    valid, amount = validate_amount(raw_text)

    if not valid:
        data = await state.get_data()
        from_curr = "INR" if data.get("exchange_type") == "INR_TO_NPR" else "NPR"
        await message.answer(
            f"❌ {amount}\nSelect from quick buttons or type a number:",
            reply_markup=get_quick_amount_reply_keyboard(from_curr)
        )
        return

    data = await state.get_data()
    exchange_type = data.get("exchange_type")
    rate = data.get("rate")

    calculated_amount, service_fee, final_amount = calculate_exchange(amount, rate)
    from_curr, to_curr = get_exchange_currencies(exchange_type)

    await state.update_data(
        amount=amount,
        calculated_amount=calculated_amount,
        service_fee=service_fee,
        final_amount=final_amount,
        from_curr=from_curr,
        to_curr=to_curr,
    )
    await state.set_state(ExchangeState.waiting_for_confirmation)

    summary_text = EXCHANGE_SUMMARY.format(
        amount=f"{amount:,.2f}",
        from_currency=from_curr,
        rate=f"{rate:.4f}",
        to_currency=to_curr,
        calculated_amount=f"{calculated_amount:,.2f}",
        fee_percent=f"{SERVICE_FEE_PERCENTAGE:.1f}",
        service_fee=f"{service_fee:,.2f}",
        final_amount=f"{final_amount:,.2f}"
    )

    await message.answer(
        summary_text,
        reply_markup=get_exchange_confirm_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(ExchangeState.waiting_for_confirmation, F.text.in_(["🔄 Change Amount", "🔄 Change"]))
async def msg_change_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    from_curr = data.get("from_curr", "INR")
    await state.set_state(ExchangeState.waiting_for_amount)
    await message.answer(
        "🔄 Select or type a new amount:",
        reply_markup=get_quick_amount_reply_keyboard(from_curr)
    )


@router.message(ExchangeState.waiting_for_confirmation, F.text.in_(["❌ Cancel Exchange", "❌ Cancel Payment", "❌ Cancel"]))
async def msg_cancel_exchange(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Exchange cancelled.",
        reply_markup=get_start_reply_keyboard()
    )


@router.message(ExchangeState.waiting_for_confirmation, F.text.in_(["✅ Confirm & Proceed", "✅ Confirm", "✅ Proceed"]))
async def msg_proceed_payment(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()

    amount = data["amount"]
    from_curr = data["from_curr"]
    upi_id, esewa_id = get_payment_details()

    pay_text = PAYMENT_INSTRUCTIONS.format(
        amount=f"{amount:,.2f}",
        from_currency=from_curr,
        upi_id=upi_id,
        esewa_id=esewa_id,
        user_id=user_id
    )

    if from_curr == "INR" and ENABLE_DYNAMIC_QR:
        qr_url = get_upi_qr_url(upi_id, amount, f"Exchange User {user_id}")
        try:
            await message.answer_photo(
                photo=URLInputFile(qr_url),
                caption=pay_text,
                reply_markup=get_payment_reply_keyboard(),
                parse_mode="HTML"
            )
            return
        except Exception as e:
            logger.warning("QR Code error: %s", e)

    await message.answer(
        pay_text,
        reply_markup=get_payment_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text.in_(["✅ I Have Paid", "✅ Paid"]))
async def msg_payment_done(message: Message, state: FSMContext):
    await state.set_state(ExchangeState.waiting_for_screenshot)
    await message.answer(
        PAYMENT_VERIFICATION,
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(ExchangeState.waiting_for_screenshot, F.photo)
async def process_payment_photo(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await state.update_data(payment_proof=photo_file_id)
    await state.set_state(ExchangeState.waiting_for_transaction_id)

    await message.answer(
        PAYMENT_ASK_TXN_ID,
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(ExchangeState.waiting_for_transaction_id)
async def process_payment_utr(message: Message, state: FSMContext, bot: Bot):
    if message.text in ("🔙 Back to Home", "🔙 Back", "🏠 Home Menu"):
        await state.clear()
        await message.answer("Main Menu:", reply_markup=get_start_reply_keyboard())
        return

    txn_id = message.text.strip() if message.text else ""
    if not validate_transaction_id(txn_id):
        await message.answer(
            "❌ Invalid Transaction ID / UTR! Please send a valid 12-digit UTR or Reference ID:\n"
            "<i>(e.g., 429019283011)</i>",
            reply_markup=get_cancel_reply_keyboard(),
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO exchange_requests (
            user_id, exchange_type, amount, rate, calculated_amount,
            service_fee, final_amount, payment_proof, transaction_id, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
    """, (
        user_id, data["exchange_type"], data["amount"], data["rate"],
        data["calculated_amount"], data["service_fee"], data["final_amount"],
        data["payment_proof"], txn_id
    ))
    request_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await state.clear()

    # User confirmation message
    await message.answer(
        f"✅ <b>Payment Proof Submitted (Order #{request_id})</b>\n\n"
        f"<blockquote>"
        f"• <b>Sent:</b> <code>{data['amount']:,.2f} {data['from_curr']}</code>\n"
        f"• <b>Payout:</b> <b>{data['final_amount']:,.2f} {data['to_curr']}</b>\n"
        f"• <b>Txn ID:</b> <code>{safe_html(txn_id)}</code>\n"
        f"• <b>Status:</b> ⏳ Under Review\n"
        f"• <b>ETA:</b> 5–15 minutes"
        f"</blockquote>\n\n"
        f"<i>Funds will be dispatched after bank UTR verification.</i>",
        reply_markup=get_start_reply_keyboard(),
        parse_mode="HTML"
    )

    # Admin notification with inline approval buttons
    user_info = get_user_info(user_id) or {}
    admin_text = ADMIN_REQUEST.format(
        request_id=request_id,
        user_id=user_id,
        username=safe_html(username),
        exchange_type=get_exchange_type_display(data["exchange_type"]),
        amount=f"{data['amount']:,.2f} {data['from_curr']}",
        rate=f"{data['rate']:.4f}",
        final_amount=f"{data['final_amount']:,.2f}",
        to_currency=data["to_curr"],
        transaction_id=safe_html(txn_id),
        total_exchanges=user_info.get("total_exchanges", 0),
        total_volume=f"₹{user_info.get('total_amount', 0):,.2f}",
        wallet_inr=f"{user_info.get('wallet_inr', 0):,.2f}",
        wallet_npr=f"{user_info.get('wallet_npr', 0):,.2f}",
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=data["payment_proof"],
                caption=admin_text,
                reply_markup=get_admin_approval_keyboard(request_id),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Admin notification error: %s", e)


# ==========================================
# REGULAR BUTTON: WALLET & BALANCES
# ==========================================
@router.message(F.text.in_(["💼 My Wallet", "💼 Wallet"]))
@router.message(Command("wallet"))
async def msg_wallet(message: Message):
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    if not user_info:
        await message.answer("❌ User profile not found.")
        return

    text = WALLET_MENU.format(
        wallet_inr=f"{user_info['wallet_inr']:,.2f}",
        wallet_npr=f"{user_info['wallet_npr']:,.2f}"
    )
    await message.answer(text, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")


@router.message(F.text.in_(["📥 Deposit Funds", "📥 Deposit"]))
async def msg_load_wallet(message: Message):
    await message.answer(
        "📥 <b>Deposit Funds into Wallet</b>\n\n"
        "Choose currency to deposit:",
        reply_markup=get_load_currency_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text.in_(["🇮🇳 Deposit INR", "🇳🇵 Deposit NPR"]))
async def msg_load_currency_choice(message: Message, state: FSMContext):
    currency = "INR" if "INR" in message.text else "NPR"
    await state.update_data(load_currency=currency)
    await state.set_state(WalletState.waiting_for_load_amount)

    symbol = "₹" if currency == "INR" else "₨"
    await message.answer(
        f"📥 <b>Deposit {currency}</b>\n\n"
        f"Limits: {symbol}100 – {symbol}100,000\n"
        f"Type the amount to deposit:",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(WalletState.waiting_for_load_amount)
async def process_load_amt(message: Message, state: FSMContext):
    if message.text in ("🔙 Back to Home", "🔙 Back", "🏠 Home Menu"):
        await state.clear()
        await message.answer("Main Menu:", reply_markup=get_start_reply_keyboard())
        return

    valid, amount = validate_amount(message.text)
    if not valid:
        await message.answer(f"❌ {amount}\nPlease enter a valid amount:", reply_markup=get_cancel_reply_keyboard())
        return

    data = await state.get_data()
    currency = data.get("load_currency", "INR")
    await state.update_data(load_amount=amount)
    await state.set_state(WalletState.waiting_for_load_screenshot)

    upi_id, esewa_id = get_payment_details()
    symbol = "₹" if currency == "INR" else "₨"

    pay_info = (
        f"💳 <b>Deposit Payment Instructions</b>\n\n"
        f"<blockquote>"
        f"<b>Amount:</b> <code>{symbol}{amount:,.2f} {currency}</code>\n"
        f"</blockquote>\n\n"
    )

    if currency == "INR":
        pay_info += f"🇮🇳 <b>UPI ID:</b> <code>{upi_id}</code>\n<i>Put User ID <code>{message.from_user.id}</code> in remarks</i>"
    else:
        pay_info += f"🇳🇵 <b>eSewa ID:</b> <code>{esewa_id}</code>\n<i>Put User ID <code>{message.from_user.id}</code> in remarks</i>"

    pay_info += "\n\n<i>Upload your <b>Payment Screenshot</b> after transfer:</i>"

    await message.answer(pay_info, reply_markup=get_cancel_reply_keyboard(), parse_mode="HTML")


@router.message(WalletState.waiting_for_load_screenshot, F.photo)
async def process_load_photo(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await state.update_data(load_photo=photo_file_id)
    await state.set_state(WalletState.waiting_for_load_txn_id)

    await message.answer(
        "🔢 Enter your 12-digit UTR / Reference ID:",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(WalletState.waiting_for_load_txn_id)
async def process_load_utr(message: Message, state: FSMContext, bot: Bot):
    if message.text in ("🔙 Back to Home", "🔙 Back", "🏠 Home Menu"):
        await state.clear()
        await message.answer("Main Menu:", reply_markup=get_start_reply_keyboard())
        return

    txn_id = message.text.strip() if message.text else ""
    if not validate_transaction_id(txn_id):
        await message.answer("❌ Invalid Transaction ID! Please send a valid UTR number:", reply_markup=get_cancel_reply_keyboard())
        return

    data = await state.get_data()
    user_id = message.from_user.id
    currency = data["load_currency"]
    amount = data["load_amount"]
    photo = data["load_photo"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO exchange_requests (
            user_id, exchange_type, amount, rate, calculated_amount,
            service_fee, final_amount, payment_proof, transaction_id, status
        ) VALUES (?, ?, ?, 1.0, ?, 0.0, ?, ?, ?, 'PENDING')
    """, (
        user_id, f"LOAD_{currency}", amount, amount, amount, photo, txn_id
    ))
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        f"✅ <b>Deposit Request #{req_id} Submitted!</b>\n"
        f"<code>{amount:,.2f} {currency}</code> will be credited to your wallet upon verification.",
        reply_markup=get_start_reply_keyboard(),
        parse_mode="HTML"
    )

    for aid in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=aid,
                photo=photo,
                caption=f"📥 <b>Deposit Request #{req_id}</b>\n"
                        f"User: <code>{user_id}</code>\n"
                        f"Amount: <b>{amount:,.2f} {currency}</b>\n"
                        f"UTR: <code>{safe_html(txn_id)}</code>",
                reply_markup=get_admin_approval_keyboard(req_id),
                parse_mode="HTML"
            )
        except Exception:
            pass


# ==========================================
# REGULAR BUTTON: WITHDRAWAL
# ==========================================
@router.message(F.text.in_(["💸 Withdraw", "💸 Withdrawal"]))
@router.message(Command("withdraw"))
async def msg_withdraw(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_info = get_user_info(user_id)

    if not user_info or (user_info["wallet_inr"] < 100 and user_info["wallet_npr"] < 100):
        await message.answer(
            "⚠️ <b>Insufficient Balance for Withdrawal</b>\n\n"
            f"<blockquote>"
            f"• INR: ₹{user_info.get('wallet_inr', 0):,.2f}\n"
            f"• NPR: ₨{user_info.get('wallet_npr', 0):,.2f}\n"
            f"Minimum withdrawal limit is 100."
            f"</blockquote>",
            reply_markup=get_start_reply_keyboard(),
            parse_mode="HTML"
        )
        return

    await state.set_state(WalletState.waiting_for_withdraw_amount)
    await message.answer(
        "💸 <b>Wallet Withdrawal</b>\n\n"
        f"<blockquote>"
        f"• Available INR: ₹{user_info['wallet_inr']:,.2f}\n"
        f"• Available NPR: ₨{user_info['wallet_npr']:,.2f}"
        f"</blockquote>\n\n"
        "Enter currency and amount (e.g. <code>INR 2000</code> or <code>NPR 3000</code>):",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(WalletState.waiting_for_withdraw_amount)
async def process_withdraw_amt(message: Message, state: FSMContext):
    if message.text in ("🔙 Back to Home", "🔙 Back", "🏠 Home Menu"):
        await state.clear()
        await message.answer("Main Menu:", reply_markup=get_start_reply_keyboard())
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Format: <code>INR 2000</code> or <code>NPR 3000</code>", parse_mode="HTML")
        return

    currency = parts[0].upper()
    if currency not in ("INR", "NPR"):
        await message.answer("❌ Invalid currency! Use INR or NPR.")
        return

    valid, amount = validate_amount(parts[1])
    if not valid:
        await message.answer(f"❌ {amount}")
        return

    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    balance = user_info["wallet_inr"] if currency == "INR" else user_info["wallet_npr"]

    if balance < amount:
        await message.answer(
            f"❌ Insufficient balance! Available {currency}: {balance:,.2f}",
            reply_markup=get_cancel_reply_keyboard()
        )
        return

    await state.update_data(withdraw_currency=currency, withdraw_amount=amount)
    await state.set_state(WalletState.waiting_for_withdraw_details)

    target_acct = "UPI VPA (e.g. name@upi)" if currency == "INR" else "eSewa ID / Phone Number"
    await message.answer(
        f"📝 Enter your destination <b>{target_acct}</b> to receive payout:",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(WalletState.waiting_for_withdraw_details)
async def process_withdraw_details(message: Message, state: FSMContext, bot: Bot):
    if message.text in ("🔙 Back to Home", "🔙 Back", "🏠 Home Menu"):
        await state.clear()
        await message.answer("Main Menu:", reply_markup=get_start_reply_keyboard())
        return

    account_details = message.text.strip()
    if len(account_details) < 4:
        await message.answer("❌ Please provide a valid payout account detail.")
        return

    data = await state.get_data()
    currency = data["withdraw_currency"]
    amount = data["withdraw_amount"]
    user_id = message.from_user.id

    deducted = atomic_deduct_wallet(user_id, currency, amount)
    if not deducted:
        await state.clear()
        await message.answer("❌ Transaction failed: Insufficient balance or concurrent request.", reply_markup=get_start_reply_keyboard())
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO exchange_requests (
            user_id, exchange_type, amount, rate, calculated_amount,
            service_fee, final_amount, status, payment_details
        ) VALUES (?, ?, ?, 1.0, ?, 0.0, ?, 'PENDING', ?)
    """, (
        user_id, f"WITHDRAW_{currency}", amount, amount, amount, account_details
    ))
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        f"✅ <b>Withdrawal Request #{req_id} Placed!</b>\n\n"
        f"<blockquote>"
        f"• Debited: <code>{amount:,.2f} {currency}</code>\n"
        f"• Destination: <code>{safe_html(account_details)}</code>\n"
        f"• Status: ⏳ Processing"
        f"</blockquote>\n\n"
        f"You will receive confirmation once the admin dispatches your payout.",
        reply_markup=get_start_reply_keyboard(),
        parse_mode="HTML"
    )

    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=aid,
                text=f"💸 <b>New Withdrawal Request #{req_id}</b>\n\n"
                     f"User: <code>{user_id}</code>\n"
                     f"Amount: <b>{amount:,.2f} {currency}</b>\n"
                     f"Account: <code>{safe_html(account_details)}</code>\n"
                     f"<i>Funds already held securely in escrow.</i>",
                reply_markup=get_admin_approval_keyboard(req_id),
                parse_mode="HTML"
            )
        except Exception:
            pass


# ==========================================
# REGULAR BUTTON: PROFILE & REFERRAL
# ==========================================
@router.message(F.text.in_(["👤 Profile & Referrals", "👤 Profile"]))
@router.message(Command("profile"))
async def msg_profile(message: Message, bot: Bot):
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    if not user_info:
        await message.answer("❌ Profile could not be loaded.")
        return

    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user_info['referral_code']}"
    referred_count = get_referred_users_count(user_id)

    profile_text = PROFILE_MESSAGE.format(
        first_name=safe_html(user_info["first_name"]),
        username=safe_html(user_info["username"]),
        user_id=user_id,
        joined_date=format_timestamp(user_info["joined_date"]),
        wallet_inr=f"{user_info['wallet_inr']:,.2f}",
        wallet_npr=f"{user_info['wallet_npr']:,.2f}",
        total_exchanges=user_info["total_exchanges"],
        total_amount=f"₹{user_info['total_amount']:,.2f}",
        referral_code=user_info["referral_code"],
        referral_link=referral_link,
        referred_count=referred_count
    )

    await message.answer(profile_text, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")


# ==========================================
# REGULAR BUTTON: HISTORY
# ==========================================
@router.message(F.text.in_(["📜 History", "📜 Transactions"]))
@router.message(Command("history"))
async def msg_history(message: Message):
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, exchange_type, amount, final_amount, status, created_at
        FROM exchange_requests
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 5
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "📜 <b>No Transactions Found</b>\n\nStart your first exchange using the buttons below!",
            reply_markup=get_start_reply_keyboard(),
            parse_mode="HTML"
        )
        return

    items = []
    for r in rows:
        status_emoji = "✅" if r[4] in ("APPROVED", "COMPLETED") else "⏳" if r[4] == "PENDING" else "❌"
        items.append(
            f"• #{r[0]} | {status_emoji} <b>{r[4]}</b> | {get_exchange_type_display(r[1])}\n"
            f"  Amount: <code>{r[2]:,.2f}</code> ➔ <code>{r[3]:,.2f}</code> | <i>{format_timestamp(r[5])}</i>"
        )

    user_info = get_user_info(user_id) or {}
    text = TRANSACTION_HISTORY.format(
        transactions="\n\n".join(items),
        total=user_info.get("total_exchanges", 0),
        total_amount=f"₹{user_info.get('total_amount', 0):,.2f}"
    )

    await message.answer(text, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")


# ==========================================
# REGULAR BUTTON: SUPPORT
# ==========================================
@router.message(F.text.in_(["📞 Contact Support", "📞 Support"]))
@router.message(Command("support"))
async def msg_support(message: Message, state: FSMContext):
    await state.set_state(SupportState.waiting_for_subject)
    await message.answer(
        "📞 <b>Support Helpdesk</b>\n\n"
        "Please enter a short subject for your ticket:\n"
        "<i>(e.g., Payment Verification / Delay)</i>",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(SupportState.waiting_for_subject)
async def process_support_subj(message: Message, state: FSMContext):
    if message.text in ("🔙 Back to Home", "🔙 Back", "🏠 Home Menu"):
        await state.clear()
        await message.answer("Main Menu:", reply_markup=get_start_reply_keyboard())
        return

    subject = message.text.strip()
    await state.update_data(ticket_subject=subject)
    await state.set_state(SupportState.waiting_for_message)
    await message.answer(
        "💬 Please describe your issue in detail:",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.message(SupportState.waiting_for_message)
async def process_support_msg(message: Message, state: FSMContext, bot: Bot):
    if message.text in ("🔙 Back to Home", "🔙 Back", "🏠 Home Menu"):
        await state.clear()
        await message.answer("Main Menu:", reply_markup=get_start_reply_keyboard())
        return

    desc = message.text.strip()
    data = await state.get_data()
    subject = data.get("ticket_subject", "Support Inquiry")
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO support_tickets (user_id, subject, message, status)
        VALUES (?, ?, ?, 'OPEN')
    """, (user_id, subject, desc))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        SUPPORT_TICKET_CREATED.format(ticket_id=ticket_id),
        reply_markup=get_start_reply_keyboard(),
        parse_mode="HTML"
    )

    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=aid,
                text=f"🎫 <b>New Support Ticket #{ticket_id}</b>\n\n"
                     f"<blockquote>"
                     f"User: @{safe_html(username)} (<code>{user_id}</code>)\n"
                     f"Subject: <b>{safe_html(subject)}</b>\n"
                     f"Message: {safe_html(desc)}"
                     f"</blockquote>",
                reply_markup=get_admin_support_keyboard(ticket_id),
                parse_mode="HTML"
            )
        except Exception:
            pass


# ==========================================
# ORDER STATUS TRACKER (/status <id>)
# ==========================================
@router.message(Command("status"))
async def cmd_order_status(message: Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer(
            "ℹ️ <b>Usage:</b> <code>/status &lt;Order_ID&gt;</code>\n"
            "e.g. <code>/status 104</code>",
            reply_markup=get_start_reply_keyboard(),
            parse_mode="HTML"
        )
        return

    req_id = int(parts[1])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, exchange_type, amount, final_amount, status, rejection_reason, created_at
        FROM exchange_requests WHERE id = ?
    """, (req_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or (row[1] != message.from_user.id and not is_admin(message.from_user.id)):
        await message.answer("❌ Order not found or unauthorized.", reply_markup=get_start_reply_keyboard())
        return

    status_badge = {
        "PENDING": "⏳ Under Review",
        "APPROVED": "✅ Approved / Processing",
        "COMPLETED": "🎉 Completed",
        "REJECTED": "❌ Rejected",
    }.get(row[5], row[5])

    details = (
        f"📋 <b>Order Details — #{row[0]}</b>\n\n"
        f"<blockquote>"
        f"• Type: {get_exchange_type_display(row[2])}\n"
        f"• Amount: <code>{row[3]:,.2f}</code>\n"
        f"• Net Payout: <b>{row[4]:,.2f}</b>\n"
        f"• Status: <b>{status_badge}</b>\n"
        f"• Date: <code>{format_timestamp(row[7])}</code>"
    )
    if row[6]:
        details += f"\n• Reason: <i>{safe_html(row[6])}</i>"
    details += "</blockquote>"

    await message.answer(details, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")


# ==========================================
# ADMIN BACKOFFICE
# ==========================================
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Unauthorized: Admin access required.")
        return

    await message.answer(
        "🛡️ <b>Admin Control Center (Backoffice)</b>",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )


# Admin Approve Order
@router.callback_query(F.data.startswith("admin_approve_"))
async def cb_admin_approve(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Unauthorized!", show_alert=True)
        return

    req_id = int(callback.data.replace("admin_approve_", ""))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, exchange_type, amount, final_amount, status
        FROM exchange_requests WHERE id = ?
    """, (req_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        await callback.answer("❌ Order not found.", show_alert=True)
        return

    user_id, ex_type, amount, final_amount, current_status = row
    if current_status in ("APPROVED", "COMPLETED"):
        conn.close()
        await callback.answer("⚠️ Already approved!", show_alert=True)
        return

    cursor.execute("""
        UPDATE exchange_requests
        SET status = 'APPROVED', processed_at = CURRENT_TIMESTAMP, processed_by = ?
        WHERE id = ?
    """, (callback.from_user.id, req_id))

    cursor.execute("""
        UPDATE users
        SET total_exchanges = total_exchanges + 1,
            total_amount = total_amount + ?
        WHERE user_id = ?
    """, (amount, user_id))
    conn.commit()

    if ex_type.startswith("LOAD_"):
        curr = ex_type.replace("LOAD_", "")
        atomic_add_wallet(user_id, curr, amount, f"Load approved #{req_id}")

    if ENABLE_REFERRAL:
        cursor.execute("SELECT referred_by, referral_bonus_given FROM users WHERE user_id = ?", (user_id,))
        ref_row = cursor.fetchone()
        if ref_row and ref_row[0] and not ref_row[1]:
            referrer_id = ref_row[0]
            bonus_amount = round(amount * (REFERRAL_BONUS_PERCENT / 100.0), 2)
            bonus_curr = "INR" if "INR" in ex_type else "NPR"
            atomic_add_wallet(referrer_id, bonus_curr, bonus_amount, f"Referral bonus from user {user_id}")
            cursor.execute("UPDATE users SET referral_bonus_given = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            try:
                await bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎁 <b>Referral Bonus Credited!</b>\n\n"
                         f"You received <b>+{bonus_amount:,.2f} {bonus_curr}</b> from a friend's first trade!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    conn.close()
    await callback.answer("✅ Approved successfully!", show_alert=True)

    try:
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\n<b>✅ APPROVED by Admin {callback.from_user.id}</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        pass

    from_c, to_c = get_exchange_currencies(ex_type)
    approved_text = APPROVED_MESSAGE.format(
        request_id=req_id,
        final_amount=f"{final_amount:,.2f}",
        to_currency=to_c
    )
    try:
        await bot.send_message(chat_id=user_id, text=approved_text, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")
    except Exception:
        pass

    await log_event(bot, "request_approved", request_id=req_id, user_id=user_id, amount=f"{amount} {from_c}", admin_id=callback.from_user.id)


# Admin Reject Menu
@router.callback_query(F.data.startswith("admin_reject_"))
async def cb_admin_reject_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    req_id = int(callback.data.replace("admin_reject_", ""))
    await callback.message.answer(
        f"❌ <b>Select Rejection Reason for Order #{req_id}:</b>",
        reply_markup=get_reject_reason_keyboard(req_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rr_"))
async def cb_handle_reject_reason(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    parts = callback.data.split("_")
    req_id = int(parts[1])
    code = parts[2]

    if code == "6":
        await state.update_data(reject_req_id=req_id)
        await state.set_state(AdminState.waiting_for_reject_reason)
        await callback.message.answer("✏️ Type custom rejection reason:")
        return

    reason = REJECT_REASONS.get(code, "Payment verification failed")
    await _execute_rejection(req_id, reason, callback.from_user.id, bot, callback.message)


@router.message(AdminState.waiting_for_reject_reason)
async def process_custom_reject(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    reason = message.text.strip()
    data = await state.get_data()
    req_id = data["reject_req_id"]
    await state.clear()
    await _execute_rejection(req_id, reason, message.from_user.id, bot, message)


async def _execute_rejection(req_id: int, reason: str, admin_id: int, bot: Bot, msg_context: Message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, exchange_type, amount, status
        FROM exchange_requests WHERE id = ?
    """, (req_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        await msg_context.answer("❌ Order not found.")
        return

    user_id, ex_type, amount, current_status = row
    if current_status in ("APPROVED", "COMPLETED", "REJECTED"):
        conn.close()
        await msg_context.answer(f"⚠️ Order is already {current_status}.")
        return

    cursor.execute("""
        UPDATE exchange_requests
        SET status = 'REJECTED', rejection_reason = ?, processed_at = CURRENT_TIMESTAMP, processed_by = ?
        WHERE id = ?
    """, (reason, admin_id, req_id))
    conn.commit()
    conn.close()

    if ex_type.startswith("WITHDRAW_"):
        curr = ex_type.replace("WITHDRAW_", "")
        atomic_add_wallet(user_id, curr, amount, f"Auto-refund rejected withdrawal #{req_id}")

    await msg_context.answer(f"✅ Order #{req_id} rejected.")

    reject_text = REJECTED_MESSAGE.format(request_id=req_id, reason=safe_html(reason))
    try:
        await bot.send_message(chat_id=user_id, text=reject_text, reply_markup=get_start_reply_keyboard(), parse_mode="HTML")
    except Exception:
        pass

    await log_event(bot, "request_rejected", request_id=req_id, user_id=user_id, reason=reason, admin_id=admin_id)


# Admin Pending Orders
@router.callback_query(F.data == "admin_pending")
async def cb_admin_pending(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, exchange_type, amount, final_amount, transaction_id, created_at
        FROM exchange_requests
        WHERE status = 'PENDING'
        ORDER BY id DESC LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await callback.message.answer("✅ <b>No pending orders! All caught up.</b>", parse_mode="HTML")
        return

    lines = ["⏳ <b>Pending Orders (Latest 5):</b>\n"]
    for r in rows:
        lines.append(
            f"• <b>#{r[0]}</b> | User <code>{r[1]}</code> | {r[2]}\n"
            f"  Amount: <code>{r[3]:,.2f}</code> ➔ <b>{r[4]:,.2f}</b> | UTR: <code>{safe_html(r[5])}</code>\n"
            f"  Date: <code>{format_timestamp(r[6])}</code>"
        )
    await callback.message.answer("\n\n".join(lines), parse_mode="HTML")


# Admin Completed Orders
@router.callback_query(F.data == "admin_completed")
async def cb_admin_completed(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, exchange_type, amount, final_amount, processed_at
        FROM exchange_requests
        WHERE status IN ('APPROVED', 'COMPLETED')
        ORDER BY id DESC LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await callback.message.answer("📜 <b>No completed orders found.</b>", parse_mode="HTML")
        return

    lines = ["✅ <b>Recent Completed Orders:</b>\n"]
    for r in rows:
        lines.append(
            f"• <b>#{r[0]}</b> | User <code>{r[1]}</code> | {r[2]}\n"
            f"  Amount: <code>{r[3]:,.2f}</code> ➔ <b>{r[4]:,.2f}</b> | At: <code>{format_timestamp(r[5])}</code>"
        )
    await callback.message.answer("\n\n".join(lines), parse_mode="HTML")


# Admin Settings View
@router.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()

    inr_rate = get_exchange_rate("INR_TO_NPR") or DEFAULT_INR_TO_NPR_RATE
    npr_rate = get_exchange_rate("NPR_TO_INR") or DEFAULT_NPR_TO_INR_RATE
    upi_id, esewa_id = get_payment_details()

    text = (
        "⚙️ <b>Exchange & Merchant Configuration</b>\n\n"
        f"<blockquote>"
        f"• <b>1 INR ➔ NPR:</b> <code>{inr_rate:.4f}</code>\n"
        f"• <b>1 NPR ➔ INR:</b> <code>{npr_rate:.4f}</code>\n"
        f"• <b>Service Fee:</b> <code>{SERVICE_FEE_PERCENTAGE}%</code>\n"
        f"• <b>Referral Bonus:</b> <code>{REFERRAL_BONUS_PERCENT}%</code>\n"
        f"• <b>UPI ID:</b> <code>{upi_id}</code>\n"
        f"• <b>eSewa ID:</b> <code>{esewa_id}</code>"
        f"</blockquote>"
    )
    await callback.message.answer(text, parse_mode="HTML")


# Admin Support Tickets
@router.callback_query(F.data == "admin_support")
async def cb_admin_support_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, subject, status, created_at
        FROM support_tickets
        WHERE status = 'OPEN'
        ORDER BY id DESC LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await callback.message.answer("✅ <b>No open support tickets!</b>", parse_mode="HTML")
        return

    lines = ["💬 <b>Open Support Tickets:</b>\n"]
    for r in rows:
        lines.append(f"• Ticket #{r[0]} | User: <code>{r[1]}</code>\n  Subject: <i>{safe_html(r[2])}</i>")
    await callback.message.answer("\n\n".join(lines), parse_mode="HTML")


# Navigation Callbacks
@router.callback_query(F.data == "back_to_admin")
async def cb_back_to_admin(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    await callback.message.answer(
        "🛡️ <b>Admin Control Center (Backoffice)</b>",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.in_(["back_to_start", "btn_home"]))
async def cb_back_to_start(callback: CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    await callback.answer()
    user_id = callback.from_user.id
    inr_to_npr = get_exchange_rate("INR_TO_NPR") or DEFAULT_INR_TO_NPR_RATE
    npr_to_inr = get_exchange_rate("NPR_TO_INR") or DEFAULT_NPR_TO_INR_RATE
    welcome_text = WELCOME_MESSAGE.format(
        inr_to_npr=f"{inr_to_npr:.4f}",
        npr_to_inr=f"{npr_to_inr:.4f}",
        fee=f"{SERVICE_FEE_PERCENTAGE:.1f}"
    )
    if BANNER_IMAGE_URL:
        try:
            await callback.message.answer_photo(
                photo=BANNER_IMAGE_URL,
                caption=welcome_text,
                reply_markup=get_start_reply_keyboard(is_admin=is_admin(user_id)),
                parse_mode="HTML"
            )
            return
        except Exception:
            pass
    await callback.message.answer(
        welcome_text,
        reply_markup=get_start_reply_keyboard(is_admin=is_admin(user_id)),
        parse_mode="HTML"
    )


# ==========================================
# USER INLINE BUTTON CALLBACKS
# ==========================================

@router.callback_query(F.data.in_(["exchange_inr_npr", "exchange_npr_inr"]))
async def cb_start_exchange(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        await callback.message.answer(ERROR_MESSAGES["banned"])
        return

    can_exchange, wait_time = check_anti_spam(user_id)
    if not can_exchange:
        await callback.message.answer(
            ERROR_MESSAGES["anti_spam"].format(wait_time=wait_time),
            reply_markup=get_start_reply_keyboard(is_admin=is_admin(user_id))
        )
        return

    exchange_type = "INR_TO_NPR" if callback.data == "exchange_inr_npr" else "NPR_TO_INR"
    from_curr, to_curr = get_exchange_currencies(exchange_type)
    rate = get_exchange_rate(exchange_type) or (DEFAULT_INR_TO_NPR_RATE if exchange_type == "INR_TO_NPR" else DEFAULT_NPR_TO_INR_RATE)

    await state.update_data(exchange_type=exchange_type, rate=rate, from_curr=from_curr, to_curr=to_curr)
    await state.set_state(ExchangeState.waiting_for_amount)

    info_text = (
        f"💱 <b>Direction: {get_exchange_type_display(exchange_type)}</b>\n\n"
        f"<blockquote>"
        f"• Current Rate: <b>1 {from_curr} = {rate:.4f} {to_curr}</b>\n"
        f"• Service Fee: <b>{SERVICE_FEE_PERCENTAGE}%</b>"
        f"</blockquote>\n\n"
        f"{ENTER_AMOUNT}"
    )

    await callback.message.answer(
        info_text,
        reply_markup=get_quick_amount_reply_keyboard(from_curr),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("amt_"), ExchangeState.waiting_for_amount)
async def cb_quick_amount(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    val_str = callback.data.replace("amt_", "")
    valid, amount = validate_amount(val_str)
    if not valid:
        return
    data = await state.get_data()
    exchange_type = data["exchange_type"]
    rate = data["rate"]
    from_curr, to_curr = get_exchange_currencies(exchange_type)
    final_amount, fee = calculate_exchange(amount, rate)

    await state.update_data(
        amount=amount,
        final_amount=final_amount,
        fee=fee,
        from_curr=from_curr,
        to_curr=to_curr
    )
    await state.set_state(ExchangeState.waiting_for_confirmation)

    summary_text = EXCHANGE_SUMMARY.format(
        exchange_type=get_exchange_type_display(exchange_type),
        from_amount=f"{amount:,.2f}",
        from_currency=from_curr,
        to_amount=f"{final_amount:,.2f}",
        to_currency=to_curr,
        rate=f"{rate:.4f}",
        fee=f"{fee:,.2f}",
        fee_currency=to_curr
    )
    await callback.message.answer(
        summary_text,
        reply_markup=get_exchange_confirm_reply_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "confirm_exchange", ExchangeState.waiting_for_confirmation)
async def cb_confirm_exchange(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    data = await state.get_data()

    amount = data["amount"]
    from_curr = data["from_curr"]
    upi_id, esewa_id = get_payment_details()

    pay_text = PAYMENT_INSTRUCTIONS.format(
        amount=f"{amount:,.2f}",
        from_currency=from_curr,
        upi_id=upi_id,
        esewa_id=esewa_id,
        user_id=user_id
    )

    await state.set_state(ExchangeState.waiting_for_payment)

    if from_curr == "INR" and ENABLE_DYNAMIC_QR:
        qr_url = get_upi_qr_url(upi_id, amount, f"Exchange User {user_id}")
        try:
            await callback.message.answer_photo(
                photo=URLInputFile(qr_url),
                caption=pay_text,
                reply_markup=get_payment_reply_keyboard(),
                parse_mode="HTML"
            )
            return
        except Exception as e:
            logger.warning("QR Code error: %s", e)

    await callback.message.answer(
        pay_text,
        reply_markup=get_payment_reply_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "change_amount", ExchangeState.waiting_for_confirmation)
async def cb_change_amount(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    from_curr = data.get("from_curr", "INR")
    await state.set_state(ExchangeState.waiting_for_amount)
    await callback.message.answer(
        "🔄 Select or type a new amount:",
        reply_markup=get_quick_amount_reply_keyboard(from_curr)
    )


@router.callback_query(F.data == "cancel_exchange")
async def cb_cancel_exchange(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Exchange cancelled.")
    await callback.message.answer(
        "❌ Exchange cancelled.",
        reply_markup=get_start_reply_keyboard(is_admin=is_admin(callback.from_user.id))
    )


@router.callback_query(F.data == "payment_done")
async def cb_payment_done(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ExchangeState.waiting_for_screenshot)
    await callback.message.answer(
        PAYMENT_VERIFICATION,
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "cancel_payment")
async def cb_cancel_payment(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Payment cancelled.")
    await callback.message.answer(
        "❌ Payment cancelled.",
        reply_markup=get_start_reply_keyboard(is_admin=is_admin(callback.from_user.id))
    )


@router.callback_query(F.data == "btn_wallet")
async def cb_btn_wallet(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user_info = get_user_info(user_id)
    if not user_info:
        await callback.message.answer("❌ User profile not found.")
        return
    text = WALLET_MENU.format(
        wallet_inr=f"{user_info['wallet_inr']:,.2f}",
        wallet_npr=f"{user_info['wallet_npr']:,.2f}",
        total_exchanges=user_info["total_exchanges"],
        total_volume=f"{user_info['total_volume']:,.2f}"
    )
    await callback.message.answer(text, reply_markup=get_cancel_reply_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "btn_calc")
async def cb_btn_calc(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(CalcState.waiting_for_calc_input)
    await callback.message.answer(
        "🔢 <b>Instant Rate Calculator</b>\n\n"
        "Send the amount you want to calculate (e.g. <code>5000</code> or <code>INR 5000</code> or <code>NPR 8000</code>):",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "btn_rates")
async def cb_btn_rates(callback: CallbackQuery):
    await callback.answer()
    inr_to_npr = get_exchange_rate("INR_TO_NPR") or DEFAULT_INR_TO_NPR_RATE
    npr_to_inr = get_exchange_rate("NPR_TO_INR") or DEFAULT_NPR_TO_INR_RATE
    text = CURRENT_RATE.format(
        inr_to_npr=f"{inr_to_npr:.4f}",
        npr_to_inr=f"{npr_to_inr:.4f}",
        fee=f"{SERVICE_FEE_PERCENTAGE:.1f}"
    )
    await callback.message.answer(text, reply_markup=get_cancel_reply_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "btn_history")
async def cb_btn_history(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, exchange_type, amount, final_amount, status, created_at
        FROM exchange_requests
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 5
    """, (user_id,))
    orders = cursor.fetchall()
    conn.close()
    if not orders:
        text = TRANSACTION_HISTORY.format(history="No transactions yet.")
    else:
        lines = []
        for o in orders:
            status_emoji = {"PENDING": "⏳", "APPROVED": "✅", "REJECTED": "❌"}.get(o[4], "❓")
            lines.append(f"{status_emoji} <b>Order #{o[0]}</b>: {o[2]:,.2f} ➔ {o[3]:,.2f} ({o[4]})\n<i>{format_timestamp(o[5])}</i>")
        text = TRANSACTION_HISTORY.format(history="\n\n".join(lines))
    await callback.message.answer(text, reply_markup=get_cancel_reply_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "btn_deposit")
async def cb_btn_deposit(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📥 <b>Deposit Funds into Wallet</b>\n\nChoose currency to deposit:",
        reply_markup=get_load_currency_reply_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.in_(["deposit_inr", "deposit_npr"]))
async def cb_deposit_currency(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    currency = "INR" if "inr" in callback.data else "NPR"
    await state.update_data(load_currency=currency)
    await state.set_state(WalletState.waiting_for_load_amount)

    symbol = "₹" if currency == "INR" else "₨"
    await callback.message.answer(
        f"📥 <b>Deposit {currency}</b>\n\n"
        f"Limits: {symbol}100 – {symbol}100,000\n"
        f"Type the amount to deposit:",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "btn_withdraw")
async def cb_btn_withdraw(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    user_info = get_user_info(user_id)
    if not user_info:
        await callback.message.answer("❌ Profile not found.")
        return
    await state.set_state(WalletState.waiting_for_withdraw_amount)
    await callback.message.answer(
        "💸 <b>Wallet Withdrawal</b>\n\n"
        f"<blockquote>"
        f"• Available INR: ₹{user_info['wallet_inr']:,.2f}\n"
        f"• Available NPR: ₨{user_info['wallet_npr']:,.2f}"
        f"</blockquote>\n\n"
        "Enter currency and amount (e.g. <code>INR 2000</code> or <code>NPR 3000</code>):",
        reply_markup=get_cancel_reply_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "btn_profile")
async def cb_btn_profile(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user_info = get_user_info(user_id)
    if not user_info:
        await callback.message.answer("❌ Profile not found.")
        return
    ref_count = get_referred_users_count(user_id)
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_info['referral_code']}"
    profile_text = PROFILE_MESSAGE.format(
        user_id=user_id,
        username=f"@{callback.from_user.username}" if callback.from_user.username else "N/A",
        name=safe_html(callback.from_user.full_name),
        joined_date=format_timestamp(user_info["joined_date"]),
        wallet_inr=f"{user_info['wallet_inr']:,.2f}",
        wallet_npr=f"{user_info['wallet_npr']:,.2f}",
        total_exchanges=user_info["total_exchanges"],
        total_volume=f"{user_info['total_volume']:,.2f}",
        ref_count=ref_count,
        ref_bonus=f"{REFERRAL_BONUS_PERCENT}%",
        ref_link=ref_link
    )
    await callback.message.answer(profile_text, reply_markup=get_cancel_reply_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "btn_status")
async def cb_btn_status(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, exchange_type, amount, final_amount, status, created_at
        FROM exchange_requests
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    latest = cursor.fetchone()
    conn.close()
    if latest:
        status_badge = {
            "PENDING": "⏳ Under Review",
            "APPROVED": "✅ Approved / Processing",
            "COMPLETED": "🎉 Completed",
            "REJECTED": "❌ Rejected",
        }.get(latest[4], latest[4])
        resp = (
            f"🔍 <b>Latest Order: #{latest[0]}</b>\n\n"
            f"<blockquote>"
            f"• <b>Type:</b> {get_exchange_type_display(latest[1])}\n"
            f"• <b>Amount:</b> <code>{latest[2]:,.2f}</code> ➔ <b>{latest[3]:,.2f}</b>\n"
            f"• <b>Status:</b> <b>{status_badge}</b>\n"
            f"• <b>Date:</b> <code>{format_timestamp(latest[5])}</code>"
            f"</blockquote>\n\n"
            f"<i>💡 To check any specific order: <code>/status &lt;Order_ID&gt;</code></i>"
        )
        await callback.message.answer(resp, reply_markup=get_cancel_reply_keyboard(), parse_mode="HTML")
    else:
        await callback.message.answer(
            "🔍 <b>Order Status Tracker</b>\n\n"
            "<blockquote>No recent orders found on your account.</blockquote>\n"
            "<i>To track an order, send: <code>/status &lt;Order_ID&gt;</code></i>",
            reply_markup=get_cancel_reply_keyboard(),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "btn_about")
async def cb_btn_about(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(ABOUT_US_MESSAGE, reply_markup=get_cancel_reply_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "btn_help")
async def cb_btn_help(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(HOW_IT_WORKS, reply_markup=get_cancel_reply_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "btn_support")
async def cb_btn_support(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(CONTACT_US_MESSAGE, reply_markup=get_cancel_reply_keyboard(), parse_mode="HTML")


# Admin Stats
@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(joined_date) = DATE('now')")
    new_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM exchange_requests")
    total_txns = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM exchange_requests WHERE status IN ('APPROVED', 'COMPLETED')")
    completed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM exchange_requests WHERE status = 'PENDING'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM exchange_requests WHERE status = 'REJECTED'")
    rejected = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM exchange_requests WHERE exchange_type = 'INR_TO_NPR' AND status = 'APPROVED'")
    inr_vol = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM exchange_requests WHERE exchange_type = 'NPR_TO_INR' AND status = 'APPROVED'")
    npr_vol = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(service_fee), 0) FROM exchange_requests WHERE status = 'APPROVED'")
    total_fees = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'OPEN'")
    open_tickets = cursor.fetchone()[0]
    conn.close()

    inr_rate = get_exchange_rate("INR_TO_NPR") or DEFAULT_INR_TO_NPR_RATE
    npr_rate = get_exchange_rate("NPR_TO_INR") or DEFAULT_NPR_TO_INR_RATE

    text = ADMIN_STATS.format(
        total_users=total_users,
        new_users=new_users,
        active_today=new_users,
        total_transactions=total_txns,
        completed=completed,
        pending=pending,
        rejected=rejected,
        total_inr=f"₹{inr_vol:,.2f}",
        total_npr=f"₨{npr_vol:,.2f}",
        total_fees=f"₹{total_fees:,.2f}",
        inr_to_npr=f"{inr_rate:.4f}",
        npr_to_inr=f"{npr_rate:.4f}",
        open_tickets=open_tickets
    )
    await callback.message.answer(text, parse_mode="HTML")


# Admin Search
@router.message(Command("find"))
@router.callback_query(F.data == "admin_search")
async def cb_admin_find(event: Message | CallbackQuery, state: FSMContext):
    user_id = event.from_user.id
    if not is_admin(user_id):
        return

    msg = event.message if isinstance(event, CallbackQuery) else event
    if isinstance(event, CallbackQuery):
        await event.answer()

    if isinstance(event, Message) and len(event.text.split()) > 1:
        query = " ".join(event.text.split()[1:])
        await _run_admin_search(msg, query)
        return

    await state.set_state(AdminState.waiting_for_search_query)
    await msg.answer("🔍 Enter User ID, Username, Order ID, or UTR number:")


@router.message(AdminState.waiting_for_search_query)
async def process_search_query(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await _run_admin_search(message, message.text.strip())


async def _run_admin_search(message: Message, query: str):
    res = search_records(query)
    users = res.get("users", [])
    requests = res.get("requests", [])

    if not users and not requests:
        await message.answer(f"🔍 No results found for '{safe_html(query)}'.")
        return

    lines = [f"🔍 <b>Search Results for: '{safe_html(query)}'</b>\n"]
    if users:
        lines.append("<b>👤 Users:</b>")
        for u in users:
            lines.append(f"• ID: <code>{u[0]}</code> | @{safe_html(u[1])} ({safe_html(u[2])})\n  Wallet: ₹{u[4]:,.2f} | ₨{u[5]:,.2f} | Trades: {u[3]}")
        lines.append("")

    if requests:
        lines.append("<b>📋 Orders:</b>")
        for r in requests:
            lines.append(f"• #{r[0]} | User: <code>{r[1]}</code> | {r[2]} | {r[5]}\n  Amount: {r[3]:,.2f} ➔ {r[4]:,.2f} | UTR: <code>{safe_html(r[6])}</code>")

    await message.answer("\n".join(lines), parse_mode="HTML")
