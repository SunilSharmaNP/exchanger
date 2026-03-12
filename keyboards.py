from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

# Start Menu Keyboard
def get_start_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💱 INR → NPR", callback_data="exchange_inr_to_npr"),
            InlineKeyboardButton(text="💱 NPR → INR", callback_data="exchange_npr_to_inr")
        ],
        [
                InlineKeyboardButton(text="💰 Load Wallet", callback_data="load_wallet"),
                InlineKeyboardButton(text="💼 Wallet Balance", callback_data="wallet_balance"),
                InlineKeyboardButton(text="📊 Current Rate", callback_data="check_rate")
        ],
        [
            InlineKeyboardButton(text="📜 Transaction History", callback_data="transaction_history"),
            InlineKeyboardButton(text="ℹ️ How It Works", callback_data="how_it_works")
        ],
        [
            InlineKeyboardButton(text="📞 Support", callback_data="support"),
            InlineKeyboardButton(text="👤 Profile", callback_data="profile")
        ]
    ])
    return keyboard

# Exchange Confirmation Keyboard
def get_exchange_confirmation_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Confirm Exchange", callback_data="confirm_exchange"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_exchange")
        ]
    ])
    return keyboard

# Payment Keyboard
def get_payment_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 I Have Paid", callback_data="payment_done"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_payment")
        ]
    ])
    return keyboard

# Admin Approval Keyboard
def get_admin_approval_keyboard(request_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"admin_approve_{request_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"admin_reject_{request_id}")
        ],
        [
            InlineKeyboardButton(text="💬 Message User", callback_data=f"admin_message_{request_id}")
        ]
    ])
    return keyboard

# Admin Menu Keyboard
def get_admin_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Pending Requests", callback_data="admin_pending"),
            InlineKeyboardButton(text="✅ Completed", callback_data="admin_completed")
        ],
        [
            InlineKeyboardButton(text="📊 Statistics", callback_data="admin_stats"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="📋 Logs", callback_data="admin_logs")
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="back_to_start")
        ]
    ])
    return keyboard

# Settings Keyboard
def get_settings_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💹 Set Exchange Rate", callback_data="set_rate"),
            InlineKeyboardButton(text="💳 Update Payment Details", callback_data="update_payment")
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="back_to_admin")
        ]
    ])
    return keyboard

# Load Wallet Keyboard
def get_load_wallet_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💵 Load INR", callback_data="load_inr"),
            InlineKeyboardButton(text="₨ Load NPR", callback_data="load_npr")
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_start")
        ]
    ])
    return keyboard

# Back Button
def get_back_button():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_start")]
    ])
    return keyboard
