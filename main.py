import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
from config import BOT_TOKEN, TRONGRID_API_KEY, ETHERSCAN_API_KEY, ADMINS
from bot_logic import get_wallet_analytics, get_usdt_balance_trc20, get_usdt_balance_erc20
from db import init_db, add_wallet, get_user_wallets, update_balance, get_all_wallets, delete_wallet, get_all_users, add_user

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SELECT_NETWORK_CHECK, ENTER_WALLET_CHECK, SELECT_NETWORK_ADD, ENTER_LABEL_ADD, ENTER_WALLET_ADD, CONFIRM_DELETE = range(6)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        add_user(user.id, user.username, user.first_name)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("FAQ", callback_data='faq')],
        [InlineKeyboardButton("Проверить баланс", callback_data='check_balance')],
        [InlineKeyboardButton("Добавить кошелек", callback_data='add_wallet')],
        [InlineKeyboardButton("Мои кошельки", callback_data='my_wallets')]
    ])
    
    # Добавляем кнопку админа если пользователь админ
    if user.id in ADMINS:
        keyboard.inline_keyboard.append([InlineKeyboardButton("🔧 Админ-панель", callback_data='admin_panel')])
    
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=keyboard)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in ADMINS:
        await update.message.reply_text("Нет доступа.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /broadcast <сообщение>")
        return
    
    message = ' '.join(context.args)
    users = get_all_users()
    
    success = 0
    failed = 0
    
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 Рассылка:\n\n{message}")
            success += 1
        except Exception as e:
            logger.error(f"Ошибка {user_id}: {e}")
            failed += 1
    
    await update.message.reply_text(f"Готово!\nУспешно: {success}\nОшибки: {failed}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == 'back':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("FAQ", callback_data='faq')],
            [InlineKeyboardButton("Проверить баланс", callback_data='check_balance')],
            [InlineKeyboardButton("Добавить кошелек", callback_data='add_wallet')],
            [InlineKeyboardButton("Мои кошельки", callback_data='my_wallets')]
        ])
        if user_id in ADMINS:
            keyboard.inline_keyboard.append([InlineKeyboardButton("🔧 Админ-панель", callback_data='admin_panel')])
        await query.message.reply_text("Главное меню:", reply_markup=keyboard)
        return
    
    # АДМИН ПАНЕЛЬ
    elif data == 'admin_panel':
        if user_id not in ADMINS:
            await query.message.reply_text("Нет доступа!")
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast')],
            [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back')]
        ])
        await query.message.reply_text("🔧 Админ-панель:", reply_markup=keyboard)
        return
    
    elif data == 'admin_broadcast':
        if user_id not in ADMINS:
            return
        context.user_data['action'] = 'admin_broadcast'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data='admin_panel')]])
        await query.message.reply_text("Введите текст рассылки:", reply_markup=keyboard)
        return CONFIRM_DELETE
    
    elif data == 'admin_stats':
        if user_id not in ADMINS:
            return
        users = get_all_users()
        wallets = get_all_wallets()
        
        text = f"📊 *Статистика бота:*\n\n"
        text += f"👥 Пользователей: {len(users)}\n"
        text += f"💰 Кошельков на мониторинге: {len(wallets)}\n"
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]])
        await query.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        return
    
    elif data == 'faq':
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
        await query.message.reply_text(
            "FAQ:\n\n"
            "• Бот проверяет баланс USDT на TRC20 и ERC20\n"
            "• Добавьте кошелек на мониторинг\n"
            "• Получите уведомление когда баланс превысит 1500 USDT",
            reply_markup=keyboard
        )
        return
    
    elif data == 'check_balance':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("TRC20", callback_data='check_trc20')],
            [InlineKeyboardButton("ERC20", callback_data='check_erc20')],
            [InlineKeyboardButton("В меню", callback_data='back')]
        ])
        await query.message.reply_text("Выберите сеть:", reply_markup=keyboard)
        return SELECT_NETWORK_CHECK
    
    elif data == 'add_wallet':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("TRC20", callback_data='add_trc20')],
            [InlineKeyboardButton("ERC20", callback_data='add_erc20')],
            [InlineKeyboardButton("В меню", callback_data='back')]
        ])
        await query.message.reply_text("Выберите сеть:", reply_markup=keyboard)
        return SELECT_NETWORK_ADD
    
    elif data == 'my_wallets':
        wallets = get_user_wallets(user_id)
        if not wallets:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Добавить", callback_data='add_wallet')],
                [InlineKeyboardButton("В меню", callback_data='back')]
            ])
            await query.message.reply_text("Нет кошельков.", reply_markup=keyboard)
        else:
            text = "📋 *Ваши кошельки:*\n\n"
            for i, (wallet, network, balance, label) in enumerate(wallets, 1):
                label_disp = label if label else "Без метки"
                text += f"{i}. {label_disp} ({network}) - {balance:.2f} USDT\n"
                text += f"   `{wallet}`\n\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Удалить", callback_data='delete_wallet')],
                [InlineKeyboardButton("В меню", callback_data='back')]
            ])
            await query.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        return
    
    elif data == 'delete_wallet':
        wallets = get_user_wallets(user_id)
        if not wallets:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
            await query.message.reply_text("Нет кошельков.", reply_markup=keyboard)
            return
        
        # ВАЖНО: Устанавливаем action = delete
        context.user_data['action'] = 'delete'
        
        text = "❌ *Удаление кошелька*\n\nВведите номер:\n\n"
        for i, (wallet, network, balance, label) in enumerate(wallets, 1):
            label_disp = label if label else "Без метки"
            text += f"{i}. {label_disp} ({network})\n   `{wallet}`\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Отмена", callback_data='my_wallets')]
        ])
        await query.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        return CONFIRM_DELETE
    
    elif data == 'check_trc20':
        context.user_data['network'] = 'TRC20'
        context.user_data['action'] = 'check'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
        await query.message.reply_text("Введите адрес кошелька:", reply_markup=keyboard)
        return ENTER_WALLET_CHECK
    
    elif data == 'check_erc20':
        context.user_data['network'] = 'ERC20'
        context.user_data['action'] = 'check'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
        await query.message.reply_text("Введите адрес кошелька:", reply_markup=keyboard)
        return ENTER_WALLET_CHECK
    
    elif data == 'add_trc20':
        context.user_data['network'] = 'TRC20'
        context.user_data['action'] = 'add'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
        await query.message.reply_text("Введите метку:", reply_markup=keyboard)
        return ENTER_LABEL_ADD
    
    elif data == 'add_erc20':
        context.user_data['network'] = 'ERC20'
        context.user_data['action'] = 'add'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
        await query.message.reply_text("Введите метку:", reply_markup=keyboard)
        return ENTER_LABEL_ADD
    
    elif data.startswith('add_monitor_'):
        parts = data.split('_')
        wallet = parts[2]
        network = parts[3]
        try:
            add_wallet(user_id, wallet, network, 'Без метки')
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
            await query.message.reply_text(f"✅ Добавлено! {wallet} ({network})", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
            await query.message.reply_text("Ошибка", reply_markup=keyboard)
        return


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id if user else None
    
    # РАССЫЛКА АДМИНА
    if context.user_data.get('action') == 'admin_broadcast':
        if user_id not in ADMINS:
            return ConversationHandler.END
        
        users = get_all_users()
        success = 0
        failed = 0
        
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 Рассылка:\n\n{text}")
                success += 1
            except:
                failed += 1
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔧 В админку", callback_data='admin_panel')]])
        await update.message.reply_text(f"✅ Рассылка завершена!\nУспешно: {success}\nОшибки: {failed}", reply_markup=keyboard)
        return ConversationHandler.END
    
    # УДАЛЕНИЕ КОШЕЛЬКА
    if context.user_data.get('action') == 'delete':
        wallets = get_user_wallets(user_id)
        if not wallets:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
            await update.message.reply_text("Нет кошельков.", reply_markup=keyboard)
            return ConversationHandler.END
        
        if not text.isdigit():
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
            await update.message.reply_text("Введите номер кошелька.", reply_markup=keyboard)
            return CONFIRM_DELETE
        
        num = int(text)
        if num < 1 or num > len(wallets):
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
            await update.message.reply_text(f"Введите от 1 до {len(wallets)}.", reply_markup=keyboard)
            return CONFIRM_DELETE
        
        wallet, network, _, label = wallets[num - 1]
        delete_wallet(user_id, wallet, network)
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
        await update.message.reply_text(f"✅ Удалено: {label}", reply_markup=keyboard)
        return ConversationHandler.END
    
    # ПРОВЕРКА БАЛАНСА
    if 'network' in context.user_data:
        network = context.user_data['network']
        
        if context.user_data.get('action') == 'check':
            wallet = text
            
            if network == 'TRC20' and not wallet.startswith('T'):
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
                await update.message.reply_text("Ошибка: адрес TRC20 должен начинаться с T", reply_markup=keyboard)
                return ENTER_WALLET_CHECK
            
            if network == 'ERC20' and not (wallet.startswith('0x') and len(wallet) == 42):
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
                await update.message.reply_text("Ошибка: невалидный адрес ERC20", reply_markup=keyboard)
                return ENTER_WALLET_CHECK
            
            api_key = TRONGRID_API_KEY if network == 'TRC20' else ETHERSCAN_API_KEY
            analytics = get_wallet_analytics(wallet, network, api_key)
            
            scan_link = f"https://tronscan.org/#/address/{wallet}" if network == 'TRC20' else f"https://etherscan.io/address/{wallet}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Добавить", callback_data=f'add_monitor_{wallet}_{network}')],
                [InlineKeyboardButton("🔍 Сканер", url=scan_link)],
                [InlineKeyboardButton("В меню", callback_data='back')]
            ])
            
            await update.message.reply_text(
                f"💰 *Баланс:* {analytics['balance']}\n"
                f"📈 *Входящие (24ч):* {analytics['incoming_24h']} USDT\n"
                f"📉 *Исходящие (24ч):* {analytics['outgoing_24h']} USDT\n"
                f"📊 *Тип кошелька:* {analytics['exchange']}\n"
                f"🔗 [Сканер]({scan_link})",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        elif context.user_data.get('action') == 'add':
            if 'label' not in context.user_data:
                context.user_data['label'] = text or 'Без метки'
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
                await update.message.reply_text("Введите адрес кошелька:", reply_markup=keyboard)
                return ENTER_WALLET_ADD
            else:
                label = context.user_data['label']
                wallet = text
                
                if network == 'TRC20' and not wallet.startswith('T'):
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
                    await update.message.reply_text("Ошибка: адрес TRC20", reply_markup=keyboard)
                    return ENTER_WALLET_ADD
                
                if network == 'ERC20' and not (wallet.startswith('0x') and len(wallet) == 42):
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
                    await update.message.reply_text("Ошибка: адрес ERC20", reply_markup=keyboard)
                    return ENTER_WALLET_ADD
                
                try:
                    add_wallet(user_id, wallet, network, label)
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
                    await update.message.reply_text(f"✅ Добавлено! {label} ({network})", reply_markup=keyboard)
                except Exception as e:
                    logger.error(f"Ошибка: {e}")
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
                    await update.message.reply_text("Ошибка", reply_markup=keyboard)
                return ConversationHandler.END
    
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("В меню", callback_data='back')]])
    await update.message.reply_text("Выберите действие:", reply_markup=keyboard)
    return None


