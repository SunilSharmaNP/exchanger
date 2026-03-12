import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database tables"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
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

    # Exchange requests table
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

    # Admin settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_settings (
            setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Transactions history table
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

    # Admin actions log
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

    # Initialize default settings
    cursor.execute('''
        INSERT OR IGNORE INTO admin_settings (setting_name, setting_value)
        VALUES (?, ?)
    ''', ('inr_to_npr_rate', '1.60'))

    cursor.execute('''
        INSERT OR IGNORE INTO admin_settings (setting_name, setting_value)
        VALUES (?, ?)
    ''', ('npr_to_inr_rate', '0.625'))

    cursor.execute('''
        INSERT OR IGNORE INTO admin_settings (setting_name, setting_value)
        VALUES (?, ?)
    ''', ('upi_id', 'business@upi'))

    cursor.execute('''
        INSERT OR IGNORE INTO admin_settings (setting_name, setting_value)
        VALUES (?, ?)
    ''', ('esewa_id', 'esewa_merchant@123'))

    # Referral bonus percent (default 1%)
    cursor.execute('''
        INSERT OR IGNORE INTO admin_settings (setting_name, setting_value)
        VALUES (?, ?)
    ''', ('referral_bonus_percent', '1.0'))

    # Ensure rates keys include suffix _rate for consistency
    cursor.execute("INSERT OR IGNORE INTO admin_settings (setting_name, setting_value) VALUES (?, ?)", ('inr_to_npr_rate', '1.60'))
    cursor.execute("INSERT OR IGNORE INTO admin_settings (setting_name, setting_value) VALUES (?, ?)", ('npr_to_inr_rate', '0.625'))

    conn.commit()
    conn.close()

    print("✅ Database initialized successfully!")


def execute_db(query, params=(), fetchone=False, fetchall=False, commit=False, retries=3):
    """Execute a database query with simple retry logic."""
    import sqlite3
    from time import sleep

    attempt = 0
    while attempt < retries:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = None
            # If caller asked to commit, do it. For INSERTs return lastrowid when no fetch requested.
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
        except sqlite3.OperationalError as e:
            attempt += 1
            sleep(0.2 * attempt)
            if attempt >= retries:
                raise
        except Exception:
            if conn:
                conn.close()
            raise

if __name__ == "__main__":
    init_database()
