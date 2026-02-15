from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from config import BOT_TOKEN, TRONGRID_API_KEY, ETHERSCAN_API_KEY
from bot_logic import get_usdt_balance_trc20, get_usdt_balance_erc20, get_wallet_analytics
from db import init_db, add_wallet, get_user_wallets, update_balance, get_all_wallets
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Состояния для ConversationHandler (расширены для метки)
SELECT_NETWORK_CHECK, ENTER_WALLET_CHECK, SELECT_NETWORK_ADD, ENTER_LABEL_ADD, ENTER_WALLET_ADD = range(5)

# Клавиатура с кнопками (убрана "Аналитика кошелька")
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("❓ FAQ"), KeyboardButton("💰 Проверить баланс")],
    [KeyboardButton("➕ Добавить кошелек"), KeyboardButton("📋 Мои кошельки")]
], resize_keyboard=True, one_time_keyboard=False)

NETWORK_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("🔗 TRC20"), KeyboardButton("🔗 ERC20")]
], resize_keyboard=True, one_time_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Привет! 👋 Выберите действие:", reply_markup=MAIN_KEYBOARD)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user_id = update.effective_user.id if update.effective_user else None

    if text == "❓ FAQ":
        await update.message.reply_text(
            "❓ FAQ:\n"
            "- Этот бот проверяет баланс USDT на кошельках TRC20 (Tron) и ERC20 (Ethereum). 💰\n"
            "- Мониторинг: Добавьте кошелек, и бот уведомит, если баланс увеличится на 1500+ USDT (проверка каждые 60 мин). 🔔\n"
            "- Проверка: Введите адрес, и бот покажет текущий баланс с полной аналитикой. 🔍\n"
            "- Метки: Ставьте метки на кошельки для удобства. 🏷️\n"
            "- Адреса: TRC20 начинаются с 'T', ERC20 с '0x'.\n"
            "Вернуться: /start"
        )
        return None
    elif text == "💰 Проверить баланс":
        await update.message.reply_text("Выберите сеть для проверки баланса: 🔍", reply_markup=NETWORK_KEYBOARD)
        context.user_data['action'] = 'check'
        return SELECT_NETWORK_CHECK
    elif text == "➕ Добавить кошелек":
        await update.message.reply_text("Выберите сеть для добавления кошелька на мониторинг: ➕", reply_markup=NETWORK_KEYBOARD)
        context.user_data['action'] = 'add'
        return SELECT_NETWORK_ADD
    elif text == "📋 Мои кошельки":
        if not user_id:
            await update.message.reply_text("Ошибка: Не удалось определить пользователя. Попробуйте /start. ❌")
            return None
        try:
            wallets = get_user_wallets(user_id)
            if not wallets:
                await update.message.reply_text("У вас нет добавленных кошельков. ➕ Добавьте первый!")
            else:
                wallet_list = "\n".join([f"🏷️ {label}: {wallet} ({network})" for wallet, network, _, label in wallets])
                await update.message.reply_text(f"📋 Ваши кошельки:\n{wallet_list}")
        except Exception as e:
            logging.error(f"Ошибка при получении кошельков для user_id {user_id}: {e}")
            await update.message.reply_text("Ошибка при загрузке кошельков. Попробуйте позже или /start. ❌")
        return None
    elif text == "🔗 TRC20":
        context.user_data['network'] = 'TRC20'
        if context.user_data.get('action') == 'check':
            await update.message.reply_text("Введите адрес кошелька для проверки баланса и аналитики: 🔍")
            return ENTER_WALLET_CHECK
        elif context.user_data.get('action') == 'add':
            await update.message.reply_text("Введите метку для кошелька (например, 'Мой личный' или оставьте пустым): 🏷️")
            return ENTER_LABEL_ADD
    elif text == "🔗 ERC20":
        context.user_data['network'] = 'ERC20'
        if context.user_data.get('action') == 'check':
            await update.message.reply_text("Введите адрес кошелька для проверки баланса и аналитики: 🔍")
            return ENTER_WALLET_CHECK
        elif context.user_data.get('action') == 'add':
            await update.message.reply_text("Введите метку для кошелька (например, 'Мой личный' или оставьте пустым): 🏷️")
            return ENTER_LABEL_ADD
    else:
        # Обработка ввода адреса или метки
        if 'network' in context.user_data:
            network = context.user_data['network']
            if context.user_data.get('action') == 'check':
                wallet = text.strip()
                if network == 'TRC20' and not wallet.startswith('T'):
                    await update.message.reply_text("Ошибка: Адрес TRC20 должен начинаться с 'T'. Попробуйте снова. ❌")
                    return ENTER_WALLET_CHECK
                if network == 'ERC20' and not wallet.startswith('0x'):
                    await update.message.reply_text("Ошибка: Адрес ERC20 должен начинаться с '0x'. Попробуйте снова. ❌")
                    return ENTER_WALLET_CHECK
                analytics = get_wallet_analytics(wallet, network, TRONGRID_API_KEY if network == 'TRC20' else ETHERSCAN_API_KEY)
                await update.message.reply_text(
                    f"💰 Проверка баланса и аналитика для {network} кошелька {wallet}:\n"
                    f"- Текущий баланс: {analytics['balance']}\n"
                    f"- Входящих транзакций USDT за 24 ч: {analytics['incoming_24h']} 📈\n"
                    f"- Исходящих транзакций USDT за 24 ч: {analytics['outgoing_24h']} 📉\n"
                    f"- Приблизительный баланс: {analytics['estimated_balance']}\n"
                    f"- Тип: {analytics['exchange']}"
                )
                return ConversationHandler.END
            elif context.user_data.get('action') == 'add':
                if 'label' not in context.user_data:
                    context.user_data['label'] = text.strip() or 'Без метки'
                    await update.message.reply_text("Введите адрес кошелька: ➕")
                    return ENTER_WALLET_ADD
                else:
                    label = context.user_data['label']
                    wallet = text.strip()
                    if not user_id:
                        await update.message.reply_text("Ошибка: Не удалось определить пользователя. Попробуйте /start. ❌")
                        return ConversationHandler.END
                    if network == 'TRC20' and not wallet.startswith('T'):
                        await update.message.reply_text("Ошибка: Адрес TRC20 должен начинаться с 'T'. Попробуйте снова. ❌")
                        return ENTER_WALLET_ADD
                    if network == 'ERC20' and not wallet.startswith('0x'):
                        await update.message.reply_text("Ошибка: Адрес ERC20 должен начинаться с '0x'. Попробуйте снова. ❌")
                        return ENTER_WALLET_ADD
                    try:
                        add_wallet(user_id, wallet, network, label)
                        await update.message.reply_text(f"Кошелек {wallet} ({network}) с меткой '{label}' добавлен для мониторинга. 🔔 Вы получите уведомление при увеличении баланса на 1500+ USDT.")
                    except Exception as e:
                        logging.error(f"Ошибка при добавлении кошелька для user_id {user_id}: {e}")
                        await update.message.reply_text("Ошибка при добавлении кошелька. Попробуйте позже или /start. ❌")
                    return ConversationHandler.END

    # Если ничего не подошло, показать главное меню
    await update.message.reply_text("Не понял команду. Выберите действие:", reply_markup=MAIN_KEYBOARD)
    return None

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено. ❌", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

async def monitor_wallets(context: ContextTypes.DEFAULT_TYPE):
    try:
        wallets = get_all_wallets()
        for user_id, wallet, network, last_balance, label in wallets:
            if network == 'TRC20':
                current_balance, _ = get_usdt_balance_trc20(wallet, TRONGRID_API_KEY)
            else:
                current_balance, _ = get_usdt_balance_erc20(wallet, ETHERSCAN_API_KEY)
            
            if current_balance - last_balance >= 1500:
                increase = current_balance - last_balance
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🔔 Уведомление: Баланс на кошельке '{label}' ({wallet}, {network}) увеличился на {increase:.6f} USDT (теперь {current_balance:.6f} USDT)."
                )
                update_balance(user_id, wallet, network, current_balance)
    except Exception as e:
        logging.error(f"Ошибка в мониторинге: {e}")

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            SELECT_NETWORK_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ENTER_WALLET_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            SELECT_NETWORK_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ENTER_LABEL_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ENTER_WALLET_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=30  # Таймаут 30 секунд для предотвращения "зависания"
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    job_queue = application.job_queue
    job_queue.run_repeating(monitor_wallets, interval=3600, first=10)  # 3600 сек = 60 мин

    application.run_polling()

if __name__ == '__main__':
    main()