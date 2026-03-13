from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from database import get_db_connection, init_database
from config import BOT_TOKEN, ADMIN_IDS, SERVICE_FEE_PERCENTAGE, BANNER_IMAGE_URL, PAYMENT_IMAGE_URL
from keyboards import (
    get_start_keyboard, get_exchange_confirmation_keyboard,
    get_payment_keyboard, get_admin_approval_keyboard,
    get_admin_menu_keyboard, get_settings_keyboard,
    get_load_wallet_keyboard, get_back_button
)
from messages import *
from utils import (
    validate_amount, calculate_exchange, get_exchange_rate,
    get_payment_details, check_anti_spam, is_user_banned,
    format_currency, format_timestamp, get_exchange_type_display,
    validate_transaction_id, get_user_info, generate_referral_code
)

# Initialize router
router = Router()

# Define states
class ExchangeStates(StatesGroup):
    selecting_type = State()
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

class WalletStates(StatesGroup):
    loading_wallet = State()
    entering_load_amount = State()

# ============================================================================
# START COMMAND AND MENU
# ============================================================================

@router.message(lambda msg: msg.text == "/start" or msg.text == "/menu")
async def start_command(message: Message, state: FSMContext):
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name or "User"
    last_name = message.from_user.last_name or ""

    # Check if user is banned
    if is_user_banned(user_id):
        await message.answer(ERROR_MESSAGES["banned"])
        return

    # Register user if not exists
    # Use centralized DB helper with retries
    from database import execute_db

    existing = execute_db("SELECT user_id FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not existing:
        referral_code = generate_referral_code(user_id)
        execute_db("INSERT INTO users (user_id, username, first_name, last_name, referral_code) VALUES (?, ?, ?, ?, ?)", (user_id, username, first_name, last_name, referral_code), commit=True)

    # Clear state
    await state.clear()

    # Send welcome message
    try:
        await message.answer_photo(
            photo="https://via.placeholder.com/1280x720?text=Currency+Exchange+Bot",
            caption=WELCOME_MESSAGE,
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )
    except:
        # Fallback if image URL fails
        await message.answer(
            text=WELCOME_MESSAGE,
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )


@router.message(lambda msg: msg.text and msg.text.startswith("/restart"))
async def admin_restart(message: Message):
    """Admin command to update code from upstream and restart the bot"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        return

    await message.answer("🔄 Starting update from upstream... This may take a few moments.")
    from updater import restart_bot
    ok, msg = await restart_bot()
    await message.answer(msg)

    if ok:
        # Attempt graceful restart of current process
        try:
                import os, sys
                # If running inside Docker/container, exit and let the supervisor restart
                in_docker = os.getenv("IN_DOCKER", "0")
                if in_docker == "1":
                    await message.answer("♻️ Exiting process; container supervisor should restart the bot.")
                    sys.exit(0)
                else:
                    await message.answer("♻️ Restarting bot process now...")
                    os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            await message.answer(f"Restart failed: {e}")

# ============================================================================
# EXCHANGE FLOW
# ============================================================================

@router.callback_query(F.data == "exchange_inr_to_npr")
async def exchange_inr_to_npr(callback: CallbackQuery, state: FSMContext):
    """Handle INR to NPR exchange"""
    user_id = callback.from_user.id

    if is_user_banned(user_id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return

    can_exchange, wait_time = check_anti_spam(user_id)
    if not can_exchange:
        await callback.answer(
            f"⏱️ Too many requests! Wait {wait_time} minutes.",
            show_alert=True
        )
        return

    await state.set_state(ExchangeStates.entering_amount)
    await state.update_data(exchange_type="INR_TO_NPR")

    await callback.message.edit_text(
        text=ENTER_AMOUNT,
        parse_mode="HTML",
        reply_markup=get_back_button()
    )

@router.callback_query(F.data == "exchange_npr_to_inr")
async def exchange_npr_to_inr(callback: CallbackQuery, state: FSMContext):
    """Handle NPR to INR exchange"""
    user_id = callback.from_user.id

    if is_user_banned(user_id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return

    can_exchange, wait_time = check_anti_spam(user_id)
    if not can_exchange:
        await callback.answer(
            f"⏱️ Too many requests! Wait {wait_time} minutes.",
            show_alert=True
        )
        return

    await state.set_state(ExchangeStates.entering_amount)
    await state.update_data(exchange_type="NPR_TO_INR")

    await callback.message.edit_text(
        text=ENTER_AMOUNT,
        parse_mode="HTML",
        reply_markup=get_back_button()
    )

@router.message(ExchangeStates.entering_amount)
async def process_amount(message: Message, state: FSMContext):
    """Process entered amount"""
    is_valid, result = validate_amount(message.text)

    if not is_valid:
        await message.answer(
            text=f"❌ {result}\n\nPlease enter a valid amount between 100 and 100,000",
            parse_mode="HTML"
        )
        return

    amount = result
    data = await state.get_data()
    exchange_type = data["exchange_type"]

    # Check user's wallet balance before proceeding
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    wallet_inr = float(user_info["wallet_inr"] or 0) if user_info else 0
    wallet_npr = float(user_info["wallet_npr"] or 0) if user_info else 0

    if exchange_type == "INR_TO_NPR":
        if wallet_inr < amount:
            await message.answer(
                text=(f"⚠️ Insufficient INR wallet balance.\n\n"
                      f"Requested: {format_currency(amount, 'INR')}\n"
                      f"Your INR Wallet: {format_currency(wallet_inr, 'INR')}\n\n"
                      "Please load your INR wallet before proceeding."),
                parse_mode="HTML",
                reply_markup=get_load_wallet_keyboard()
            )
            return
    else:
        # NPR_TO_INR
        if wallet_npr < amount:
            await message.answer(
                text=(f"⚠️ Insufficient NPR wallet balance.\n\n"
                      f"Requested: {format_currency(amount, 'NPR')}\n"
                      f"Your NPR Wallet: {format_currency(wallet_npr, 'NPR')}\n\n"
                      "Please load your NPR wallet before proceeding."),
                parse_mode="HTML",
                reply_markup=get_load_wallet_keyboard()
            )
            return

    # Get exchange rate
    rate = get_exchange_rate(exchange_type)
    if not rate:
        await message.answer("⚠️ Exchange rate not available. Please try again later.")
        return

    # Calculate
    calculated, fee, final = calculate_exchange(amount, rate)

    # Determine currencies
    if exchange_type == "INR_TO_NPR":
        from_currency, to_currency = "INR", "NPR"
    else:
        from_currency, to_currency = "NPR", "INR"

    # Store data
    await state.update_data(
        amount=amount,
        exchange_rate=rate,
        calculated_amount=calculated,
        service_fee=fee,
        final_amount=final,
        from_currency=from_currency,
        to_currency=to_currency
    )

    # Show summary
    summary = EXCHANGE_SUMMARY.format(
        amount=format_currency(amount, from_currency),
        from_currency=from_currency,
        rate=rate,
        to_currency=to_currency,
        calculated_amount=format_currency(calculated, to_currency),
        fee_percent=SERVICE_FEE_PERCENTAGE,
        service_fee=format_currency(fee, to_currency),
        final_amount=format_currency(final, to_currency)
    )

    await state.set_state(ExchangeStates.confirming_exchange)
    await message.answer(
        text=summary,
        parse_mode="HTML",
        reply_markup=get_exchange_confirmation_keyboard()
    )

@router.callback_query(F.data == "confirm_exchange")
async def confirm_exchange(callback: CallbackQuery, state: FSMContext):
    """Confirm exchange and show payment details"""
    user_id = callback.from_user.id
    data = await state.get_data()

    upi_id, esewa_id = get_payment_details()

    payment_msg = PAYMENT_INSTRUCTIONS.format(
        upi_id=upi_id,
        esewa_id=esewa_id,
        user_id=user_id
    )

    await state.set_state(ExchangeStates.waiting_payment)
    await state.update_data(upi_id=upi_id, esewa_id=esewa_id)

    try:
        await callback.message.answer_photo(
            photo="https://via.placeholder.com/800x400?text=Payment+Instructions",
            caption=payment_msg,
            parse_mode="HTML",
            reply_markup=get_payment_keyboard()
        )
    except:
        await callback.message.answer(
            text=payment_msg,
            parse_mode="HTML",
            reply_markup=get_payment_keyboard()
        )

@router.callback_query(F.data == "payment_done")
async def payment_done(callback: CallbackQuery, state: FSMContext):
    """User confirms payment is sent"""
    await state.set_state(ExchangeStates.uploading_screenshot)

    await callback.message.answer(
        text="📸 <b>Upload Payment Screenshot</b>\n\nPlease send a screenshot of your payment confirmation.",
        parse_mode="HTML",
        reply_markup=get_back_button()
    )

@router.message(ExchangeStates.uploading_screenshot)
async def receive_screenshot(message: Message, state: FSMContext):
    """Receive payment screenshot"""
    if not message.photo:
        await message.answer("❌ Please send a valid image file.")
        return

    # Store file ID
    file_id = message.photo[-1].file_id
    await state.update_data(screenshot_file_id=file_id)

    await state.set_state(ExchangeStates.uploading_transaction_id)
    await message.answer(
        text="📋 <b>Transaction ID</b>\n\nPlease send your transaction ID (from payment confirmation).",
        parse_mode="HTML",
        reply_markup=get_back_button()
    )

@router.message(ExchangeStates.uploading_transaction_id)
async def receive_transaction_id(message: Message, state: FSMContext):
    """Receive transaction ID and save request"""
    transaction_id = message.text.strip()

    if not validate_transaction_id(transaction_id):
        await message.answer("❌ Invalid transaction ID format. Please try again.")
        return

    # Get all data
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    # Save to database
    from database import execute_db

    request_id = execute_db("INSERT INTO exchange_requests (user_id, username, exchange_type, amount, exchange_rate, calculated_amount, service_fee, final_amount, transaction_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
        user_id, username, data["exchange_type"], data["amount"], data["exchange_rate"], data["calculated_amount"], data["service_fee"], data["final_amount"], transaction_id, "pending"
    ), commit=True)

    # Confirm to user
    await message.answer(
        text=SUCCESS_MESSAGES["payment_received"] + "\n\n" +
             "Your request is now being reviewed by our admin team.\n" +
             "You will receive a notification once it's processed.",
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )

    # Send to admin
    await notify_admin(user_id, username, data, transaction_id, request_id, message)

    await state.clear()

@router.callback_query(F.data == "cancel_exchange")
async def cancel_exchange(callback: CallbackQuery, state: FSMContext):
    """Cancel exchange"""
    await state.clear()
    await callback.message.answer(
        text="❌ Exchange cancelled. Returning to menu...",
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    """Cancel payment"""
    await state.clear()
    await callback.message.answer(
        text="❌ Payment cancelled. Returning to menu...",
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )

# ============================================================================
# OTHER MAIN FEATURES
# ============================================================================

@router.callback_query(F.data == "check_rate")
async def check_rate(callback: CallbackQuery):
    """Show current exchange rates"""
    inr_to_npr = get_exchange_rate("INR_TO_NPR")
    npr_to_inr = get_exchange_rate("NPR_TO_INR")

    rate_msg = CURRENT_RATE.format(
        inr_to_npr=inr_to_npr or "N/A",
        npr_to_inr=npr_to_inr or "N/A"
    )

    await callback.message.edit_text(
        text=rate_msg,
        parse_mode="HTML",
        reply_markup=get_back_button()
    )


@router.callback_query(F.data == "wallet_balance")
async def wallet_balance(callback: CallbackQuery):
    """Show user's current wallet balances"""
    user_id = callback.from_user.id

    if is_user_banned(user_id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return

    user_info = get_user_info(user_id)
    if not user_info:
        await callback.answer("⚠️ Profile not found.", show_alert=True)
        return

    inr_bal = format_currency(user_info.get("wallet_inr") or 0, "INR")
    npr_bal = format_currency(user_info.get("wallet_npr") or 0, "NPR")

    text = (
        f"💼 <b>Your Wallet Balances</b>\n\n"
        f"• 💵 INR: <b>{inr_bal}</b>\n"
        f"• ₨ NPR: <b>{npr_bal}</b>\n\n"
        "Use 'Load Wallet' to add funds if needed."
    )

    await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=get_load_wallet_keyboard())

@router.callback_query(F.data == "transaction_history")
async def show_transaction_history(callback: CallbackQuery):
    """Show user's transaction history"""
    user_id = callback.from_user.id

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT request_id, exchange_type, amount, final_amount, status, created_at
        FROM exchange_requests
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
    """, (user_id,))

    transactions = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM exchange_requests
        WHERE user_id = ? AND status = 'completed'
    """, (user_id,))

    stats = cursor.fetchone()
    total = stats[0] or 0
    total_amount = stats[1] or 0

    conn.close()

    if not transactions:
        history_text = "<i>No transactions yet.</i>"
    else:
        history_text = ""
        for txn in transactions:
            history_text += (
                f"#{txn[0]} | {get_exchange_type_display(txn[1])}\n"
                f"{format_currency(txn[2], 'INR')} → {format_currency(txn[3], 'NPR')}\n"
                f"Status: <b>{txn[4].upper()}</b> | {format_timestamp(txn[5])}\n\n"
            )

    history_msg = TRANSACTION_HISTORY.format(
        transactions=history_text,
        total=total,
        total_amount=format_currency(total_amount, "INR")
    )

    await callback.message.edit_text(
        text=history_msg,
        parse_mode="HTML",
        reply_markup=get_back_button()
    )

