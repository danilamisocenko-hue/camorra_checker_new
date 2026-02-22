"""
Telegram Bot для мониторинга USDT кошельков (TRC20/ERC20)
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
from config import BOT_TOKEN, TRONGRID_API_KEY, ETHERSCAN_API_KEY
from bot_logic import get_wallet_analytics
from db import init_db, add_wallet, get_user_wallets, update_balance, get_all_wallets, delete_wallet, get_all_users, add_user

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния
SELECT_NETWORK_CHECK, ENTER_WALLET_CHECK, SELECT_NETWORK_ADD, ENTER_LABEL_ADD, ENTER_WALLET_ADD, CONFIRM_DELETE = range(6)
OWNER_ID = 7788251820


# ==================== КОМАНДЫ ====================

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
        await update.message.reply_text("❌ У вас нет доступа.")
        return
    
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: /broadcast <сообщение>")
        return
    
    message = ' '.join(context.args)
    users = get_all_users()
    
    success = 0
    failed = 0
    
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 *Сообщение:*\n\n{message}", parse_mode='Markdown')
            success += 1
        except Exception as e:
            logger.error(f"Ошибка отправки {user_id}: {e}")
            failed += 1
    
    await update.message.reply_text(f"✅ Готово!\nУспешно: {success}\nОшибки: {failed}")


# ==================== CALLBACKS ====================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        return
    
    elif data == 'faq':
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
        await query.message.reply_text(
            "❓ FAQ:\n\n"
            "• Бот проверяет баланс USDT на TRC20 и ERC20\n"
            "• Добавь кошелек на мониторинг\n"
            "• Получишь уведомление при балансе 1500+ USDT",
            reply_markup=keyboard
        )
        return
    
    elif data == 'check_balance':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 TRC20", callback_data='check_trc20')],
            [InlineKeyboardButton("🔗 ERC20", callback_data='check_erc20')],
            [InlineKeyboardButton("🔙 В меню", callback_data='back')]
        ])
        await query.message.reply_text("Выберите сеть:", reply_markup=keyboard)
        return SELECT_NETWORK_CHECK
    
    elif data == 'add_wallet':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 TRC20", callback_data='add_trc20')],
            [InlineKeyboardButton("🔗 ERC20", callback_data='add_erc20')],
            [InlineKeyboardButton("🔙 В меню", callback_data='back')]
        ])
        await query.message.reply_text("Выберите сеть:", reply_markup=keyboard)
        return SELECT_NETWORK_ADD
    
    elif data == 'my_wallets':
        wallets = get_user_wallets(user_id)
        if not wallets:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Добавить", callback_data='add_wallet')],
                [InlineKeyboardButton("🔙 В меню", callback_data='back')]
            ])
            await query.message.reply_text("Нет кошельков. Добавьте первый!", reply_markup=keyboard)
        else:
            text = "📋 *Ваши кошельки:*\n\n"
            for i, (wallet, network, balance, label) in enumerate(wallets, 1):
                label_disp = label if label else "Без метки"
                text += f"{i}. {label_disp} ({network})\n   `{wallet}`\n   Баланс: {balance:.2f} USDT\n\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Удалить", callback_data='delete_wallet')],
                [InlineKeyboardButton("🔙 В меню", callback_data='back')]
            ])
            await query.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        return
    
    elif data == 'delete_wallet':
        wallets = get_user_wallets(user_id)
        if not wallets:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
            await query.message.reply_text("Нет кошельков для удаления.", reply_markup=keyboard)
            return
        
        text = "❌ *Удаление кошелька*\n\nВведите номер:\n\n"
        for i, (wallet, network, balance, label) in enumerate(wallets, 1):
            label_disp = label if label else "Без метки"
            text += f"{i}. {label_disp} ({network})\n   `{wallet}`\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data='my_wallets')]
        ])
        await query.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        return CONFIRM_DELETE
    
    elif data == 'check_trc20':
        context.user_data['network'] = 'TRC20'
        context.user_data['action'] = 'check'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
        await query.message.reply_text("Введите адрес кошелька:", reply_markup=keyboard)
        return ENTER_WALLET_CHECK
    
    elif data == 'check_erc20':
        context.user_data['network'] = 'ERC20'
        context.user_data['action'] = 'check'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
        await query.message.reply_text("Введите адрес кошелька:", reply_markup=keyboard)
        return ENTER_WALLET_CHECK
    
    elif data == 'add_trc20':
        context.user_data['network'] = 'TRC20'
        context.user_data['action'] = 'add'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
        await query.message.reply_text("Введите метку для кошелька:", reply_markup=keyboard)
        return ENTER_LABEL_ADD
    
    elif data == 'add_erc20':
        context.user_data['network'] = 'ERC20'
        context.user_data['action'] = 'add'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
        await query.message.reply_text("Введите метку для кошелька:", reply_markup=keyboard)
        return ENTER_LABEL_ADD
    
    elif data.startswith('add_monitor_'):
        parts = data.split('_')
        wallet = parts[2]
        network = parts[3]
        try:
            add_wallet(user_id, wallet, network, 'Без метки')
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
            await query.message.reply_text(f"✅ Добавлено!\n`{wallet}` ({network})", reply_markup=keyboard, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка добавления: {e}")
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
            await query.message.reply_text("❌ Ошибка", reply_markup=keyboard)
        return


# ==================== ОБРАБОТКА СООБЩЕНИЙ ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id if user else None
    
    # Удаление кошелька
    if context.user_data.get('action') == 'delete':
        wallets = get_user_wallets(user_id)
        if not wallets:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
            await update.message.reply_text("Нет кошельков.", reply_markup=keyboard)
            return ConversationHandler.END
        
        if not text.isdigit():
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
            await update.message.reply_text("Введите номер кошелька.", reply_markup=keyboard)
            return CONFIRM_DELETE
        
        num = int(text)
        if num < 1 or num > len(wallets):
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
            await update.message.reply_text(f"Введите от 1 до {len(wallets)}.", reply_markup=keyboard)
            return CONFIRM_DELETE
        
        wallet, network, _, label = wallets[num - 1]
        delete_wallet(user_id, wallet, network)
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
        await update.message.reply_text(f"✅ Удалено: {label}", reply_markup=keyboard)
        return ConversationHandler.END
    
    # Проверка баланса
    if 'network' in context.user_data:
        network = context.user_data['network']
        
        if context.user_data.get('action') == 'check':
            wallet = text
            
            if network == 'TRC20' and not wallet.startswith('T'):
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
                await update.message.reply_text("❌ Невалидный TRC20 адрес (должен начинаться с T)", reply_markup=keyboard)
                return ENTER_WALLET_CHECK
            
            if network == 'ERC20' and not (wallet.startswith('0x') and len(wallet) == 42):
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
                await update.message.reply_text("❌ Невалидный ERC20 адрес", reply_markup=keyboard)
                return ENTER_WALLET_CHECK
            
            api_key = TRONGRID_API_KEY if network == 'TRC20' else ETHERSCAN_API_KEY
            analytics = get_wallet_analytics(wallet, network, api_key)
            
            scan_link = f"https://tronscan.org/#/address/{wallet}" if network == 'TRC20' else f"https://etherscan.io/address/{wallet}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Добавить", callback_data=f'add_monitor_{wallet}_{network}')],
                [InlineKeyboardButton("🌐 Сканер", url=scan_link)],
                [InlineKeyboardButton("🔙 В меню", callback_data='back')]
            ])
            
            await update.message.reply_text(
                f"💰 Баланс: {analytics['balance']}\n"
                f"📈 Входящие 24ч: {analytics['incoming_24h']}\n"
                f"📉 Исходящие 24ч: {analytics['outgoing_24h']}\n"
                f"📊 Тип: {analytics['exchange']}",
                reply_markup=keyboard
            )
            return ConversationHandler.END
        
        elif context.user_data.get('action') == 'add':
            if 'label' not in context.user_data:
                context.user_data['label'] = text or 'Без метки'
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
                await update.message.reply_text("Введите адрес кошелька:", reply_markup=keyboard)
                return ENTER_WALLET_ADD
            else:
                label = context.user_data['label']
                wallet = text
                
                if network == 'TRC20' and not wallet.startswith('T'):
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
                    await update.message.reply_text("❌ Невалидный TRC20 адрес", reply_markup=keyboard)
                    return ENTER_WALLET_ADD
                
                if network == 'ERC20' and not (wallet.startswith('0x') and len(wallet) == 42):
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
                    await update.message.reply_text("❌ Невалидный ERC20 адрес", reply_markup=keyboard)
                    return ENTER_WALLET_ADD
                
                try:
                    add_wallet(user_id, wallet, network, label)
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
                    await update.message.reply_text(f"✅ Добавлено!\n🏷️ {label}\n{wallet} ({network})", reply_markup=keyboard)
                except Exception as e:
                    logger.error(f"Ошибка: {e}")
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
                    await update.message.reply_text("❌ Ошибка", reply_markup=keyboard)
                return ConversationHandler.END
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
    await update.message.reply_text("Выберите действие из меню:", reply_markup=keyboard)
    return None


# ==================== МОНИТОРИНГ ====================

async def monitor_wallets(context: ContextTypes.DEFAULT_TYPE):
    try:
        wallets = get_all_wallets()
        for user_id, wallet, network, last_balance, label in wallets:
            try:
                from bot_logic import get_usdt_balance_trc20, get_usdt_balance_erc20
                
                if network == 'TRC20':
                    result = get_usdt_balance_trc20(wallet, TRONGRID_API_KEY)
                else:
                    result = get_usdt_balance_erc20(wallet, ETHERSCAN_API_KEY)
                
                current_balance = result.balance if hasattr(result, 'balance') else result[0]
                
                if current_balance >= 1500 and last_balance < 1500:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🔔 Баланс достиг {current_balance:.2f} USDT!\n\n{label}\n{wallet}"
                    )
                
                update_balance(user_id, wallet, network, current_balance)
            
            except Exception as e:
                logger.error(f"Ошибка мониторинга {wallet}: {e}")
                continue
    except Exception as e:
        logger.error(f"Ошибка мониторинга: {e}")


# ==================== MAIN ====================

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            SELECT_NETWORK_CHECK: [CallbackQueryHandler(handle_callback)],
            ENTER_WALLET_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            SELECT_NETWORK_ADD: [CallbackQueryHandler(handle_callback)],
            ENTER_LABEL_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            ENTER_WALLET_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        },
        fallbacks=[
            CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            CommandHandler("start", start_command)
        ],
        conversation_timeout=120
    )
    
        app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    app.job_queue.run_repeating(monitor_wallets, interval=3600, first=60)
    
    print("✅ Бот запущен!")
    app.run_polling()


if __name__ == '__main__':
    main()
