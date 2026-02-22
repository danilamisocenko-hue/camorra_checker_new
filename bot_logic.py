import requests
import time
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

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


@dataclass
class BalanceResult:
    """Результат проверки баланса"""
    success: bool
    balance: float
    message: str
    error_type: Optional[str] = None  # 'invalid_wallet', 'zero_balance', 'api_error', 'network_error'


def is_exchange_wallet(wallet, network):
    return wallet in EXCHANGE_WALLETS.get(network, [])


def validate_trc20_address(wallet: str) -> Tuple[bool, str]:
    """Валидация TRC20 адреса"""
    if not wallet:
        return False, "Пустой адрес кошелька"
    
    if not wallet.startswith('T'):
        return False, "Адрес должен начинаться с 'T'"
    
    if len(wallet) < 34:
        return False, "Слишком короткий адрес (минимум 34 символа)"
    
    if len(wallet) > 44:
        return False, "Слишком длинный адрес (максимум 44 символа)"
    
    return True, "OK"


def validate_erc20_address(wallet: str) -> Tuple[bool, str]:
    """Валидация ERC20 адреса"""
    if not wallet:
        return False, "Пустой адрес кошелька"
    
    if not wallet.startswith('0x'):
        return False, "Адрес должен начинаться с '0x'"
    
    if len(wallet) != 42:
        return False, f"Неверная длина адреса (ожидалось 42 символа, получено {len(wallet)})"
    
    # Проверка что это hex
    try:
        int(wallet[2:], 16)
    except ValueError:
        return False, "Адрес содержит недопустимые символы"
    
    return True, "OK"


def get_usdt_balance_trc20(wallet_address, api_key) -> BalanceResult:
    """Получение баланса USDT TRC20"""
    # Валидация адреса
    valid, error_msg = validate_trc20_address(wallet_address)
    if not valid:
        return BalanceResult(
            success=False,
            balance=0,
            message=f"❌ *Невалидный TRC20 кошелёк*\n\n{error_msg}",
            error_type='invalid_wallet'
        )
    
    for attempt in range(2):
        try:
            url = f"https://api.trongrid.io/v1/accounts/{wallet_address}"
            headers = {"TRON-PRO-API-KEY": api_key}
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 429:
                return BalanceResult(
                    success=False,
                    balance=0,
                    message="⚠️ *Превышен лимит запросов*\n\nПопробуйте через несколько секунд",
                    error_type='api_error'
                )
            
            if response.status_code != 200:
                return BalanceResult(
                    success=False,
                    balance=0,
                    message=f"⚠️ *Ошибка API TRON*\n\nКод ошибки: {response.status_code}",
                    error_type='api_error'
                )
            
            data = response.json()
            
            # Проверяем структуру ответа
            if 'data' not in data or not data['data']:
                return BalanceResult(
                    success=False,
                    balance=0,
                    message="❌ *Кошелёк не найден*\n\nПроверьте адрес и попробуйте снова",
                    error_type='invalid_wallet'
                )
            
            trc20_data = data['data'][0].get('trc20', [])
            
            if not trc20_data:
                return BalanceResult(
                    success=True,
                    balance=0,
                    message="💰 *Баланс: 0 USDT*\n\nНа кошельке нет USDT TRC20",
                    error_type='zero_balance'
                )
            
            # Ищем USDT контракт
            usdt_token = None
            for token in trc20_data:
                if 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t' in token:
                    usdt_token = token['TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t']
                    break
            
            if not usdt_token:
                return BalanceResult(
                    success=True,
                    balance=0,
                    message="💰 *Баланс: 0 USDT*\n\nНа кошельке нет USDT TRC20",
                    error_type='zero_balance'
                )
            
            balance = int(usdt_token) / 10**6
            
            if balance == 0:
                return BalanceResult(
                    success=True,
                    balance=0,
                    message="💰 *Баланс: 0 USDT*\n\nНа кошельке нет средств",
                    error_type='zero_balance'
                )
            
            return BalanceResult(
                success=True,
                balance=balance,
                message=f"💰 *Баланс: {balance:.6f} USDT*",
                error_type=None
            )
        
        except requests.exceptions.Timeout:
            if attempt < 1:
                time.sleep(1)
                continue
            return BalanceResult(
                success=False,
                balance=0,
                message="⏱️ *Таймаут соединения*\n\nПревышено время ожидания ответа от API TRON",
                error_type='network_error'
            )
        
        except requests.exceptions.ConnectionError:
            return BalanceResult(
                success=False,
                balance=0,
                message="🌐 *Ошибка соединения*\n\nНе удалось подключиться к API TRON",
                error_type='network_error'
            )
        
        except Exception as e:
            logging.error(f"Неизвестная ошибка TRC20: {e}")
            if attempt < 1:
                time.sleep(1)
                continue
            return BalanceResult(
                success=False,
                balance=0,
                message=f"❌ *Произошла ошибка*\n\n{str(e)}",
                error_type='api_error'
            )
    
    return BalanceResult(
        success=False,
        balance=0,
        message="❌ *Не удалось получить баланс*\n\nПопробуйте позже",
        error_type='api_error'
    )