@router.callback_query(F.data == "how_it_works")
async def how_it_works(callback: CallbackQuery):
    """Show how it works guide"""
    await callback.message.edit_text(
        text=HOW_IT_WORKS,
        parse_mode="HTML",
        reply_markup=get_back_button()
    )

@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    """Show support information"""
    await callback.message.edit_text(
        text=SUPPORT_MESSAGE,
        parse_mode="HTML",
        reply_markup=get_back_button()
    )

@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    """Show user profile"""
    user_id = callback.from_user.id
    user_info = get_user_info(user_id)

    if not user_info:
        await callback.answer("⚠️ Profile not found.", show_alert=True)
        return

    # Count referrals
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    referred_count = cursor.fetchone()[0]
    conn.close()

    profile_msg = PROFILE_MESSAGE.format(
        first_name=user_info["first_name"],
        username=user_info["username"],
        user_id=user_id,
        joined_date=format_timestamp(user_info["joined_date"]),
        wallet_inr=format_currency(user_info["wallet_inr"], "INR"),
        wallet_npr=format_currency(user_info["wallet_npr"], "NPR"),
        total_exchanges=user_info["total_exchanges"],
        total_amount=format_currency(user_info["total_amount"], "INR"),
        referral_code=user_info["referral_code"],
        referred_count=referred_count
    )

    await callback.message.edit_text(
        text=profile_msg,
        parse_mode="HTML",
        reply_markup=get_back_button()
    )

