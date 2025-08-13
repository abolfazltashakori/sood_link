import sqlite3
from datetime import datetime

import logging
DB_FILE = '1database.db'
logger = logging.getLogger(__name__)


def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('''
                        CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER,
                        first_name TEXT DEFAULT "",
                        last_name TEXT DEFAULT "",
                        username TEXT DEFAULT "",
                        balance INTEGER DEFAULT 0,
                        phone_number TEXT DEFAULT "",
                        ban BOOLEAN DEFAULT FALSE,
                        join_date TEXT DEFAULT "",
                        have_subscription BOOLEAN DEFAULT FALSE,
                        file_buy INTEGER DEFAULT 0,
                        file_free INTEGER DEFAULT 2147483648
        );
        ''')
        cur.execute('''
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(telegram_id)
        );
        ''')



        conn.commit()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    finally:
        conn.close()
init_db()

def create_user_if_not_exists(telegram_id, first_name, last_name, username, balance=0, join_date=None):
    try:
        join_date = join_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('''INSERT OR IGNORE INTO users(
                telegram_id, first_name, last_name, username, balance, join_date, file_free) 
                VALUES (?,?,?,?,?,?,?)''',  # افزودن file_free
                    (telegram_id, first_name, last_name, username, balance, join_date, 2147483648))
        conn.commit()
    except Exception as e:
        logger.error(f"Error creating user: {e}")

def used_test_service(telegram_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('SELECT file_free FROM users WHERE telegram_id = ?', (telegram_id,))
        result = cur.fetchone()
        return result[0] > 0 if result else False
    except Exception as e:
        logger.error(f"Error checking test service: {e}")
        return False

def incraise_balance(telegram_id,balance):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('SELECT balance FROM users WHERE telegram_id = ?', (telegram_id,))
        result = cur.fetchone()
        new_balance = result[0] + balance
        cur.execute('UPDATE users SET balance = ? WHERE telegram_id = ?', (new_balance, telegram_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating user: {e}")


def decraise_balance(telegram_id, balance):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('SELECT balance FROM users WHERE telegram_id = ?', (telegram_id,))
        result = cur.fetchone()

        if not result:
            logger.error(f"User {telegram_id} not found")
            return False

        current_balance = result[0]
        new_balance = current_balance - balance

        if new_balance < 0:
            return False
        cur.execute('UPDATE users SET balance = ? WHERE telegram_id = ?', (new_balance, telegram_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return False
    finally:
        conn.close()

def return_balance(telegram_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('SELECT balance FROM users WHERE telegram_id = ?', (telegram_id,))
        result = cur.fetchone()
        return result[0]
    except Exception as e:
        logger.error(f"Error updating user: {e}")


def return_traffic(telegram_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT file_free, file_buy FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cur.fetchone()
        conn.close()
        if not user:
            return 0

        file_free = user['file_free']
        file_buy = user['file_buy']

        return file_buy if file_buy > 0 else file_free
    except Exception as e:
        logger.error(f"Error in return_traffic: {e}")
        return 0


def decrease_traffic(telegram_id, traffic_size):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('SELECT file_free, file_buy FROM users WHERE telegram_id = ?', (telegram_id,))
        result = cur.fetchone()
        if not result:
            return False
        file_free, file_buy = result
        total_traffic = file_free + file_buy

        if total_traffic < traffic_size:
            return False

        if file_buy >= traffic_size:
            new_file_buy = file_buy - traffic_size
            cur.execute('UPDATE users SET file_buy = ? WHERE telegram_id = ?', (new_file_buy, telegram_id))
        else:

            remaining = traffic_size - file_buy
            new_file_buy = 0
            new_file_free = file_free - remaining
            cur.execute('''
                UPDATE users 
                SET file_buy = ?, file_free = ? 
                WHERE telegram_id = ?
            ''', (new_file_buy, new_file_free, telegram_id))

        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error decreasing traffic: {e}")
        return False
    finally:
        conn.close()
