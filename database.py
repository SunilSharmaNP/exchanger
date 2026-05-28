import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_exchanges INTEGER DEFAULT 0,
            total_amount REAL DEFAULT 0,
            wallet_inr REAL DEFAULT 0,
            wallet_npr REAL DEFAULT 0,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            is_banned INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchange_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            exchange_type TEXT NOT NULL,
            amount REAL NOT NULL,
            exchange_rate REAL NOT NULL,
            calculated_amount REAL NOT NULL,
            service_fee REAL NOT NULL,
            final_amount REAL NOT NULL,
            upi_id_used TEXT,
            esewa_id_used TEXT,
            status TEXT DEFAULT 'pending',
            payment_screenshot TEXT,
            transaction_id TEXT,
            admin_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_settings (
            setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exchange_request_id INTEGER,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(exchange_request_id) REFERENCES exchange_requests(request_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            request_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Support ticket system ──────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            status TEXT DEFAULT 'open',
            subject TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            sender_id INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(ticket_id) REFERENCES support_tickets(ticket_id)
        )
    ''')

    # Default settings
    defaults = [
        ('inr_to_npr_rate', '1.60'),
        ('npr_to_inr_rate', '0.625'),
        ('upi_id', 'business@upi'),
        ('esewa_id', 'esewa_merchant@123'),
        ('referral_bonus_percent', '1.0'),
    ]
    for name, value in defaults:
        cursor.execute(
            'INSERT OR IGNORE INTO admin_settings (setting_name, setting_value) VALUES (?, ?)',
            (name, value)
        )

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")


def execute_db(query, params=(), fetchone=False, fetchall=False, commit=False, retries=3):
    """Execute a database query with simple retry logic."""
    from time import sleep

    conn = None
    attempt = 0
    while attempt < retries:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = None
            if commit:
                conn.commit()
                if not fetchone and not fetchall:
                    result = cursor.lastrowid
            if fetchone:
                result = cursor.fetchone()
            elif fetchall:
                result = cursor.fetchall()
            cursor.close()
            conn.close()
            return result
        except sqlite3.OperationalError:
            attempt += 1
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            conn = None
            sleep(0.2 * attempt)
            if attempt >= retries:
                raise
        except Exception:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            raise


def get_bot_stats():
    """Return a dict with today's stats for admin panel."""
    conn = get_db_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE date(joined_date) = ?", (today,))
    new_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(DISTINCT user_id) FROM exchange_requests WHERE date(created_at) = ?", (today,)
    )
    active_today = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM exchange_requests")
    total_transactions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM exchange_requests WHERE status = 'completed'")
    completed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM exchange_requests WHERE status = 'pending'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM exchange_requests WHERE status = 'rejected'")
    rejected = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM exchange_requests WHERE status = 'completed'")
    total_inr = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(final_amount), 0) FROM exchange_requests WHERE status = 'completed'")
    total_npr = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(service_fee), 0) FROM exchange_requests WHERE status = 'completed'")
    total_fees = cursor.fetchone()[0]

    cursor.execute("SELECT setting_value FROM admin_settings WHERE setting_name = 'inr_to_npr_rate'")
    row = cursor.fetchone()
    inr_to_npr = row[0] if row else "N/A"

    cursor.execute("SELECT setting_value FROM admin_settings WHERE setting_name = 'npr_to_inr_rate'")
    row = cursor.fetchone()
    npr_to_inr = row[0] if row else "N/A"

    cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'")
    open_tickets = cursor.fetchone()[0]

    conn.close()

    return {
        "total_users": total_users,
        "new_users": new_users,
        "active_today": active_today,
        "total_transactions": total_transactions,
        "completed": completed,
        "pending": pending,
        "rejected": rejected,
        "total_inr": total_inr,
        "total_npr": total_npr,
        "total_fees": total_fees,
        "inr_to_npr": inr_to_npr,
        "npr_to_inr": npr_to_inr,
        "open_tickets": open_tickets,
    }


if __name__ == "__main__":
    init_database()
