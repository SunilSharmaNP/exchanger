from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

REJECT_REASONS = {
    "1": "Payment not received",
    "2": "Invalid / blurry screenshot",
    "3": "Transaction ID mismatch",
    "4": "Amount mismatch",
    "5": "Duplicate request",
    "6": "Custom reason…",
}


def get_start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💱 INR → NPR", callback_data="exchange_inr_to_npr"),
            InlineKeyboardButton(text="💱 NPR → INR", callback_data="exchange_npr_to_inr"),
        ],
        [
            InlineKeyboardButton(text="💰 Load Wallet", callback_data="load_wallet"),
            InlineKeyboardButton(text="💸 Withdraw",    callback_data="withdraw"),
        ],
        [
            InlineKeyboardButton(text="💼 My Wallet",    callback_data="wallet_balance"),
            InlineKeyboardButton(text="📊 Live Rates",   callback_data="check_rate"),
        ],
        [
            InlineKeyboardButton(text="📜 History",      callback_data="transaction_history"),
            InlineKeyboardButton(text="👤 Profile",      callback_data="profile"),
        ],
        [
            InlineKeyboardButton(text="📞 Support",      callback_data="support"),
            InlineKeyboardButton(text="ℹ️ How It Works", callback_data="how_it_works"),
        ],
    ])


def get_exchange_confirmation_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Confirm & Proceed", callback_data="confirm_exchange"),
        ],
        [
            InlineKeyboardButton(text="❌ Cancel",  callback_data="cancel_exchange"),
            InlineKeyboardButton(text="🔙 Back",    callback_data="back_to_start"),
        ],
    ])


def get_payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ I Have Paid", callback_data="payment_done"),
        ],
        [
            InlineKeyboardButton(text="❌ Cancel",      callback_data="cancel_payment"),
            InlineKeyboardButton(text="🔙 Back",        callback_data="back_to_start"),
        ],
    ])


def get_admin_approval_keyboard(request_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve",      callback_data=f"admin_approve_{request_id}"),
            InlineKeyboardButton(text="❌ Reject",       callback_data=f"admin_reject_{request_id}"),
        ],
        [
            InlineKeyboardButton(text="💬 Message User", callback_data=f"admin_message_{request_id}"),
            InlineKeyboardButton(text="🔙 Admin Panel",  callback_data="back_to_admin"),
        ],
    ])


def get_reject_reason_keyboard(request_id):
    rows = []
    for code, label in REJECT_REASONS.items():
        rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"rr_{request_id}_{code}",
        )])
    rows.append([InlineKeyboardButton(text="🔙 Back", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_admin_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Pending",      callback_data="admin_pending"),
            InlineKeyboardButton(text="✅ Completed",    callback_data="admin_completed"),
        ],
        [
            InlineKeyboardButton(text="📊 Statistics",   callback_data="admin_stats"),
            InlineKeyboardButton(text="⚙️ Settings",     callback_data="admin_settings"),
        ],
        [
            InlineKeyboardButton(text="💬 Support",      callback_data="admin_support"),
            InlineKeyboardButton(text="📋 Logs",         callback_data="admin_logs"),
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast",    callback_data="admin_broadcast"),
            InlineKeyboardButton(text="🔙 Main Menu",    callback_data="back_to_start"),
        ],
    ])


def get_settings_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💹 Exchange Rate",     callback_data="set_rate"),
            InlineKeyboardButton(text="💳 Payment Details",   callback_data="update_payment"),
        ],
        [
            InlineKeyboardButton(text="🔙 Admin Panel",       callback_data="back_to_admin"),
        ],
    ])


def get_load_wallet_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💵 Load INR", callback_data="load_inr"),
            InlineKeyboardButton(text="₨ Load NPR",  callback_data="load_npr"),
        ],
        [
            InlineKeyboardButton(text="🔙 Back",     callback_data="back_to_start"),
        ],
    ])


def get_back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_start")],
    ])


def get_cancel_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_start")],
    ])


# ── Support keyboards ──────────────────────────────────────────────────────────

def get_support_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Open Support Ticket", callback_data="support_new_ticket"),
        ],
        [
            InlineKeyboardButton(text="📋 My Tickets",          callback_data="support_my_tickets"),
            InlineKeyboardButton(text="❓ FAQ",                  callback_data="how_it_works"),
        ],
        [
            InlineKeyboardButton(text="🔙 Back",                callback_data="back_to_start"),
        ],
    ])


def get_user_support_reply_keyboard(ticket_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💬 Reply to Support",
                callback_data=f"support_reply_{ticket_id}",
            ),
        ],
        [
            InlineKeyboardButton(text="🔙 Main Menu", callback_data="back_to_start"),
        ],
    ])


def get_admin_support_keyboard(ticket_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💬 Reply",
                callback_data=f"admin_support_reply_{ticket_id}",
            ),
            InlineKeyboardButton(
                text="✅ Close Ticket",
                callback_data=f"admin_support_close_{ticket_id}",
            ),
        ],
        [
            InlineKeyboardButton(text="🔙 Admin Panel", callback_data="back_to_admin"),
        ],
    ])


def get_admin_support_panel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Refresh",     callback_data="admin_support"),
            InlineKeyboardButton(text="🔙 Admin Panel", callback_data="back_to_admin"),
        ],
    ])
