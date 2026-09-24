import sqlite3
import os
from datetime import datetime
from config import DATABASE_NAME


def get_db_connection():
    """Get SQLite database connection with WAL mode and high busy_timeout to eliminate locking."""
    conn = sqlite3.connect(DATABASE_NAME, timeout=30.0)
    # Enable Write-Ahead Logging (WAL) for concurrent reads and writes
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db():
    """Initialize database tables with optimal schemas and indexes."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_banned INTEGER DEFAULT 0,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_exchanges INTEGER DEFAULT 0,
            total_amount REAL DEFAULT 0.0,
            wallet_inr REAL DEFAULT 0.0,
            wallet_npr REAL DEFAULT 0.0,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            referral_bonus_given INTEGER DEFAULT 0,
            FOREIGN KEY (referred_by) REFERENCES users(user_id)
        )
    """)

    # Exchange Requests Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exchange_type TEXT NOT NULL,
            amount REAL NOT NULL,
            rate REAL NOT NULL,
            calculated_amount REAL NOT NULL,
            service_fee REAL DEFAULT 0.0,
            final_amount REAL NOT NULL,
            payment_proof TEXT,
            transaction_id TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            processed_by INTEGER,
            rejection_reason TEXT,
            payment_details TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Support Tickets Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'OPEN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            closed_by INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Support Messages Thread Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets(id)
        )
    """)

    # Wallet Transactions (Audit Trail)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            currency TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'COMPLETED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Admin Settings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            setting_name TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER
        )
    """)

    # Security Audit Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Speed Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_user ON exchange_requests(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_status ON exchange_requests(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_created ON exchange_requests(created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user ON support_tickets(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_referral ON users(referral_code);")

    # Default Settings
    default_settings = [
        ("inr_to_npr_rate", "1.60"),
        ("npr_to_inr_rate", "0.625"),
        ("upi_id", "merchant@okaxis"),
        ("esewa_id", "9801234567"),
        ("service_fee_percentage", "2.5"),
        ("referral_bonus_percentage", "1.0"),
    ]

    for name, value in default_settings:
        cursor.execute("""
            INSERT OR IGNORE INTO admin_settings (setting_name, setting_value)
            VALUES (?, ?)
        """, (name, value))

    conn.commit()
    conn.close()


def add_or_update_user(user_id, username, first_name, last_name, referral_code=None, referred_by=None):
    """Register or update a Telegram user."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, referral_code, referred_by)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name
    """, (user_id, username, first_name, last_name, referral_code, referred_by))

    conn.commit()
    conn.close()


def atomic_deduct_wallet(user_id: int, currency: str, amount: float) -> bool:
    """
    Atomically deduct from user wallet balance.
    Guarantees balance will not go negative. Returns True if deducted, False if insufficient balance.
    """
    if amount <= 0:
        return False
    column = "wallet_inr" if currency.upper() == "INR" else "wallet_npr"
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        UPDATE users
        SET {column} = round({column} - ?, 2)
        WHERE user_id = ? AND {column} >= ?
    """, (amount, user_id, amount))

    success = cursor.rowcount > 0
    if success:
        cursor.execute("""
            INSERT INTO wallet_transactions (user_id, type, currency, amount, status, details)
            VALUES (?, 'DEBIT', ?, ?, 'COMPLETED', 'Wallet exchange debit')
        """, (user_id, currency.upper(), amount))
        conn.commit()
    else:
        conn.rollback()

    conn.close()
    return success


def atomic_add_wallet(user_id: int, currency: str, amount: float, details: str = "Deposit") -> bool:
    """Atomically credit user wallet balance."""
    if amount <= 0:
        return False
    column = "wallet_inr" if currency.upper() == "INR" else "wallet_npr"
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        UPDATE users
        SET {column} = round({column} + ?, 2)
        WHERE user_id = ?
    """, (amount, user_id))

    cursor.execute("""
        INSERT INTO wallet_transactions (user_id, type, currency, amount, status, details)
        VALUES (?, 'CREDIT', ?, ?, 'COMPLETED', ?)
    """, (user_id, currency.upper(), amount, details))

    conn.commit()
    conn.close()
    return True


def get_user_by_referral_code(referral_code):
    """Find user ID associated with a referral code."""
    if not referral_code:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (referral_code.strip(),))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None


def get_referred_users_count(user_id):
    """Count how many users were referred by this user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def search_records(query: str):
    """Search for users or exchange requests by ID, username, or UTR."""
    clean_q = f"%{query.strip()}%"
    conn = get_db_connection()
    cursor = conn.cursor()

    # Search users
    cursor.execute("""
        SELECT user_id, username, first_name, total_exchanges, wallet_inr, wallet_npr
        FROM users
        WHERE CAST(user_id AS TEXT) LIKE ? OR username LIKE ? OR first_name LIKE ?
        LIMIT 5
    """, (clean_q, clean_q, clean_q))
    users = cursor.fetchall()

    # Search requests
    cursor.execute("""
        SELECT id, user_id, exchange_type, amount, final_amount, status, transaction_id, created_at
        FROM exchange_requests
        WHERE CAST(id AS TEXT) LIKE ? OR CAST(user_id AS TEXT) LIKE ? OR transaction_id LIKE ?
        ORDER BY id DESC LIMIT 5
    """, (clean_q, clean_q, clean_q))
    requests = cursor.fetchall()

    conn.close()
    return {"users": users, "requests": requests}
