import requests
import time
import logging

EXCHANGE_WALLETS = {
    'TRC20': [
        'T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuW9',  # Binance
        'TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE',  # Binance
        'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',  # USDT контракт
        'TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7',  # OKX
        'TWd4WrZ9wn84f5x1hZhL4DHvk738ns5jwb',  # Huobi
    ],
    'ERC20': [
        '0x28C6c06298d514Db089934071355E5743bf21d60',  # Coinbase
        '0x8894E0a0c962CB723c1976a4421c95949bE2D4E3',  # Coinbase
        '0xdAC17F958D2ee523a2206206994597C13D831ec7',  # USDT контракт
        '0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE',  # Binance
        '0xD551234Ae421e3BCBA99A0Da6d736074f22192FF',  # Binance
        '0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43',  # Kraken
    ]
}

def is_exchange_wallet(wallet, network):
    return wallet in EXCHANGE_WALLETS.get(network, [])

def get_usdt_balance_trc20(wallet_address, api_key):
    for attempt in range(2):
        try:
            url = f"https://api.trongrid.io/v1/accounts/{wallet_address}"
            headers = {"TRON-PRO-API-KEY": api_key}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                for token in data.get('data', [{}])[0].get('trc20', []):
                    if token.get('TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'):
                        balance = int(token['TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t']) / 10**6
                        return balance, f"{balance:.6f} USDT"
            return 0, "Ошибка: Не удалось получить баланс."
        except Exception as e:
            logging.warning(f"Попытка {attempt + 1} для TRC20 баланса: {e}")
            if attempt < 1:
                time.sleep(1)
    return 0, "Ошибка: Таймаут или проблема с API. Попробуйте позже."

def get_usdt_balance_erc20(wallet_address, api_key):
    for attempt in range(2):
        try:
            url = f"https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress=0xdAC17F958D2ee523a2206206994597C13D831ec7&address={wallet_address}&tag=latest&apikey={api_key}"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    balance = int(data['result']) / 10**6
                    return balance, f"{balance:.6f} USDT"
            return 0, "Ошибка: Не удалось получить баланс."
        except Exception as e:
            logging.warning(f"Попытка {attempt + 1} для ERC20 баланса: {e}")
            if attempt < 1:
                time.sleep(1)
    return 0, "Ошибка: Таймаут или проблема с API. Попробуйте позже."

def get_usdt_transactions_trc20(wallet_address, api_key, full_history=False):
    since = 0 if full_history else int(time.time() * 1000) - 24 * 60 * 60 * 1000
    for attempt in range(2):
        try:
            url = f"https://api.trongrid.io/v1/accounts/{wallet_address}/transactions/trc20?limit=200&min_block_timestamp={since}"
            headers = {"TRON-PRO-API-KEY": api_key}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                incoming = 0
                outgoing = 0
                total_volume = 0
                count = 0
                exchange_related = False
                for tx in data.get('data', []):
                    if tx.get('token_info', {}).get('address') == 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t':
                        if tx.get('to') == wallet_address:
                            incoming += 1
                        elif tx.get('from') == wallet_address:
                            outgoing += 1
                        volume = int(tx.get('value', 0)) / 10**6
                        total_volume += volume
                        count += 1
                        if tx.get('from') in EXCHANGE_WALLETS.get('TRC20', []) or tx.get('to') in EXCHANGE_WALLETS.get('TRC20', []):
                            exchange_related = True
                avg_volume = total_volume / count if count > 0 else 0
                return incoming, outgoing, avg_volume, exchange_related
            return 0, 0, 0, False
        except Exception as e:
            logging.warning(f"Попытка {attempt + 1} для TRC20 транзакций: {e}")
            if attempt < 1:
                time.sleep(1)
    return 0, 0, 0, False

def get_usdt_transactions_erc20(wallet_address, api_key, full_history=False):
    for attempt in range(2):
        try:
            url = f"https://api.etherscan.io/api?module=account&action=tokentx&contractaddress=0xdAC17F958D2ee523a2206206994597C13D831ec7&address={wallet_address}&startblock=0&endblock=99999999&sort=asc&apikey={api_key}"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                now = int(time.time())
                incoming = 0
                outgoing = 0
                total_volume = 0
                count = 0
                exchange_related = False
                for tx in data.get('result', []):
                    is_recent = now - int(tx.get('timeStamp', 0)) <= 24 * 60 * 60
                    if full_history or is_recent:
                        if tx.get('to').lower() == wallet_address.lower():
                            incoming += 1
                        elif tx.get('from').lower() == wallet_address.lower():
                            outgoing += 1
                        volume = int(tx.get('value', 0)) / 10**6
                        total_volume += volume
                        count += 1
                        if tx.get('from').lower() in [addr.lower() for addr in EXCHANGE_WALLETS.get('ERC20', [])] or tx.get('to').lower() in [addr.lower() for addr in EXCHANGE_WALLETS.get('ERC20', [])]:
                            exchange_related = True
                avg_volume = total_volume / count if count > 0 else 0
                return incoming, outgoing, avg_volume, exchange_related
            return 0, 0, 0, False
        except Exception as e:
            logging.warning(f"Попытка {attempt + 1} для ERC20 транзакций: {e}")
            if attempt < 1:
                time.sleep(1)
    return 0, 0, 0, False

def get_wallet_analytics(wallet_address, network, api_key, label='Без метки'):
    if network == 'TRC20':
        balance_num, balance_str = get_usdt_balance_trc20(wallet_address, api_key)
        incoming, outgoing, avg_volume, _ = get_usdt_transactions_trc20(wallet_address, api_key, full_history=False)  # 24 ч
        _, _, _, exchange_related = get_usdt_transactions_trc20(wallet_address, api_key, full_history=True)  # Вся история для биржи
    else:
        balance_num, balance_str = get_usdt_balance_erc20(wallet_address, api_key)
        incoming, outgoing, avg_volume, _ = get_usdt_transactions_erc20(wallet_address, api_key, full_history=False)  # 24 ч
        _, _, _, exchange_related = get_usdt_transactions_erc20(wallet_address, api_key, full_history=True)  # Вся история для биржи
    
    if "Ошибка" in balance_str:
        return {
            'balance': balance_str,
            'incoming_24h': 0,
            'outgoing_24h': 0,
            'estimated_balance': "Не удалось рассчитать",
            'exchange': "Не удалось определить",
            'label': label
        }
    
    exchange_status = "Возможно биржевой (на основе адреса или истории транзакций)" if is_exchange_wallet(wallet_address, network) or exchange_related else "Не биржевой"
    if incoming > 10 and outgoing > 10:
        exchange_status = "Возможно биржа (высокий объем транзакций)"
    
    estimated_balance_num = balance_num + (incoming - outgoing) * avg_volume
    estimated_balance = f"{estimated_balance_num:.6f} USDT (прогноз на основе активности)"
    
    return {
        'balance': balance_str,
        'incoming_24h': incoming,
        'outgoing_24h': outgoing,
        'estimated_balance': estimated_balance,
        'exchange': exchange_status,
        'label': label
    }