async def monitor_wallets(context: ContextTypes.DEFAULT_TYPE):
    """Мониторинг - уведомление при ПРЕВЫШЕНИИ баланса 1500 USDT"""
    try:
        wallets = get_all_wallets()
        for user_id, wallet, network, last_balance, label in wallets:
            try:
                if network == 'TRC20':
                    result = get_usdt_balance_trc20(wallet, TRONGRID_API_KEY)
                else:
                    result = get_usdt_balance_erc20(wallet, ETHERSCAN_API_KEY)
                
                current_balance = result.balance
                
                # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: отправляем когда баланс ПРЕВЫСИЛ 1500
                # (а не когда пришла транзакция на 1500)
                if current_balance >= 1500 and last_balance < 1500:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🔔 *Уведомление!*\n\n"
                             f"Баланс превысил 1500 USDT!\n\n"
                             f"💰 Текущий баланс: *{current_balance:.2f} USDT*\n"
                             f"🏷️ Кошелёк: {label}\n"
                             f"🌐 Сеть: {network}\n"
                             f"📋 Адрес: `{wallet}`",
                        parse_mode='Markdown'
                    )
                
                # Всегда обновляем баланс в БД
                update_balance(user_id, wallet, network, current_balance)
            
            except Exception as e:
                logger.error(f"Ошибка мониторинга {wallet}: {e}")
                continue
    except Exception as e:
        logger.error(f"Ошибка мониторинга: {e}")


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
    
    # Мониторинг каждые 60 минут
    app.job_queue.run_repeating(monitor_wallets, interval=3600, first=60)
    
    print("✅ Бот запущен!")
    app.run_polling()


if __name__ == '__main__':
    main()

