"""
Regular ReplyKeyboardMarkup (Bottom Screen Keyboard) + Admin Inline Keyboards.
Persistent, easy-to-tap buttons right at the bottom of Telegram in 100% English.
"""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)

REJECT_REASONS = {
    "1": "❌ Payment not received in bank account",
    "2": "📸 Unclear or invalid screenshot",
    "3": "🔢 UTR / Transaction ID mismatch",
    "4": "💰 Sent amount differs from order amount",
    "5": "🔄 Duplicate request already submitted",
    "6": "✏️ Other custom reason...",
}

# ==========================================
# REGULAR REPLY KEYBOARDS (Bottom Screen)
# ==========================================

def get_start_reply_keyboard():
    """
    Regular ReplyKeyboardMarkup persistent at bottom of user's screen.
    Includes Help, About, Contact, Home and all exchange/wallet services.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🇮🇳 INR → 🇳🇵 NPR"),
                KeyboardButton(text="🇳🇵 NPR → 🇮🇳 INR"),
            ],
            [
                KeyboardButton(text="💼 My Wallet"),
                KeyboardButton(text="🔢 Rate Calculator"),
            ],
            [
                KeyboardButton(text="📊 Live Rates"),
                KeyboardButton(text="📜 History"),
            ],
            [
                KeyboardButton(text="📥 Deposit Funds"),
                KeyboardButton(text="💸 Withdraw"),
            ],
            [
                KeyboardButton(text="👤 Profile & Referrals"),
                KeyboardButton(text="🔍 Order Status"),
            ],
            [
                KeyboardButton(text="ℹ️ About Us"),
                KeyboardButton(text="❓ Help Guide"),
                KeyboardButton(text="📞 Contact Support"),
            ],
            [
                KeyboardButton(text="🏠 Home Menu"),
            ]
        ],
        resize_keyboard=True,
        persistent=True,
        input_field_placeholder="Select an option from the menu below..."
    )


def get_quick_amount_reply_keyboard(currency="INR"):
    """Regular buttons for fast amount selection."""
    symbol = "₹" if currency == "INR" else "₨"
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=f"{symbol}500"),
                KeyboardButton(text=f"{symbol}1,000"),
                KeyboardButton(text=f"{symbol}2,500"),
            ],
            [
                KeyboardButton(text=f"{symbol}5,000"),
                KeyboardButton(text=f"{symbol}10,000"),
                KeyboardButton(text=f"{symbol}25,000"),
            ],
            [
                KeyboardButton(text="🔙 Back to Home"),
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Choose amount or type directly..."
    )


def get_exchange_confirm_reply_keyboard():
    """Regular confirmation buttons."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Confirm & Proceed"),
            ],
            [
                KeyboardButton(text="🔄 Change Amount"),
                KeyboardButton(text="❌ Cancel Exchange"),
            ],
            [
                KeyboardButton(text="🔙 Back to Home"),
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_payment_reply_keyboard():
    """Regular buttons during payment phase."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ I Have Paid"),
            ],
            [
                KeyboardButton(text="❌ Cancel Payment"),
                KeyboardButton(text="🔙 Back to Home"),
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_load_currency_reply_keyboard():
    """Regular buttons to choose load currency."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🇮🇳 Deposit INR"),
                KeyboardButton(text="🇳🇵 Deposit NPR"),
            ],
            [
                KeyboardButton(text="🔙 Back to Home"),
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_cancel_reply_keyboard():
    """Regular cancel button."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔙 Back to Home")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# ==========================================
# ADMIN INLINE KEYBOARDS
# ==========================================

def get_admin_approval_keyboard(request_id):
    """Admin action keyboard attached to the order proof photo."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"admin_approve_{request_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"admin_reject_{request_id}"),
        ],
        [
            InlineKeyboardButton(text="💬 Message User", callback_data=f"admin_message_{request_id}"),
            InlineKeyboardButton(text="👤 User Profile", callback_data=f"admin_userinfo_{request_id}"),
        ],
        [
            InlineKeyboardButton(text="🔙 Admin Dashboard", callback_data="back_to_admin"),
        ]
    ])


def get_reject_reason_keyboard(request_id):
    """Structured reject reason inline keyboard."""
    rows = []
    for code, label in REJECT_REASONS.items():
        rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"rr_{request_id}_{code}",
        )])
    rows.append([InlineKeyboardButton(text="🔙 Cancel", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_admin_menu_keyboard():
    """Backoffice admin dashboard controls."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏳ Pending Orders", callback_data="admin_pending"),
            InlineKeyboardButton(text="✅ Completed Orders", callback_data="admin_completed"),
        ],
        [
            InlineKeyboardButton(text="📊 Stats & Analytics", callback_data="admin_stats"),
            InlineKeyboardButton(text="⚙️ Rates & Settings", callback_data="admin_settings"),
        ],
        [
            InlineKeyboardButton(text="💬 Support Tickets", callback_data="admin_support"),
            InlineKeyboardButton(text="🔍 Search Order/User", callback_data="admin_search"),
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="📋 Audit Logs", callback_data="admin_logs"),
        ],
        [
            InlineKeyboardButton(text="🔙 User Menu", callback_data="back_to_start"),
        ],
    ])


def get_admin_support_keyboard(ticket_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Reply", callback_data=f"admin_support_reply_{ticket_id}"),
            InlineKeyboardButton(text="✅ Close Ticket", callback_data=f"admin_support_close_{ticket_id}"),
        ],
        [
            InlineKeyboardButton(text="🔙 Admin Panel", callback_data="back_to_admin"),
        ],
    ])
