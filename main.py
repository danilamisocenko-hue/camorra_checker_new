from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from config import BOT_TOKEN, TRONGRID_API_KEY, ETHERSCAN_API_KEY
from bot_logic import get_usdt_balance_trc20, get_usdt_balance_erc20, get_wallet_analytics
from db import init_db, add_wallet, get_user_wallets, update_balance, get_all_wallets
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

SELECT_NETWORK_CHECK, ENTER_WALLET_CHECK, SELECT_NETWORK_ADD, ENTER_LABEL_ADD, ENTER_WALLET_ADD = range(5)

MAIN_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("❓ FAQ"), KeyboardButton("💰 Проверить баланс")],
    [KeyboardButton("➕ Добавить кошелек"), KeyboardButton("📋 Мои кошельки")]
], resize_keyboard=True, one_time_keyboard=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Привет! 👋 Выберите действие:", reply_markup=MAIN_KEYBOARD)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == 'back':
        await query.edit_message_text("Привет! 👋 Выберите действие:", reply_markup=MAIN_KEYBOARD)
        return None
    elif data == 'check_trc20':
        context.user_data['network'] = 'TRC20'
        context.user_data['action'] = 'check'
        await query.edit_message_text("Введите адрес кошелька для проверки баланса и аналитики: 🔍", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
        return ENTER_WALLET_CHECK
    elif data == 'check_erc20':
        context.user_data['network'] = 'ERC20'
        context.user_data['action'] = 'check'
        await query.edit_message_text("Введите адрес кошелька для проверки баланса и аналитики: 🔍", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
        return ENTER_WALLET_CHECK
    elif data == 'add_trc20':
        context.user_data['network'] = 'TRC20'
        context.user_data['action'] = 'add'
        await query.edit_message_text("Введите метку для кошелька (например, 'Мой личный' или оставьте пустым): 🏷️", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
        return ENTER_LABEL_ADD
    elif data == 'add_erc20':
        context.user_data['network'] = 'ERC20'
        context.user_data['action'] = 'add'
        await query.edit_message_text("Введите метку для кошелька (например, 'Мой личный' или оставьте пустым): 🏷️", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
        return ENTER_LABEL_ADD
    elif data.startswith('add_monitor_'):
        wallet = data.split('_')[2]
        network = data.split('_')[3]
        try:
            add_wallet(user_id, wallet, network, 'Без метки')
            await query.edit_message_text(f"Кошелек {wallet} ({network}) добавлен для мониторинга. 🔔 Вы получите уведомление при увеличении баланса на 1500+ USDT.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
        except Exception as e:
            logging.error(f"Ошибка при добавлении кошелька для user_id {user_id}: {e}")
            await query.edit_message_text("Ошибка при добавлении кошелька. Попробуйте позже.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user_id = update.effective_user.id if update.effective_user else None

    if text == "❓ FAQ":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
        await update.message.reply_text(
            "❓ FAQ:\n"
            "- Этот бот проверяет баланс USDT на кошельках TRC20 (Tron) и ERC20 (Ethereum). 💰\n"
            "- Мониторинг: Добавьте кошелек, и бот уведомит, если баланс увеличится на 1500+ USDT (проверка каждые 60 мин). 🔔\n"
            "- Проверка: Введите адрес, и бот покажет текущий баланс с полной аналитикой. 🔍\n"
            "- Метки: Ставьте метки на кошельки для удобства. 🏷️\n"
            "- Адреса: TRC20 начинаются с 'T', ERC20 с '0x'.\n"
            "Выберите действие.",
            reply_markup=keyboard
        )
        return None
    elif text == "💰 Проверить баланс":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 TRC20", callback_data='check_trc20')],
            [InlineKeyboardButton("🔗 ERC20", callback_data='check_erc20')],
            [InlineKeyboardButton("Выход в главное меню", callback_data='back')]
        ])
        await update.message.reply_text("Выберите сеть для проверки баланса: 🔍", reply_markup=keyboard)
        return SELECT_NETWORK_CHECK
    elif text == "➕ Добавить кошелек":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 TRC20", callback_data='add_trc20')],
            [InlineKeyboardButton("🔗 ERC20", callback_data='add_erc20')],
            [InlineKeyboardButton("Выход в главное меню", callback_data='back')]
        ])
        await update.message.reply_text("Выберите сеть для добавления кошелька на мониторинг: ➕", reply_markup=keyboard)
        return SELECT_NETWORK_ADD
    elif text == "📋 Мои кошельки":
        try:
            wallets = get_user_wallets(user_id)
            if not wallets:
                await update.message.reply_text("У вас нет добавленных кошельков. ➕ Добавьте первый!", reply_markup=MAIN_KEYBOARD)
            else:
                wallet_list = "\n".join([f"🏷️ {label}: {wallet} ({network})" for wallet, network, _, label in wallets])
                await update.message.reply_text(f"📋 Ваши кошельки:\n{wallet_list}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
        except Exception as e:
            logging.error(f"Ошибка при получении кошельков для user_id {user_id}: {e}")
            await update.message.reply_text("Ошибка при загрузке кошельков. Попробуйте позже. ❌", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
        return None
    else:
        if 'network' in context.user_data:
            network = context.user_data['network']
            if context.user_data.get('action') == 'check':
                wallet = text.strip()
                if network == 'TRC20' and not wallet.startswith('T'):
                    await update.message.reply_text("Ошибка: Адрес TRC20 должен начинаться с 'T'. Попробуйте снова. ❌", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
                    return ENTER_WALLET_CHECK
                if network == 'ERC20' and not wallet.startswith('0x'):
                    await update.message.reply_text("Ошибка: Адрес ERC20 должен начинаться с '0x'. Попробуйте снова. ❌", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
                    return ENTER_WALLET_CHECK
                analytics = get_wallet_analytics(wallet, network, TRONGRID_API_KEY if network == 'TRC20' else ETHERSCAN_API_KEY)
                menu_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Добавить на мониторинг", callback_data=f'add_monitor_{wallet}_{network}')],
                    [InlineKeyboardButton("Выход в главное меню", callback_data='back')]
                ])
                await update.message.reply_text(
                    f"💰 Проверка баланса и аналитика для {network} кошелька {wallet}:\n"
                    f"- Текущий баланс: {analytics['balance']}\n"
                    f"- Входящих транзакций USDT за 24 ч: {analytics['incoming_24h']} 📈\n"
                    f"- Исходящих транзакций USDT за 24 ч: {analytics['outgoing_24h']} 📉\n"
                    f"- Приблизительный баланс: {analytics['estimated_balance']}\n"
                    f"- Тип: {analytics['exchange']}",
                    reply_markup=menu_keyboard
                )
                return ConversationHandler.END
            elif context.user_data.get('action') == 'add':
                if 'label' not in context.user_data:
                    context.user_data['label'] = text.strip() or 'Без метки'
                    await update.message.reply_text("Введите адрес кошелька: ➕", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
                    return ENTER_WALLET_ADD
                else:
                    label = context.user_data['label']
                    wallet = text.strip()
                    if not user_id:
                        await update.message.reply_text("Ошибка: Не удалось определить пользователя. Попробуйте /start. ❌", reply_markup=MAIN_KEYBOARD)
                        return ConversationHandler.END
                    if network == 'TRC20' and not wallet.startswith('T'):
                        await update.message.reply_text("Ошибка: Адрес TRC20 должен начинаться с 'T'. Попробуйте снова. ❌", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
                        return ENTER_WALLET_ADD
                    if network == 'ERC20' and not wallet.startswith('0x'):
                        await update.message.reply_text("Ошибка: Адрес ERC20 должен начинаться с '0x'. Попробуйте снова. ❌", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
                        return ENTER_WALLET_ADD
                    try:
                        add_wallet(user_id, wallet, network, label)
                        await update.message.reply_text(f"Кошелек {wallet} ({network}) с меткой '{label}' добавлен для мониторинга. 🔔 Вы получите уведомление при увеличении баланса на 1500+ USDT.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
                    except Exception as e:
                        logging.error(f"Ошибка при добавлении кошелька для user_id {user_id}: {e}")
                        await update.message.reply_text("Ошибка при добавлении кошелька. Попробуйте позже. ❌", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]]))
                    return ConversationHandler.END

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
            SELECT_NETWORK_CHECK: [CallbackQueryHandler(handle_callback)],
            ENTER_WALLET_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            SELECT_NETWORK_ADD: [CallbackQueryHandler(handle_callback)],
            ENTER_LABEL_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ENTER_WALLET_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=30
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))

    job_queue = application.job_queue
    job_queue.run_repeating(monitor_wallets, interval=3600, first=10)

    application.run_polling()

if __name__ == '__main__':
    main()
