import sqlite3
import os
from contextlib import contextmanager
from typing import List, Tuple, Optional
import threading

DB_NAME = 'users_wallets.db'

# Блокировка для потокобезопасности
_db_lock = threading.Lock()


def init_db():
    """Инициализация базы данных с созданием таблиц и индексов"""
    with _db_lock:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Создание таблицы users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создание таблицы wallets
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                wallet_address TEXT NOT NULL,
                network TEXT NOT NULL,
                last_balance REAL DEFAULT 0,
                label TEXT DEFAULT 'Без метки',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, wallet_address, network)
            )
        ''')
        
        # Создание индексов для ускорения запросов
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_wallets_user_id ON wallets(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_wallets_network ON wallets(network)',
            'CREATE INDEX IF NOT EXISTS idx_wallets_balance ON wallets(last_balance)',
            'CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)'
        ]
        
        for index in indexes:
            try:
                cursor.execute(index)
            except sqlite3.OperationalError:
                pass  # Индекс уже существует
        
        conn.commit()
        conn.close()


@contextmanager
def get_connection():
    """Контекстный менеджер для безопасного соединения с БД"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Позволяет обращаться к полям по имени
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
    """Добавление нового пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )


def get_all_users() -> List[int]:
    """Получение всех user_id пользователей"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        return [row[0] for row in cursor.fetchall()]


def add_wallet(user_id: int, wallet_address: str, network: str, label: str = 'Без метки'):
    """Добавление кошелька на мониторинг"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO wallets (user_id, wallet_address, network, label) VALUES (?, ?, ?, ?)",
            (user_id, wallet_address, network, label)
        )


def get_user_wallets(user_id: int) -> List[Tuple[str, str, float, str]]:
    """Получение всех кошельков пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT wallet_address, network, last_balance, label FROM wallets WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchall()


def get_all_wallets() -> List[Tuple[int, str, str, float, str]]:
    """Получение всех кошельков для мониторинга"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, wallet_address, network, last_balance, label FROM wallets")
        return cursor.fetchall()


def update_balance(user_id: int, wallet_address: str, network: str, new_balance: float):
    """Обновление баланса кошелька"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE wallets SET last_balance = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND wallet_address = ? AND network = ?",
            (new_balance, user_id, wallet_address, network)
        )


def delete_wallet(user_id: int, wallet_address: str, network: str):
    """Удаление кошелька из мониторинга"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM wallets WHERE user_id = ? AND wallet_address = ? AND network = ?",
            (user_id, wallet_address, network)
        )


def delete_wallet_by_number(user_id: int, wallet_number: int) -> Optional[Tuple[str, str, str]]:
    """Удаление кошелька по номеру (для пользователя)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Получаем кошелек по номеру (ORDER BY для стабильной нумерации)
        cursor.execute(
            "SELECT wallet_address, network, label FROM wallets WHERE user_id = ? ORDER BY id",
            (user_id,)
        )
        wallets = cursor.fetchall()
        
        if wallet_number < 1 or wallet_number > len(wallets):
            return None
        
        wallet = wallets[wallet_number - 1]
        wallet_address, network, label = wallet
        
        # Удаляем кошелёк
        cursor.execute(
            "DELETE FROM wallets WHERE user_id = ? AND wallet_address = ? AND network = ?",
            (user_id, wallet_address, network)
        )
        
        return (wallet_address, network, label)


def get_wallet_count(user_id: int) -> int:
    """Получение количества кошельков пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM wallets WHERE user_id = ?", (user_id,))
        return cursor.fetchone()[0]


def search_wallets(user_id: int, query: str) -> List[Tuple[str, str, float, str]]:
    """Поиск кошельков по адресу или метке"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT wallet_address, network, last_balance, label FROM wallets 
               WHERE user_id = ? AND (wallet_address LIKE ? OR label LIKE ?)""",
            (user_id, f'%{query}%', f'%{query}%')
        )
        return cursor.fetchall()


def get_wallet_info(user_id: int, wallet_address: str, network: str) -> Optional[Tuple[float, str]]:
    """Получение информации о конкретном кошельке"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT last_balance, label FROM wallets WHERE user_id = ? AND wallet_address = ? AND network = ?",
            (user_id, wallet_address, network)
        )
        result = cursor.fetchone()
        return result if result else None


def update_wallet_label(user_id: int, wallet_address: str, network: str, new_label: str):
    """Обновление метки кошелька"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE wallets SET label = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND wallet_address = ? AND network = ?",
            (new_label, user_id, wallet_address, network)
        )


def get_high_balance_wallets(threshold: float = 1500) -> List[Tuple[int, str, str, float, str]]:
    """Получение кошельков с балансом выше порога (для мониторинга)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, wallet_address, network, last_balance, label FROM wallets WHERE last_balance >= ?",
            (threshold,)
        )
        return cursor.fetchall()


def cleanup_old_records(days: int = 30):
    """Очистка старых записей (опционально)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM wallets WHERE updated_at < datetime('now', '-{} days')".format(days)
        )
        deleted = cursor.rowcount
        return deleted
    conn.close()