def get_usdt_balance_erc20(wallet_address, api_key) -> BalanceResult:
    """Получение баланса USDT ERC20"""
    # Валидация адреса
    valid, error_msg = validate_erc20_address(wallet_address)
    if not valid:
        return BalanceResult(
            success=False,
            balance=0,
            message=f"❌ *Невалидный ERC20 кошелёк*\n\n{error_msg}",
            error_type='invalid_wallet'
        )
    
    for attempt in range(2):
        try:
            url = (
                f"https://api.etherscan.io/api"
                f"?module=account&action=tokenbalance"
                f"&contractaddress=0xdAC17F958D2ee523a2206206994597C13D831ec7"
                f"&address={wallet_address}&tag=latest&apikey={api_key}"
            )
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                return BalanceResult(
                    success=False,
                    balance=0,
                    message=f"⚠️ *Ошибка API Etherscan*\n\nКод ошибки: {response.status_code}",
                    error_type='api_error'
                )
            
            data = response.json()
            
            # Проверяем статус ответа API
            if data.get('status') == '0':
                if data.get('message') == 'OK':
                    return BalanceResult(
                        success=True,
                        balance=0,
                        message="💰 *Баланс: 0 USDT*\n\nНа кошельке нет USDT ERC20",
                        error_type='zero_balance'
                    )
                error_msg = data.get('message', 'Unknown error')
                return BalanceResult(
                    success=False,
                    balance=0,
                    message=f"⚠️ *Ошибка Etherscan*\n\n{error_msg}",
                    error_type='api_error'
                )
            
            balance = int(data['result']) / 10**6
            
            if balance == 0:
                return BalanceResult(
                    success=True,
                    balance=0,
                    message="💰 *Баланс: 0 USDT*\n\nНа кошельке нет средств",
                    error_type='zero_balance'
                )
            
            return BalanceResult(
                success=True,
                balance=balance,
                message=f"💰 *Баланс: {balance:.6f} USDT*",
                error_type=None
            )
        
        except requests.exceptions.Timeout:
            if attempt < 1:
                time.sleep(1)
                continue
            return BalanceResult(
                success=False,
                balance=0,
                message="⏱️ *Таймаут соединения*\n\nПревышено время ожидания ответа от API Etherscan",
                error_type='network_error'
            )
        
        except requests.exceptions.ConnectionError:
            return BalanceResult(
                success=False,
                balance=0,
                message="🌐 *Ошибка соединения*\n\nНе удалось подключиться к API Etherscan",
                error_type='network_error'
            )
        
        except KeyError:
            return BalanceResult(
                success=False,
                balance=0,
                message="❌ *Невалидный ответ от API*\n\nПолучены некорректные данные",
                error_type='api_error'
            )
        
        except Exception as e:
            logging.error(f"Неизвестная ошибка ERC20: {e}")
            if attempt < 1:
                time.sleep(1)
                continue
            return BalanceResult(
                success=False,
                balance=0,
                message=f"❌ *Произошла ошибка*\n\n{str(e)}",
                error_type='api_error'
            )
    
    return BalanceResult(
        success=False,
        balance=0,
        message="❌ *Не удалось получить баланс*\n\nПопробуйте позже",
        error_type='api_error'
    )


def get_usdt_transactions_trc20(wallet_address, api_key, full_history=False):
    """Получение транзакций TRC20"""
    since = 0 if full_history else int(time.time() * 1000) - 24 * 60 * 60 * 1000
    
    for attempt in range(2):
        try:
            url = (
                f"https://api.trongrid.io/v1/accounts/{wallet_address}/transactions/trc20"
                f"?limit=200&min_block_timestamp={since}"
            )
            headers = {"TRON-PRO-API-KEY": api_key}
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                return 0, 0, 0, False
            
            data = response.json()
            incoming = 0
            outgoing = 0
            total_volume = 0
            count = 0
            exchange_related = False
            
            for tx in data.get('data', []):
                if tx.get('token_info', {}).get('address') != 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t':
                    continue
                
                if tx.get('to') == wallet_address:
                    incoming += 1
                elif tx.get('from') == wallet_address:
                    outgoing += 1
                
                volume = int(tx.get('value', 0)) / 10**6
                total_volume += volume
                count += 1
                
                if tx.get('from') in EXCHANGE_WALLETS.get('TRC20', []) or \
                   tx.get('to') in EXCHANGE_WALLETS.get('TRC20', []):
                    exchange_related = True
            
            avg_volume = total_volume / count if count > 0 else 0
            return incoming, outgoing, avg_volume, exchange_related
        
        except Exception as e:
            logging.warning(f"Попытка {attempt + 1} для TRC20 транзакций: {e}")
            if attempt < 1:
                time.sleep(1)
    
    return 0, 0, 0, False