@router.callback_query(F.data == "load_wallet")
async def load_wallet(callback: CallbackQuery):
    """Show wallet loading options"""
    await callback.message.edit_text(
        text="💰 <b>Load Wallet</b>\n\nSelect which currency you want to load:",
        parse_mode="HTML",
        reply_markup=get_load_wallet_keyboard()
    )


@router.callback_query(F.data == "load_inr")
async def load_inr(callback: CallbackQuery, state: FSMContext):
    """Start loading INR into wallet"""
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return

    await state.set_state(WalletStates.entering_load_amount)
    await state.update_data(load_currency="INR")
    await callback.message.edit_text(text="💵 <b>Load INR</b>\n\nEnter amount to load:", parse_mode="HTML", reply_markup=get_back_button())


@router.callback_query(F.data == "load_npr")
async def load_npr(callback: CallbackQuery, state: FSMContext):
    """Start loading NPR into wallet"""
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        await callback.answer(ERROR_MESSAGES["banned"], show_alert=True)
        return

    await state.set_state(WalletStates.entering_load_amount)
    await state.update_data(load_currency="NPR")
    await callback.message.edit_text(text="₨ <b>Load NPR</b>\n\nEnter amount to load:", parse_mode="HTML", reply_markup=get_back_button())


@router.message(WalletStates.entering_load_amount)
async def process_wallet_load_amount(message: Message, state: FSMContext):
    """Process amount for wallet loading and send payment instructions"""
    is_valid, result = validate_amount(message.text)
    if not is_valid:
        await message.answer(text=f"❌ {result}", parse_mode="HTML")
        return

    amount = result
    data = await state.get_data()
    load_currency = data.get("load_currency", "INR")
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    # Prepare a wallet-load exchange in FSM state (don't save to DB yet).
    # We will ask for screenshot and transaction ID, then persist and notify admin
    # once both are received (same flow as INR↔NPR exchange).
    exchange_type = "LOAD_INR" if load_currency == "INR" else "LOAD_NPR"

    # Store all necessary details in state; set waiting for payment so
    # when user clicks 'I have paid' the standard payment flow continues.
    await state.update_data(
        exchange_type=exchange_type,
        amount=amount,
        exchange_rate=1.0,
        calculated_amount=amount,
        service_fee=0.0,
        final_amount=amount,
        from_currency=load_currency,
        to_currency=load_currency
    )

    # Send payment instructions and set to waiting_payment so `payment_done`
    # handler will prompt for screenshot (reusing the exchange flow behavior).
    upi_id, esewa_id = get_payment_details()
    payment_msg = PAYMENT_INSTRUCTIONS.format(upi_id=upi_id, esewa_id=esewa_id, user_id=user_id)

    try:
        await message.answer_photo(photo=BANNER_IMAGE_URL, caption=payment_msg, parse_mode="HTML", reply_markup=get_payment_keyboard())
    except Exception:
        await message.answer(text=payment_msg, parse_mode="HTML", reply_markup=get_payment_keyboard())

    await state.set_state(ExchangeStates.waiting_payment)

