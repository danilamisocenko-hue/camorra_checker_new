import sqlite3
import os

DB_NAME = 'users_wallets.db'

def init_db():
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                wallet_address TEXT NOT NULL,
                network TEXT NOT NULL,
                last_balance REAL DEFAULT 0,
                label TEXT DEFAULT 'Без метки'
            )
        ''')
        conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE NOT NULL, username TEXT, first_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        conn.commit()
        conn.close()

def add_user(user_id, username=None, first_name=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", (user_id, username, first_name))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result

def add_wallet(user_id, wallet_address, network, label='Без метки'):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO wallets (user_id, wallet_address, network, label) VALUES (?, ?, ?, ?)", 
                  (user_id, wallet_address, network, label))
    conn.commit()
    conn.close()

def get_user_wallets(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT wallet_address, network, last_balance, label FROM wallets WHERE user_id = ?", (user_id,))
    result = cursor.fetchall()
    conn.close()
    return result

def get_all_wallets():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, wallet_address, network, last_balance, label FROM wallets")
    result = cursor.fetchall()
    conn.close()
    return result

def update_balance(user_id, wallet_address, network, new_balance):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE wallets SET last_balance = ? WHERE user_id = ? AND wallet_address = ? AND network = ?", 
                  (new_balance, user_id, wallet_address, network))
    conn.commit()
    conn.close()

def delete_wallet(user_id, wallet_address, network):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wallets WHERE user_id = ? AND wallet_address = ? AND network = ?", 
                  (user_id, wallet_address, network))
    conn.commit()
    conn.close()
