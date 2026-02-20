"""
Telegram Bot для мониторинга USDT кошельков
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from config import BOT_TOKEN, TRONGRID_API_KEY, ETHERSCAN_API_KEY
from bot_logic import get_usdt_balance_trc20, get_usdt_balance_erc20, get_wallet_analytics
from db import init_db, add_wallet, get_user_wallets, update_balance, get_all_wallets, delete_wallet, get_all_users, add_user
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

SELECT_NETWORK_CHECK, ENTER_WALLET_CHECK, SELECT_NETWORK_ADD, ENTER_LABEL_ADD, ENTER_WALLET_ADD = range(5)

OWNER_ID = 7788251820  # ЗАМЕНИТЕ НА СВОЙ TELEGRAM ID


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        add_user(user.id, user.username, user.first_name)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❓ FAQ", callback_data='faq')],
        [InlineKeyboardButton("💰 Проверить баланс", callback_data='check_balance')],
        [InlineKeyboardButton("➕ Добавить кошелек", callback_data='add_wallet')],
        [InlineKeyboardButton("📋 Мои кошельки", callback_data='my_wallets')]
    ])
    await update.message.reply_text("Привет! 👋\n\nВыберите действие:", reply_markup=keyboard)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return
    
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: /broadcast <сообщение>")
        return
    
    message = ' '.join(context.args)
    users = get_all_users()
    
    if not users:
        await update.message.reply_text("❌ Нет пользователей для рассылки.")
        return
    
    success = 0
    failed = 0
    
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 *Сообщение от бота:*\n\n{message}", parse_mode='Markdown')
            success += 1
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
            failed += 1
    
    await update.message.reply_text(f"✅ Рассылка завершена!\n\nУспешно: {success}\nОшибки: {failed}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == 'back':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❓ FAQ", callback_data='faq')],
            [InlineKeyboardButton("💰 Проверить баланс", callback_data='check_balance')],
            [InlineKeyboardButton("➕ Добавить кошелек", callback_data='add_wallet')],
            [InlineKeyboardButton("📋 Мои кошельки", callback_data='my_wallets')]
        ])
        await query.message.reply_text("Привет! 👋\n\nВыберите действие:", reply_markup=keyboard)
        return None
    
    elif data == 'faq':
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
        await query.message.reply_text(
            "❓ FAQ:\n\n"
            "• Этот бот проверяет баланс USDT на кошельках TRC20 (Tron) и ERC20 (Ethereum). 💰\n\n"
            "• Мониторинг: Добавьте кошелек, и бот уведомит вас, если баланс достигнет 1500+ USDT (проверка каждые 60 минут). 🔔\n\n"
            "• Проверка: Введите адрес, и бот покажет текущий баланс с полной аналитикой. 🔍\n\n"
            "• Метки: Ставьте метки на кошельки для удобства. 🏷️\n\n"
            "• Адреса: TRC20 начинаются с 'T', ERC20 с '0x'.",
            reply_markup=keyboard
        )
        return None
    
    elif data == 'check_balance':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 TRC20", callback_data='check_trc20')],
            [InlineKeyboardButton("🔗 ERC20", callback_data='check_erc20')],
            [InlineKeyboardButton("Выход в главное меню", callback_data='back')]
        ])
        await query.message.reply_text("Выберите сеть для проверки баланса: 🔍", reply_markup=keyboard)
        return SELECT_NETWORK_CHECK
    
    elif data == 'add_wallet':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 TRC20", callback_data='add_trc20')],
            [InlineKeyboardButton("🔗 ERC20", callback_data='add_erc20')],
            [InlineKeyboardButton("Выход в главное меню", callback_data='back')]
        ])
        await query.message.reply_text("Выберите сеть для добавления кошелька на мониторинг: ➕", reply_markup=keyboard)
        return SELECT_NETWORK_ADD
    
    elif data == 'my_wallets':
        try:
            wallets = get_user_wallets(user_id)
            if not wallets:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
                await query.message.reply_text("У вас нет добавленных кошельков. ➕ Добавьте первый!", reply_markup=keyboard)
            else:
                for wallet, network, _, label in wallets:
                    label_display = label if label else "Без метки"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Удалить", callback_data=f'delete_{wallet}_{network}')],
                        [InlineKeyboardButton("Выход в главное меню", callback_data='back')]
                    ])
                    await query.message.reply_text(f"🏷️ {label_display}\n`{wallet}`\nСеть: {network}", reply_markup=keyboard, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка при получении кошельков для user_id {user_id}: {e}")
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
            await query.message.reply_text("❌ Ошибка при загрузке кошельков. Попробуйте позже.", reply_markup=keyboard)
        return None
    
    elif data.startswith('delete_'):
        parts = data.split('_')
        wallet = parts[1]
        network = parts[2]
        try:
            delete_wallet(user_id, wallet, network)
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
            await query.message.reply_text(f"✅ Кошелек удален из мониторинга:\n`{wallet}` ({network})", reply_markup=keyboard, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка при удалении кошелька для user_id {user_id}: {e}")
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
            await query.message.reply_text("❌ Ошибка при удалении кошелька. Попробуйте позже.", reply_markup=keyboard)
        return None
    
    elif data == 'check_trc20':
        context.user_data['network'] = 'TRC20'
        context.user_data['action'] = 'check'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
        await query.message.reply_text("Введите адрес кошелька для проверки баланса и аналитики: 🔍", reply_markup=keyboard)
        return ENTER_WALLET_CHECK
    
    elif data == 'check_erc20':
        context.user_data['network'] = 'ERC20'
        context.user_data['action'] = 'check'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
        await query.message.reply_text("Введите адрес кошелька для проверки баланса и аналитики: 🔍", reply_markup=keyboard)
        return ENTER_WALLET_CHECK
    
    elif data == 'add_trc20':
        context.user_data['network'] = 'TRC20'
        context.user_data['action'] = 'add'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
        await query.message.reply_text("Введите метку для кошелька (например, 'Мой личный' или оставьте пустым): 🏷️", reply_markup=keyboard)
        return ENTER_LABEL_ADD
    
    elif data == 'add_erc20':
        context.user_data['network'] = 'ERC20'
        context.user_data['action'] = 'add'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
        await query.message.reply_text("Введите метку для кошелька (например, 'Мой личный' или оставьте пустым): 🏷️", reply_markup=keyboard)
        return ENTER_LABEL_ADD
    
    elif data.startswith('add_monitor_'):
        wallet = data.split('_')[2]
        network = data.split('_')[3]
        try:
            add_wallet(user_id, wallet, network, 'Без метки')
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
            await query.message.reply_text(f"✅ Кошелек добавлен для мониторинга:\n`{wallet}` ({network})\n\n🔔 Вы получите уведомление при балансе 1500+ USDT.", reply_markup=keyboard, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка при добавлении кошелька для user_id {user_id}: {e}")
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
            await query.message.reply_text("❌ Ошибка при добавлении кошелька. Попробуйте позже.", reply_markup=keyboard)
        return None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user = update.effective_user
    user_id = user.id if user else None

    if 'network' in context.user_data:
        network = context.user_data['network']
        
        if context.user_data.get('action') == 'check':
            wallet = text.strip()
            
            if network == 'TRC20' and not wallet.startswith('T'):
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
                await update.message.reply_text("❌ Ошибка: Адрес TRC20 должен начинаться с 'T'. Попробуйте снова.", reply_markup=keyboard)
                return ENTER_WALLET_CHECK
            
            if network == 'ERC20' and not wallet.startswith('0x'):
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
                await update.message.reply_text("❌ Ошибка: Адрес ERC20 должен начинаться с '0x'. Попробуйте снова.", reply_markup=keyboard)
                return ENTER_WALLET_CHECK
            
            api_key = TRONGRID_API_KEY if network == 'TRC20' else ETHERSCAN_API_KEY
            analytics = get_wallet_analytics(wallet, network, api_key)
            
            # Ссылки на сканеры
            if network == 'TRC20':
                scan_link = f"https://tronscan.org/#/address/{wallet}"
            else:
                scan_link = f"https://etherscan.io/address/{wallet}"
            
            menu_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Добавить на мониторинг", callback_data=f'add_monitor_{wallet}_{network}')],
                [InlineKeyboardButton("🌐 Открыть в сканере", url=scan_link)],
                [InlineKeyboardButton("Выход в главное меню", callback_data='back')]
            ])
            
            await update.message.reply_text(
                f"💰 Проверка баланса и аналитика\nСеть: {network}\nКошелек: `{wallet}`\n[Открыть в сканере]({scan_link})\n\n"
                f"• Текущий баланс: {analytics['balance']}\n"
                f"• Входящих USDT за 24ч: {analytics['incoming_24h']} 📈\n"
                f"• Исходящих USDT за 24ч: {analytics['outgoing_24h']} 📉\n"
                f"• Приблизительный баланс: {analytics['estimated_balance']}\n"
                f"• Тип: {analytics['exchange']}",
                reply_markup=menu_keyboard,
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        elif context.user_data.get('action') == 'add':
            if 'label' not in context.user_data:
                context.user_data['label'] = text.strip() or 'Без метки'
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
                await update.message.reply_text("Введите адрес кошелька: ➕", reply_markup=keyboard)
                return ENTER_WALLET_ADD
            else:
                label = context.user_data['label']
                wallet = text.strip()
                
                if not user_id:
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
                    await update.message.reply_text("❌ Ошибка: Не удалось определить пользователя. Попробуйте /start.", reply_markup=keyboard)
                    return ConversationHandler.END
                
                if network == 'TRC20' and not wallet.startswith('T'):
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
                    await update.message.reply_text("❌ Ошибка: Адрес TRC20 должен начинаться с 'T'. Попробуйте снова.", reply_markup=keyboard)
                    return ENTER_WALLET_ADD
                
                if network == 'ERC20' and not wallet.startswith('0x'):
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
                    await update.message.reply_text("❌ Ошибка: Адрес ERC20 должен начинаться с '0x'. Попробуйте снова.", reply_markup=keyboard)
                    return ENTER_WALLET_ADD
                
                try:
                    add_wallet(user_id, wallet, network, label)
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
                    await update.message.reply_text(
                        f"✅ Кошелек добавлен для мониторинга:\n`{wallet}` ({network})\nМетка: {label}\n\n🔔 Вы получите уведомление при балансе 1500+ USDT.",
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при добавлении кошелька для user_id {user_id}: {e}")
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
                    await update.message.reply_text("❌ Ошибка при добавлении кошелька. Попробуйте позже.", reply_markup=keyboard)
                return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
    await update.message.reply_text("Не понял команду. Выберите действие:", reply_markup=keyboard)
    return None


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
    await update.message.reply_text("Действие отменено. ❌", reply_markup=keyboard)
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Выход в главное меню", callback_data='back')]])
    await update.message.reply_text("Действие отменено. ❌", reply_markup=keyboard)
    return ConversationHandler.END


async def monitor_wallets(context: ContextTypes.DEFAULT_TYPE):
    try:
        wallets = get_all_wallets()
        for user_id, wallet, network, last_balance, label in wallets:
            if network == 'TRC20':
                current_balance, _ = get_usdt_balance_trc20(wallet, TRONGRID_API_KEY)
            else:
                current_balance, _ = get_usdt_balance_erc20(wallet, ETHERSCAN_API_KEY)
            
            if current_balance >= 1500 and last_balance < 1500:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🔔 Уведомление: Баланс на кошельке '{label}' ({wallet}, {network}) достиг {current_balance:.6f} USDT (больше 1500 USDT)."
                )
                update_balance(user_id, wallet, network, current_balance)
    except Exception as e:
        logger.error(f"Ошибка в мониторинге: {e}")


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
        fallbacks=[CommandHandler("cancel", cancel_command)],
        conversation_timeout=30
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))

    job_queue = application.job_queue
    job_queue.run_repeating(monitor_wallets, interval=3600, first=10)

    print("Бот запущен!")
    application.run_polling()


if __name__ == '__main__':
    main()