# ============================================================================
# BACK TO START
# ============================================================================

@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    """Go back to start menu"""
    await state.clear()
    await callback.message.edit_text(
        text=WELCOME_MESSAGE,
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )

# ============================================================================
# NOTIFICATION FUNCTIONS
# ============================================================================

async def notify_admin(user_id, username, data, transaction_id, request_id, message):
    """Send notification to admin about new exchange request"""
    admin_msg = ADMIN_REQUEST.format(
        user_id=user_id,
        username=username,
        exchange_type=get_exchange_type_display(data["exchange_type"]),
        amount=format_currency(data["amount"], data["from_currency"]),
        rate=data["exchange_rate"],
        final_amount=format_currency(data["final_amount"], data["to_currency"]),
        to_currency=data["to_currency"],
        transaction_id=transaction_id
    )

    # Send to all admins
    from aiogram import Bot
    bot = Bot(token=BOT_TOKEN)

    for admin_id in ADMIN_IDS:
        try:
            if "screenshot_file_id" in data:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=data["screenshot_file_id"],
                    caption=admin_msg,
                    parse_mode="HTML",
                    reply_markup=get_admin_approval_keyboard(request_id)
                )
            else:
                await bot.send_message(
                    chat_id=admin_id,
                    text=admin_msg,
                    parse_mode="HTML",
                    reply_markup=get_admin_approval_keyboard(request_id)
                )
        except Exception as e:
            print(f"Error sending admin notification: {e}")


# ==========================
# Admin Commands & Actions
# ==========================