def get_usdt_transactions_erc20(wallet_address, api_key, full_history=False):
    """Получение транзакций ERC20"""
    for attempt in range(2):
        try:
            url = (
                f"https://api.etherscan.io/api"
                f"?module=account&action=tokentx"
                f"&contractaddress=0xdAC17F958D2ee523a2206206994597C13D831ec7"
                f"&address={wallet_address}&startblock=0&endblock=99999999"
                f"&sort=asc&apikey={api_key}"
            )
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                return 0, 0, 0, False
            
            data = response.json()
            
            if data.get('status') != '1':
                return 0, 0, 0, False
            
            now = int(time.time())
            incoming = 0
            outgoing = 0
            total_volume = 0
            count = 0
            exchange_related = False
            
            exchange_addresses_lower = [addr.lower() for addr in EXCHANGE_WALLETS.get('ERC20', [])]
            
            for tx in data.get('result', []):
                is_recent = now - int(tx.get('timeStamp', 0)) <= 24 * 60 * 60
                if not full_history and not is_recent:
                    continue
                
                tx_from = tx.get('from', '').lower()
                tx_to = tx.get('to', '').lower()
                wallet_lower = wallet_address.lower()
                
                if tx_to == wallet_lower:
                    incoming += 1
                elif tx_from == wallet_lower:
                    outgoing += 1
                
                volume = int(tx.get('value', 0)) / 10**6
                total_volume += volume
                count += 1
                
                if tx_from in exchange_addresses_lower or tx_to in exchange_addresses_lower:
                    exchange_related = True
            
            avg_volume = total_volume / count if count > 0 else 0
            return incoming, outgoing, avg_volume, exchange_related
        
        except Exception as e:
            logging.warning(f"Попытка {attempt + 1} для ERC20 транзакций: {e}")
            if attempt < 1:
                time.sleep(1)
    
    return 0, 0, 0, False


def get_wallet_analytics(wallet_address, network, api_key, label='Без метки'):
    """Получение полной аналитики кошелька"""
    if network == 'TRC20':
        balance_result = get_usdt_balance_trc20(wallet_address, api_key)
        incoming, outgoing, avg_volume, _ = get_usdt_transactions_trc20(wallet_address, api_key, full_history=False)
        _, _, _, exchange_related = get_usdt_transactions_trc20(wallet_address, api_key, full_history=True)
    else:
        balance_result = get_usdt_balance_erc20(wallet_address, api_key)
        incoming, outgoing, avg_volume, _ = get_usdt_transactions_erc20(wallet_address, api_key, full_history=False)
        _, _, _, exchange_related = get_usdt_transactions_erc20(wallet_address, api_key, full_history=True)
    
    # Если ошибка — возвращаем информативное сообщение
    if not balance_result.success:
        return {
            'balance': balance_result.message,
            'incoming_24h': 0,
            'outgoing_24h': 0,
            'estimated_balance': "Недоступно",
            'exchange': "Не удалось определить",
            'label': label,
                        'error_type': balance_result.error_type
        }
    
    # Анализ биржевого кошелька
    exchange_status = "Не биржевой"
    if is_exchange_wallet(wallet_address, network):
        exchange_status = "🟢 Возможно биржевой (адрес известной биржи)"
    elif exchange_related:
        exchange_status = "🟡 Возможно биржевой (есть транзакции с биржами)"
    
    if incoming > 10 and outgoing > 10:
        exchange_status = "🟡 Высокая активность (возможно биржа или обменник)"
    
    # Прогнозируемый баланс на основе активности
    if incoming > outgoing:
        estimated_balance = balance_result.balance + (incoming - outgoing) * avg_volume
        estimated_text = f"📊 Прогноз: ~{estimated_balance:.2f} USDT (активный приток)"
    elif outgoing > incoming:
        estimated_balance = balance_result.balance - (outgoing - incoming) * avg_volume
        estimated_text = f"📊 Прогноз: ~{estimated_balance:.2f} USDT (активный отток)"
    else:
        estimated_balance = balance_result.balance
        estimated_text = f"📊 Прогноз: ~{estimated_balance:.2f} USDT (стабильный)"
    
    return {
        'balance': balance_result.message,
        'incoming_24h': incoming,
        'outgoing_24h': outgoing,
        'estimated_balance': estimated_text,
        'exchange': exchange_status,
        'label': label,
        'error_type': None
    }
