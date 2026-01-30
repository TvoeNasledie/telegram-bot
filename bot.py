from dotenv import load_dotenv
load_dotenv()

import os
import logging
import re
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
NAME, CITY, PHONE, CONFIRM = range(4)

# Класс для работы с базой данных
class Database:
    def __init__(self, db_name="bot_database.db"):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    full_name TEXT NOT NULL,
                    city TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    status TEXT DEFAULT 'новая',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            conn.commit()
            logger.info("База данных создана")

    def add_user(self, user_id, username, first_name, last_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, join_date)
                VALUES (?, ?, ?, ?, COALESCE(
                    (SELECT join_date FROM users WHERE user_id = ?), 
                    CURRENT_TIMESTAMP
                ))
            ''', (user_id, username, first_name, last_name, user_id))
            conn.commit()
    
    def add_application(self, user_id, full_name, city, phone):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO applications (user_id, full_name, city, phone)
                VALUES (?, ?, ?, ?)
            ''', (user_id, full_name, city, phone))
            conn.commit()
            return cursor.lastrowid
    
    def get_user_applications(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM applications WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
            return cursor.fetchall()
    
    def get_application_count(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM applications')
            return cursor.fetchone()[0]

db = Database()

# Получаем переменные окружения
TOKEN = os.getenv('8252703334:AAHXBwrVZPtP6pds')
CHANNEL_ID_1 = os.getenv('CHANNEL_ID_1', '@vmodel_msk')
CHANNEL_ID_2 = os.getenv('CHANNEL_ID_2', '@x5courer')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '400730644'))