@router.message(lambda msg: msg.text and msg.text.startswith("/admin"))
async def admin_panel(message: Message, state: FSMContext):
    """Show admin panel to authorized admins"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        return

    await state.clear()
    await message.answer("<b>Admin Panel</b>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "admin_pending")
async def admin_pending(callback: CallbackQuery):
    """List pending exchange requests"""
    admin_id = callback.from_user.id
    if admin_id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT request_id, user_id, username, exchange_type, amount, final_amount, status, created_at FROM exchange_requests WHERE status = 'pending' ORDER BY created_at DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await callback.message.edit_text("<b>No pending requests.</b>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())
        return

    text = "<b>Pending Requests</b>\n\n"
    for r in rows:
        text += f"#{r[0]} • @{r[2]} • {get_exchange_type_display(r[3])} • {r[4]} → {r[5]} • {r[6].upper()}\n"

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu_keyboard())


@router.callback_query(lambda c: c.data and c.data.startswith("admin_approve_"))
async def admin_approve(callback: CallbackQuery):
    """Approve an exchange request"""
    admin_id = callback.from_user.id
    if admin_id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    request_id = int(callback.data.split("_")[-1])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, exchange_type, final_amount, status FROM exchange_requests WHERE request_id = ?", (request_id,))
    row = cursor.fetchone()
    if not row:
        await callback.answer("⚠️ Request not found.", show_alert=True)
        conn.close()
        return

    user_id = row[0]
    username = row[1]
    exchange_type = row[2]
    final_amount = row[3]
    status = row[4]

    # Update request status (with retries) and log approval
    from database import execute_db
    execute_db("UPDATE exchange_requests SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE request_id = ?", (request_id,), commit=True)
    execute_db("INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)", (admin_id, 'approve', request_id, 'Approved by admin'), commit=True)

    # Determine currency mapping for messages and transactions
    if exchange_type == 'INR_TO_NPR':
        payout_currency = 'NPR'
        from_currency = 'INR'
        to_currency = 'NPR'
    elif exchange_type == 'NPR_TO_INR':
        payout_currency = 'INR'
        from_currency = 'NPR'
        to_currency = 'INR'
    elif exchange_type == 'LOAD_INR':
        payout_currency = 'INR'
        from_currency = 'INR'
        to_currency = 'INR'
    elif exchange_type == 'LOAD_NPR':
        payout_currency = 'NPR'
        from_currency = 'NPR'
        to_currency = 'NPR'
    else:
        payout_currency = 'NPR'
        from_currency = 'INR'
        to_currency = 'NPR'

    # Notify user about approval
    from aiogram import Bot
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=user_id, text=APPROVED_MESSAGE.format(final_amount=final_amount, to_currency=to_currency), parse_mode="HTML")
    except Exception as e:
        print(f"Error notifying user on approve: {e}")

    # Auto payout / credit handling
    conn = get_db_connection()
    cursor = conn.cursor()
    # If this is a wallet load, credit the user's wallet immediately
    if exchange_type in ('LOAD_INR', 'LOAD_NPR'):
        # mark completed
        cursor.execute("UPDATE exchange_requests SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE request_id = ?", (request_id,))
        # credit wallet
        if exchange_type == 'LOAD_INR':
            cursor.execute("UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) + ? WHERE user_id = ?", (final_amount, user_id))
        else:
            cursor.execute("UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?", (final_amount, user_id))
        # record transaction
        cursor.execute("INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status) VALUES (?, ?, ?, ?, ?, ?)", (user_id, request_id, 'wallet_load', final_amount, payout_currency, 'completed'))
        cursor.execute("INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)", (admin_id, 'wallet_credit', request_id, 'Wallet load credited'))
        conn.commit()
        conn.close()
    else:
        # For standard exchanges: mark approved only and provide admin a 'Mark Paid' button
        # so admin can confirm they have sent the exchanged funds to the user.
        execute_db("UPDATE exchange_requests SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE request_id = ?", (request_id,), commit=True)
        # send admin a quick action message to mark paid
        try:
            mark_paid_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Mark Paid", callback_data=f"admin_paid_{request_id}"), InlineKeyboardButton(text="❌ Reject", callback_data=f"admin_reject_{request_id}")]])
            await bot.send_message(chat_id=admin_id, text=f"Request #{request_id} approved. Use the button below once you've sent the payment to the user.", reply_markup=mark_paid_kb)
        except Exception:
            pass
        conn.close()

    # Referral reward: only for exchanges (not wallet loads)
    if exchange_type not in ('LOAD_INR', 'LOAD_NPR'):
        try:
            ref = execute_db("SELECT referred_by FROM users WHERE user_id = ?", (user_id,), fetchone=True)
            if ref and ref[0]:
                referrer_id = ref[0]
                bonus_str = execute_db("SELECT setting_value FROM admin_settings WHERE setting_name = 'referral_bonus_percent'", fetchone=True)
                bonus_percent = float(bonus_str[0]) if bonus_str else 1.0
                bonus_amount = float(final_amount) * (bonus_percent / 100.0)
                # Credit to referrer's wallet in payout currency
                if payout_currency == 'NPR':
                    execute_db("UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?", (bonus_amount, referrer_id), commit=True)
                else:
                    execute_db("UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) + ? WHERE user_id = ?", (bonus_amount, referrer_id), commit=True)
                execute_db("INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status) VALUES (?, ?, ?, ?, ?, ?)", (referrer_id, request_id, 'referral_bonus', bonus_amount, payout_currency, 'completed'), commit=True)
                # Notify referrer
                from aiogram import Bot
                bot = Bot(token=BOT_TOKEN)
                try:
                    await bot.send_message(chat_id=referrer_id, text=f"🎉 You received a referral bonus of {payout_currency}{bonus_amount:,.2f} for referring @{username}")
                except Exception:
                    pass
        except Exception as e:
            print(f"Referral reward failed: {e}")

    # Send completion message to user
    from datetime import datetime
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    try:
        await bot.send_message(chat_id=user_id, text=COMPLETED_MESSAGE.format(sent_amount=final_amount, from_currency=from_currency, received_amount=final_amount, to_currency=to_currency, service_fee='0', request_id=request_id, timestamp=timestamp), parse_mode="HTML")
    except Exception as e:
        print(f"Error sending completion message: {e}")

    await callback.answer("✅ Request approved and processed.")
    await callback.message.edit_reply_markup(reply_markup=None)



@router.callback_query(lambda c: c.data and c.data.startswith("admin_paid_"))
async def admin_mark_paid(callback: CallbackQuery):
    """Admin confirms they've sent payment to user — finalize payout and update wallet."""
    admin_id = callback.from_user.id
    if admin_id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    request_id = int(callback.data.split("_")[-1])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, exchange_type, final_amount, status FROM exchange_requests WHERE request_id = ?", (request_id,))
    row = cursor.fetchone()
    if not row:
        await callback.answer("⚠️ Request not found.", show_alert=True)
        conn.close()
        return

    user_id = row[0]
    username = row[1]
    exchange_type = row[2]
    final_amount = row[3]
    status = row[4]

    if status != 'approved':
        await callback.answer("⚠️ Request is not in approved state.", show_alert=True)
        conn.close()
        return

    # finalize payout: mark completed, update user's wallet, record transaction
    if exchange_type == 'INR_TO_NPR':
        # user should receive NPR
        cursor.execute("UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?", (final_amount, user_id))
        payout_currency = 'NPR'
        from_currency = 'INR'
        to_currency = 'NPR'
    elif exchange_type == 'NPR_TO_INR':
        cursor.execute("UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) + ? WHERE user_id = ?", (final_amount, user_id))
        payout_currency = 'INR'
        from_currency = 'NPR'
        to_currency = 'INR'
    else:
        # fallback — credit NPR
        cursor.execute("UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?", (final_amount, user_id))
        payout_currency = 'NPR'
        from_currency = 'INR'
        to_currency = 'NPR'

    cursor.execute("UPDATE exchange_requests SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE request_id = ?", (request_id,))
    cursor.execute("INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status) VALUES (?, ?, ?, ?, ?, ?)", (user_id, request_id, 'payout', final_amount, payout_currency, 'completed'))
    cursor.execute("INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)", (admin_id, 'paid', request_id, 'Admin confirmed payout'))
    conn.commit()
    conn.close()

    # referral reward (if any)
    try:
        ref = execute_db("SELECT referred_by FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        if ref and ref[0]:
            referrer_id = ref[0]
            bonus_str = execute_db("SELECT setting_value FROM admin_settings WHERE setting_name = 'referral_bonus_percent'", fetchone=True)
            bonus_percent = float(bonus_str[0]) if bonus_str else 1.0
            bonus_amount = float(final_amount) * (bonus_percent / 100.0)
            if payout_currency == 'NPR':
                execute_db("UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?", (bonus_amount, referrer_id), commit=True)
            else:
                execute_db("UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) + ? WHERE user_id = ?", (bonus_amount, referrer_id), commit=True)
            execute_db("INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status) VALUES (?, ?, ?, ?, ?, ?)", (referrer_id, request_id, 'referral_bonus', bonus_amount, payout_currency, 'completed'), commit=True)
            try:
                from aiogram import Bot
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(chat_id=referrer_id, text=f"🎉 You received a referral bonus of {payout_currency}{bonus_amount:,.2f} for referring @{username}")
            except Exception:
                pass
    except Exception as e:
        print(f"Referral reward failed on paid: {e}")

    # notify user and admin
    from aiogram import Bot
    bot = Bot(token=BOT_TOKEN)
    try:
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        await bot.send_message(chat_id=user_id, text=COMPLETED_MESSAGE.format(sent_amount=final_amount, from_currency=from_currency, received_amount=final_amount, to_currency=to_currency, service_fee='0', request_id=request_id, timestamp=timestamp), parse_mode="HTML")
    except Exception:
        pass

    try:
        await bot.send_message(chat_id=admin_id, text=f"✅ Marked request #{request_id} as PAID to user @{username}.")
    except Exception:
        pass

    await callback.answer("✅ Marked as paid and wallet updated.")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(lambda c: c.data and c.data.startswith("admin_reject_"))
async def admin_reject(callback: CallbackQuery, state: FSMContext):
    """Reject an exchange request"""
    admin_id = callback.from_user.id
    if admin_id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    request_id = int(callback.data.split("_")[-1])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM exchange_requests WHERE request_id = ?", (request_id,))
    row = cursor.fetchone()
    if not row:
        await callback.answer("⚠️ Request not found.", show_alert=True)
        conn.close()
        return

    user_id = row[0]

    cursor.execute("UPDATE exchange_requests SET status = 'rejected', admin_notes = 'Rejected by admin' WHERE request_id = ?", (request_id,))
    cursor.execute("INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)", (admin_id, 'reject', request_id, 'Rejected by admin'))
    conn.commit()
    conn.close()

    from aiogram import Bot
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=user_id, text=REJECTED_MESSAGE.format(reason='Validation failed'), parse_mode="HTML")
    except Exception as e:
        print(f"Error notifying user on reject: {e}")

    await callback.answer("❌ Request rejected.")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(lambda c: c.data and c.data.startswith("admin_message_"))
