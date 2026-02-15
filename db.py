import sqlite3

def init_db():
    """
    Инициализирует базу данных для хранения кошельков пользователей.
    Создает таблицу wallets, если она не существует.
    Добавляет столбец label, если его нет (миграция для старых баз).
    """
    conn = sqlite3.connect('users_wallets.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            user_id INTEGER,
            wallet TEXT,
            network TEXT,
            last_balance REAL DEFAULT 0,
            label TEXT DEFAULT 'Без метки',
            PRIMARY KEY (user_id, wallet, network)
        )
    ''')
    # Миграция: добавить столбец label, если его нет (для старых баз)
    try:
        cursor.execute("ALTER TABLE wallets ADD COLUMN label TEXT DEFAULT 'Без метки'")
    except sqlite3.OperationalError:
        # Столбец уже существует, пропускаем
        pass
    conn.commit()
    conn.close()

def add_wallet(user_id, wallet, network, label='Без метки'):
    """
    Добавляет или обновляет кошелек для пользователя.
    user_id: ID пользователя в Telegram.
    wallet: Адрес кошелька.
    network: 'TRC20' или 'ERC20'.
    label: Метка для кошелька (по умолчанию 'Без метки').
    """
    conn = sqlite3.connect('users_wallets.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO wallets (user_id, wallet, network, last_balance, label) VALUES (?, ?, ?, 0, ?)', (user_id, wallet, network, label))
    conn.commit()
    conn.close()

def get_user_wallets(user_id):
    """
    Получает все кошельки пользователя.
    Возвращает список кортежей: (wallet, network, last_balance, label).
    """
    conn = sqlite3.connect('users_wallets.db')
    cursor = conn.cursor()
    cursor.execute('SELECT wallet, network, last_balance, label FROM wallets WHERE user_id = ?', (user_id,))
    wallets = cursor.fetchall()
    conn.close()
    return wallets

def update_balance(user_id, wallet, network, new_balance):
    """
    Обновляет баланс кошелька после проверки.
    """
    conn = sqlite3.connect('users_wallets.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE wallets SET last_balance = ? WHERE user_id = ? AND wallet = ? AND network = ?', (new_balance, user_id, wallet, network))
    conn.commit()
    conn.close()

def get_all_wallets():
    """
    Получает все кошельки для мониторинга (для фоновой задачи).
    Возвращает список кортежей: (user_id, wallet, network, last_balance, label).
    """
    conn = sqlite3.connect('users_wallets.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, wallet, network, last_balance, label FROM wallets')
    wallets = cursor.fetchall()
    conn.close()
    return wallets