# Проверка подписки
async def check_subscription(user_id: int, channel_id: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        chat_member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

async def check_all_subscriptions(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    sub1 = await check_subscription(user_id, CHANNEL_ID_1, context)
    sub2 = await check_subscription(user_id, CHANNEL_ID_2, context)
    return sub1 and sub2

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    db.add_user(user_id, user.username, user.first_name, user.last_name)
    
    if await check_all_subscriptions(user_id, context):
        keyboard = [["📝 Оставить заявку", "📊 Мои заявки"], ["🔄 Проверить подписки", "📚 Помощь"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            "✅ Вы подписаны на все каналы!\n"
            "🎉 Теперь вы можете оставить заявку.\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
    else:
        status_text = f"Для использования бота подпишитесь на:\n1. {CHANNEL_ID_1}\n2. {CHANNEL_ID_2}\n\n"
        
        keyboard = [
            [
                InlineKeyboardButton("📢 Канал 1", url=f"https://t.me/{CHANNEL_ID_1[1:]}"),
                InlineKeyboardButton("📢 Канал 2", url=f"https://t.me/{CHANNEL_ID_2[1:]}")
            ],
            [InlineKeyboardButton("✅ Я подписался", callback_data="check_subs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n{status_text}После подписки нажмите кнопку ниже:",
            reply_markup=reply_markup
        )

async def check_subscriptions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if await check_all_subscriptions(user_id, context):
        await query.message.reply_text("✅ Отлично! Теперь вы можете пользоваться ботом.")
        keyboard = [["📝 Оставить заявку", "📊 Мои заявки"], ["🔄 Проверить подписки", "📚 Помощь"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    else:
        await query.message.reply_text("❌ Вы еще не подписались на все каналы. Пожалуйста, подпишитесь и проверьте снова.")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    sub1 = await check_subscription(user_id, CHANNEL_ID_1, context)
    sub2 = await check_subscription(user_id, CHANNEL_ID_2, context)
    
    text = "📊 Статус подписок:\n\n"
    text += f"1. {CHANNEL_ID_1}: {'✅ Подписан' if sub1 else '❌ Не подписан'}\n"
    text += f"2. {CHANNEL_ID_2}: {'✅ Подписан' if sub2 else '❌ Не подписан'}\n\n"
    
    if sub1 and sub2:
        text += "🎉 Вы подписаны на все каналы!"
    else:
        text += "Подпишитесь на недостающие каналы."
    
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 Справка по боту:\n\n"
        "/start - Начать работу\n"
        "/check - Проверить подписки\n"
        "/help - Эта справка\n"
        "/apply - Начать заявку\n\n"
        f"Каналы для подписки:\n1. {CHANNEL_ID_1}\n2. {CHANNEL_ID_2}"
    )
    await update.message.reply_text(text)

# Создание заявки
async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await check_all_subscriptions(user_id, context):
        await update.message.reply_text("❌ Для создания заявки необходимо подписаться на оба канала!")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 Создание заявки:\n\n"
        "1. Введите Имя и Фамилию (например: Иван Иванов):"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    
    if len(name.split()) < 2:
        await update.message.reply_text("❌ Введите имя и фамилию через пробел:")
        return NAME
    
    context.user_data['name'] = name
    await update.message.reply_text("✅ Принято!\n\n2. Введите ваш город:")
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text.strip()
    
    if len(city) < 2:
        await update.message.reply_text("❌ Город слишком короткий. Введите снова:")
        return CITY
    
    context.user_data['city'] = city
    await update.message.reply_text("✅ Принято!\n\n3. Введите номер телефона (например: +79991234567):")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    phone_pattern = r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
    
    if not re.match(phone_pattern, phone):
        await update.message.reply_text("❌ Неверный формат телефона. Введите снова:")
        return PHONE
    
    context.user_data['phone'] = phone
    
    name = context.user_data['name']
    city = context.user_data['city']
    
    keyboard = [["✅ Подтвердить", "❌ Отменить"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📋 Проверьте данные:\n\n1. {name}\n2. {city}\n3. {phone}\n\nВсё верно?",
        reply_markup=reply_markup
    )
    return CONFIRM

async def confirm_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if update.message.text == "❌ Отменить":
        context.user_data.clear()
        await update.message.reply_text("❌ Заявка отменена.")
        return ConversationHandler.END
    
    elif update.message.text == "✅ Подтвердить":
        name = context.user_data['name']
        city = context.user_data['city']
        phone = context.user_data['phone']
        
        application_id = db.add_application(user_id, name, city, phone)
        
        context.user_data.clear()
        
        await update.message.reply_text(
            f"🎉 Заявка #{application_id} создана!\n\n"
            f"Имя: {name}\nГород: {city}\nТелефон: {phone}\n\n"
            "Администратор свяжется с вами!"
        )
        
        return ConversationHandler.END
    
    return CONFIRM

async def cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Заявка отменена.")
    return ConversationHandler.END

# Обработчик сообщений
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "📊 Мои заявки":
        user_apps = db.get_user_applications(update.effective_user.id)
        if user_apps:
            response = "📋 Ваши заявки:\n\n"
            for app in user_apps:
                response += f"#{app['id']} - {app['full_name']} ({app['city']})\n"
        else:
            response = "📭 У вас нет заявок."
        
        await update.message.reply_text(response)
        
    elif text == "🔄 Проверить подписки":
        await check_command(update, context)
        
    elif text == "📚 Помощь":
        await help_command(update, context)

# Главная функция
def main():
    # Проверка обязательных переменных
    if not TOKEN:
        print("❌ ОШИБКА: Не задан TELEGRAM_BOT_TOKEN!")
        print("📝 Перейдите в Dashboard → Ваш сервис → Environment")
        print("   Добавьте переменную TELEGRAM_BOT_TOKEN")
        return
    
    print("=" * 50)
    print("🤖 ЗАПУСК ТЕЛЕГРАМ БОТА НА RENDER")
    print("=" * 50)
    print(f"🔗 Канал 1: {CHANNEL_ID_1}")
    print(f"🔗 Канал 2: {CHANNEL_ID_2}")
    print(f"👑 Админ ID: {ADMIN_USER_ID}")
    print(f"📊 Заявок в базе: {db.get_application_count()}")
    print("=" * 50)
    
    application = Application.builder().token(TOKEN).build()
    
    # ConversationHandler для заявок
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & filters.Regex("^📝 Оставить заявку$"), start_application),
            CommandHandler("apply", start_application)
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_application)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_application),
            MessageHandler(filters.Regex("^❌ Отменить$"), cancel_application)
        ],
    )
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(check_subscriptions_callback, pattern="^check_subs$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':

    main()