async def admin_message_user(callback: CallbackQuery, state: FSMContext):
    """Initiate messaging a user from admin panel"""
    admin_id = callback.from_user.id
    if admin_id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    request_id = int(callback.data.split("_")[-1])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM exchange_requests WHERE request_id = ?", (request_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        await callback.answer("⚠️ Request not found.", show_alert=True)
        return

    target_user = row[0]
    await state.set_state(AdminStates.messaging_user)
    await state.update_data(target_user=target_user, request_id=request_id)
    await callback.message.answer("✉️ Send the message you'd like to forward to the user:")


@router.message(AdminStates.messaging_user)
async def admin_send_message_to_user(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        await state.clear()
        return

    data = await state.get_data()
    target_user = data.get("target_user")
    request_id = data.get("request_id")

    from aiogram import Bot
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=target_user, text=message.text, parse_mode="HTML")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)", (admin_id, 'message_user', request_id, message.text))
        conn.commit()
        conn.close()
        await message.answer("✅ Message sent to user.")
    except Exception as e:
        await message.answer(f"⚠️ Failed to send message: {e}")

    await state.clear()


@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery):
    """Return to admin menu (for admin users)."""
    admin_id = callback.from_user.id
    if admin_id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    try:
        await callback.message.edit_text("<b>Admin Panel</b>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())
    except Exception:
        # fallback to sending message
        await callback.message.answer("<b>Admin Panel</b>", parse_mode="HTML", reply_markup=get_admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if admin_id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM exchange_requests")
    total_transactions = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM exchange_requests WHERE status = 'completed'")
    completed = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM exchange_requests WHERE status = 'pending'")
    pending = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM exchange_requests WHERE status = 'rejected'")
    rejected = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(amount) FROM exchange_requests")
    total_inr = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(final_amount) FROM exchange_requests")
    total_npr = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(service_fee) FROM exchange_requests")
    total_fees = cursor.fetchone()[0] or 0
    cursor.execute("SELECT setting_value FROM admin_settings WHERE setting_name = 'inr_to_npr_rate'")
    inr_to_npr = cursor.fetchone()[0]
    cursor.execute("SELECT setting_value FROM admin_settings WHERE setting_name = 'npr_to_inr_rate'")
    npr_to_inr = cursor.fetchone()[0]
    conn.close()

    stats_text = ADMIN_STATS.format(
        total_users=total_users,
        active_today=0,
        new_users=0,
        total_transactions=total_transactions,
        completed=completed,
        pending=pending,
        rejected=rejected,
        total_inr=total_inr,
        total_npr=total_npr,
        total_fees=total_fees,
        inr_to_npr=inr_to_npr,
        npr_to_inr=npr_to_inr,
        updated_at=format_timestamp(datetime.now())
    )

    await callback.message.edit_text(stats_text, parse_mode="HTML", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "set_rate")
async def set_rate_start(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if admin_id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    await state.set_state(AdminStates.setting_rate)
    await callback.message.answer("📈 Send the rate in format: inr_to_npr 1.60 OR npr_to_inr 0.625")


@router.message(AdminStates.setting_rate)
async def set_rate_receive(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        await state.clear()
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("❌ Invalid format. Use: inr_to_npr 1.60")
        return

    name, value = parts[0].lower(), parts[1]
    try:
        float(value)
    except:
        await message.answer("❌ Rate must be a number.")
        return

    if name not in ('inr_to_npr', 'npr_to_inr'):
        await message.answer("❌ Unknown rate name. Use inr_to_npr or npr_to_inr.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO admin_settings (setting_name, setting_value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (name + '_rate' if not name.endswith('_rate') else name, value))
    conn.commit()
    conn.close()

    await message.answer(f"✅ Updated {name} to {value}")
    await state.clear()


@router.callback_query(F.data == "update_payment")
async def update_payment_start(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if admin_id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    await state.set_state(AdminStates.updating_payment)
    await callback.message.answer("💳 Send new payment details in format: upi business@upi OR esewa esewa_id")


@router.message(AdminStates.updating_payment)
async def update_payment_receive(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        await state.clear()
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("❌ Invalid format. Use: upi business@upi")
        return

    name, value = parts[0].lower(), parts[1]
    if name not in ('upi', 'esewa'):
        await message.answer("❌ Unknown payment method. Use upi or esewa.")
        return

    key = 'upi_id' if name == 'upi' else 'esewa_id'
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO admin_settings (setting_name, setting_value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (key, value))
    conn.commit()
    conn.close()

    await message.answer(f"✅ Updated {key} to {value}")
    await state.clear()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if admin_id not in ADMIN_IDS:
        await callback.answer("⚠️ Unauthorized.", show_alert=True)
        return

    await state.set_state(AdminStates.broadcasting)
    await callback.message.answer("📣 Send the message to broadcast to all users:")


@router.message(AdminStates.broadcasting)
async def admin_broadcast_send(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        await state.clear()
        return

    text = message.text
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    from aiogram import Bot
    bot = Bot(token=BOT_TOKEN)
    sent = 0
    for u in users:
        try:
            await bot.send_message(chat_id=u[0], text=text, parse_mode="HTML")
            sent += 1
        except Exception:
            continue

    await message.answer(f"📣 Broadcast sent to {sent} users.")
    await state.clear()


@router.message(lambda msg: msg.text and msg.text.startswith("/credit"))
async def admin_credit(message: Message):
    """Admin command to add or set a user's wallet balance.

    Usage: /credit add|set <user_id|@username> <INR|NPR> <amount>
    Examples:
      /credit add 123456789 INR 1000
      /credit set @alice NPR 500
    """
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        return

    parts = message.text.strip().split()
    if len(parts) != 5:
        await message.answer("❌ Invalid format. Use: /credit add|set <user_id|@username> <INR|NPR> <amount>")
        return

    _, action, target, currency, amt_str = parts
    action = action.lower()
    currency = currency.upper()
    if action not in ("add", "set"):
        await message.answer("❌ Action must be 'add' or 'set'.")
        return
    if currency not in ("INR", "NPR"):
        await message.answer("❌ Currency must be INR or NPR.")
        return

    try:
        amount = float(amt_str)
        if amount <= 0:
            raise ValueError()
    except Exception:
        await message.answer("❌ Amount must be a positive number.")
        return

    # Resolve target user id
    target_user_id = None
    if target.startswith("@"):
        uname = target[1:]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE username = ?", (uname,))
        row = cur.fetchone()
        conn.close()
        if not row:
            await message.answer(f"⚠️ User with username @{uname} not found in database.")
            return
        target_user_id = row[0]
    else:
        try:
            target_user_id = int(target)
        except Exception:
            await message.answer("❌ Invalid user identifier. Use numeric user_id or @username.")
            return

    from database import execute_db

    # Apply update
    if currency == 'INR':
        if action == 'add':
            execute_db("UPDATE users SET wallet_inr = COALESCE(wallet_inr,0) + ? WHERE user_id = ?", (amount, target_user_id), commit=True)
            detail = f"Admin added {amount} INR to user {target_user_id}"
        else:
            execute_db("UPDATE users SET wallet_inr = ? WHERE user_id = ?", (amount, target_user_id), commit=True)
            detail = f"Admin set INR wallet to {amount} for user {target_user_id}"
        tx_currency = 'INR'
    else:
        if action == 'add':
            execute_db("UPDATE users SET wallet_npr = COALESCE(wallet_npr,0) + ? WHERE user_id = ?", (amount, target_user_id), commit=True)
            detail = f"Admin added {amount} NPR to user {target_user_id}"
        else:
            execute_db("UPDATE users SET wallet_npr = ? WHERE user_id = ?", (amount, target_user_id), commit=True)
            detail = f"Admin set NPR wallet to {amount} for user {target_user_id}"
        tx_currency = 'NPR'

    # Record transaction and admin log
    execute_db("INSERT INTO transactions (user_id, exchange_request_id, transaction_type, amount, currency, status) VALUES (?, ?, ?, ?, ?, ?)", (target_user_id, None, 'admin_credit', amount, tx_currency, 'completed'), commit=True)
    execute_db("INSERT INTO admin_logs (admin_id, action, request_id, details) VALUES (?, ?, ?, ?)", (admin_id, 'admin_credit', None, detail), commit=True)

    # Fetch new balance
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT wallet_inr, wallet_npr FROM users WHERE user_id = ?", (target_user_id,))
    bal = cur.fetchone()
    conn.close()
    inr_bal = bal[0] or 0
    npr_bal = bal[1] or 0

    # Notify admin
    await message.answer(f"✅ {detail}\n\nNew balances:\nINR: {format_currency(inr_bal, 'INR')}\nNPR: {format_currency(npr_bal, 'NPR')}")

    # Notify user
    from aiogram import Bot
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=target_user_id, text=f"🔔 Admin updated your wallet: {detail}\n\nNew balances:\nINR: {format_currency(inr_bal, 'INR')}\nNPR: {format_currency(npr_bal, 'NPR')}")
    except Exception:
        pass


@router.message(lambda msg: msg.text and msg.text.startswith("/balance"))
async def admin_balance(message: Message):
    """Admin command to query a user's wallet balances.

    Usage: /balance <user_id|@username>
    Example: /balance @alice
    """
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS:
        await message.answer("⚠️ Unauthorized.")
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("❌ Invalid format. Use: /balance <user_id|@username>")
        return

    target = parts[1]
    target_user_id = None
    if target.startswith("@"):
        uname = target[1:]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE username = ?", (uname,))
        row = cur.fetchone()
        conn.close()
        if not row:
            await message.answer(f"⚠️ User with username @{uname} not found.")
            return
        target_user_id = row[0]
    else:
        try:
            target_user_id = int(target)
        except Exception:
            await message.answer("❌ Invalid user identifier. Use numeric user_id or @username.")
            return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, wallet_inr, wallet_npr FROM users WHERE user_id = ?", (target_user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        await message.answer("⚠️ User not found in database.")
        return

    username, wallet_inr, wallet_npr = row[0], row[1] or 0, row[2] or 0
    await message.answer(f"👤 @{username} (ID: {target_user_id})\n\n💵 INR: {format_currency(wallet_inr, 'INR')}\n₨ NPR: {format_currency(wallet_npr, 'NPR')}")


# Register bot commands on startup so Telegram shows them automatically
from aiogram.types import BotCommand
from aiogram import Bot as AiogramBot


@router.startup()
async def set_bot_commands_on_startup():
    commands = [
        BotCommand(command="start", description="Show start menu"),
        BotCommand(command="menu", description="Open main menu"),
        BotCommand(command="help", description="Show help and commands"),
        BotCommand(command="profile", description="Show your profile"),
        BotCommand(command="wallet", description="Show wallet balances"),
        BotCommand(command="load", description="Load wallet funds"),
        BotCommand(command="history", description="Show recent transactions"),
        BotCommand(command="admin", description="Open admin panel (admins only)"),
        BotCommand(command="credit", description="Admin: add/set user wallet (admins only)"),
        BotCommand(command="balance", description="Admin: view user balances (admins only)"),
        BotCommand(command="restart", description="Admin: update and restart the bot (admins only)"),
    ]

    try:
        bot = AiogramBot(token=BOT_TOKEN)
        await bot.set_my_commands(commands)
    except Exception as e:
        print(f"Failed to set bot commands: {e}")
