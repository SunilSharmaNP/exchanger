import re
from datetime import datetime, timedelta
from database import get_db_connection
from config import MIN_EXCHANGE_AMOUNT, MAX_EXCHANGE_AMOUNT, SERVICE_FEE_PERCENTAGE, ANTI_SPAM_LIMIT, ANTI_SPAM_WINDOW


def validate_amount(amount_str):
    """Validate exchange amount"""
    try:
        amount = float(amount_str.strip().replace(",", ""))
        if amount < MIN_EXCHANGE_AMOUNT:
            return False, f"Amount is too low! Minimum is {MIN_EXCHANGE_AMOUNT}"
        if amount > MAX_EXCHANGE_AMOUNT:
            return False, f"Amount is too high! Maximum is {MAX_EXCHANGE_AMOUNT:,}"
        return True, amount
    except (ValueError, AttributeError):
        return False, "Please enter a valid number"


def validate_transaction_id(txn_id):
    """Validate transaction ID format"""
    if not txn_id or len(txn_id) < 5 or len(txn_id) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9\-_/]+$', txn_id))


def calculate_exchange(amount, rate, apply_fee=True):
    """Calculate exchange amount with fee"""
    calculated = amount * rate
    if apply_fee:
        fee = calculated * (SERVICE_FEE_PERCENTAGE / 100)
        final = calculated - fee
        return calculated, fee, final
    return calculated, 0, calculated


def get_exchange_rate(exchange_type):
    """Get current exchange rate from database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if exchange_type == "INR_TO_NPR":
        rate_name = "inr_to_npr_rate"
    elif exchange_type == "NPR_TO_INR":
        rate_name = "npr_to_inr_rate"
    else:
        conn.close()
        return None

    cursor.execute("SELECT setting_value FROM admin_settings WHERE setting_name = ?", (rate_name,))
    result = cursor.fetchone()
    conn.close()

    return float(result[0]) if result else None


def get_payment_details():
    """Get current payment details from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT setting_name, setting_value FROM admin_settings
        WHERE setting_name IN ('upi_id', 'esewa_id')
    """)
    settings = cursor.fetchall()
    conn.close()

    details = {}
    for setting in settings:
        details[setting[0]] = setting[1]

    return details.get("upi_id", ""), details.get("esewa_id", "")


def check_anti_spam(user_id):
    """Check if user is making too many requests. Returns (can_exchange, wait_minutes)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    time_limit = datetime.now() - timedelta(seconds=ANTI_SPAM_WINDOW)
    cursor.execute("""
        SELECT COUNT(*) FROM exchange_requests
        WHERE user_id = ? AND created_at > ?
    """, (user_id, time_limit))

    count = cursor.fetchone()[0]
    conn.close()

    if count >= ANTI_SPAM_LIMIT:
        # Estimate remaining wait in minutes (window / limit as rough spacing, at least 1 min)
        wait_minutes = max(1, int(ANTI_SPAM_WINDOW / 60 / ANTI_SPAM_LIMIT))
        return False, wait_minutes

    return True, 0


def is_user_banned(user_id):
    """Check if user is banned"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return bool(result and result[0] == 1)


def format_currency(amount, currency):
    """Format currency display"""
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if currency == "INR":
        return f"₹{amount:,.2f}"
    elif currency == "NPR":
        return f"₨{amount:,.2f}"
    return f"{amount:,.2f} {currency}"


def format_timestamp(ts):
    """Format timestamp to readable format. Handles None gracefully."""
    if ts is None:
        return "N/A"
    try:
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        return ts.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(ts)


def get_exchange_type_display(exchange_type):
    """Get human-readable exchange type"""
    types = {
        "INR_TO_NPR": "INR → NPR",
        "NPR_TO_INR": "NPR → INR",
        "LOAD_INR": "Load INR",
        "LOAD_NPR": "Load NPR",
        "WITHDRAW_INR": "Withdraw INR",
        "WITHDRAW_NPR": "Withdraw NPR",
    }
    return types.get(exchange_type, exchange_type)


def get_exchange_currencies(exchange_type):
    """Return (from_currency, to_currency) for a given exchange type."""
    mapping = {
        "INR_TO_NPR": ("INR", "NPR"),
        "NPR_TO_INR": ("NPR", "INR"),
        "LOAD_INR": ("INR", "INR"),
        "LOAD_NPR": ("NPR", "NPR"),
        "WITHDRAW_INR": ("INR", "INR"),
        "WITHDRAW_NPR": ("NPR", "NPR"),
    }
    return mapping.get(exchange_type, ("INR", "NPR"))


def generate_referral_code(user_id):
    """Generate unique referral code"""
    import hashlib
    code = hashlib.md5(f"{user_id}{datetime.now()}".encode()).hexdigest()[:8].upper()
    return code


def validate_user_exists(user_id):
    """Check if user exists in database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def mask_upi_id(upi_id):
    """Mask UPI ID for privacy"""
    parts = upi_id.split("@")
    if len(parts) == 2:
        user_part = parts[0]
        domain = parts[1]
        if len(user_part) > 4:
            user_part = user_part[:2] + "***" + user_part[-2:]
        return f"{user_part}@{domain}"
    return upi_id[:5] + "***"


def mask_transaction_id(txn_id):
    """Mask transaction ID for privacy"""
    if len(txn_id) > 8:
        return txn_id[:4] + "***" + txn_id[-4:]
    return txn_id


def get_user_info(user_id):
    """Get user information from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, first_name, last_name, joined_date,
               total_exchanges, total_amount, wallet_inr, wallet_npr, referral_code
        FROM users WHERE user_id = ?
    """, (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            "user_id": result[0],
            "username": result[1],
            "first_name": result[2],
            "last_name": result[3],
            "joined_date": result[4],
            "total_exchanges": result[5],
            "total_amount": result[6],
            "wallet_inr": result[7],
            "wallet_npr": result[8],
            "referral_code": result[9],
        }
    return None
