import sqlite3
from datetime import datetime, timedelta

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = "8913643857:AAEnSvJp3TaAdslk3Tz_o8aAcW88rDwHTwM"

conn = sqlite3.connect(
    "students.db",
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name TEXT,
    lesson_time TEXT,
    chat_id INTEGER
)
""")

conn.commit()

keyboard = [
    ["📚 Предметы", "💵 Цены"],
    ["📅 Записаться", "📅 Расписание"],
    ["❓ Часто задаваемые вопросы", "📞 Контакты"],
]

reply_markup = ReplyKeyboardMarkup(
    keyboard,
    resize_keyboard=True
)

NAME, TIME = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Я бот-ассистент Санжара.",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📚 Предметы":
        reply = (
            "📚 Предметы:\n\n"
            "• Математика\n"
            "• Физика\n"
            "• Английский"
        )

    elif text == "💵 Цены":
        reply = (
            "💵 Цены:\n\n"
            "1 час — 7000 тг\n"
            "Пробный урок — бесплатно"
        )

    elif text == "📞 Контакты":
        reply = (
            "📞 Telegram: @yourusername"
        )

    elif text == "📅 Расписание":

        chat_id = update.effective_chat.id

        cursor.execute("""
        SELECT student_name, lesson_time
        FROM lessons
        WHERE chat_id = ?
        ORDER BY lesson_time
        """, (chat_id,))

        rows = cursor.fetchall()

        if not rows:
            reply = "📭 У вас нет записанных уроков."

        else:
            reply = "📚 Ваши уроки:\n\n"

            for row in rows:
                reply += (
                    f"👤 {row[0]}\n"
                    f"⏰ {row[1]}\n\n"
                )
    elif text == "❓ Часто задаваемые вопросы":

        reply = (
            "❓ Частые вопросы:\n\n"

            "1️⃣ Где проходят занятия?\n"
            "Онлайн в Telegram / Zoom / Google Meet.\n\n"

            "2️⃣ Сколько длится урок?\n"
            "Обычно 1 час.\n\n"

            "3️⃣ Можно ли перенести урок?\n"
            "Хз.\n\n"

            "4️⃣ Есть ли пробный урок?\n"
            "Тож Хз.\n\n"

            "5️⃣ Как записаться?\n"
            "Нажмите кнопку «📅 Записаться».\n\n"

            "6️⃣ Как посмотреть расписание?\n"
            "Нажмите кнопку «📅 Расписание»."
        )

    else:
        reply = "Выберите кнопку из меню."

    await update.message.reply_text(reply)

async def book_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👤 Введите ваше имя:"
    )

    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text

    await update.message.reply_text(
        "⏰ Введите дату и время урока.\n\n"
        "Примеры:\n"
        "2027-12-25 18:00\n"
        "25.12.2027 18:00"
    )

    return TIME

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    lesson_time = None

    formats = [
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M",
    ]

    for fmt in formats:
        try:
            lesson_time = datetime.strptime(text, fmt)
            break
        except ValueError:
            pass

    if lesson_time is None:
        await update.message.reply_text(
            "❌ Неверный формат.\n\n"
            "Примеры:\n"
            "2027-12-25 18:00\n"
            "25.12.2027 18:00"
        )

        return TIME

    if lesson_time <= datetime.now():
        await update.message.reply_text(
            "❌ Время должно быть в будущем."
        )

        return TIME

    cursor.execute("""
    SELECT lesson_time
    FROM lessons
    """)

    existing_lessons = cursor.fetchall()

    for row in existing_lessons:

        existing_time = datetime.strptime(
            row[0],
            "%Y-%m-%d %H:%M"
        )

        difference = abs(
            (lesson_time - existing_time).total_seconds()
        )

        if difference < 1800:
            await update.message.reply_text(
                "❌ Это время недоступно.\n\n"
                "Между уроками должно быть минимум 30 минут."
            )

            return TIME

    student = {
        "name": context.user_data["name"],
        "lesson_time": lesson_time,
        "chat_id": update.effective_chat.id
    }

    cursor.execute("""
    INSERT INTO lessons (
        student_name,
        lesson_time,
        chat_id
    )
    VALUES (?, ?, ?)
    """, (
        student["name"],
        lesson_time.strftime("%Y-%m-%d %H:%M"),
        student["chat_id"]
    ))

    conn.commit()

    try:
        reminder_time = lesson_time - timedelta(hours=1)

        context.job_queue.run_once(
            send_reminder,
            when=reminder_time,
            data=student,
            chat_id=student["chat_id"]
        )

    except Exception as e:
        print(e)

    await update.message.reply_text(
        f"✅ Вы записаны!\n\n"
        f"👤 {student['name']}\n"
        f"⏰ {lesson_time.strftime('%d.%m.%Y %H:%M')}"
    )

    return ConversationHandler.END

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    student = context.job.data

    await context.bot.send_message(
        chat_id=student["chat_id"],
        text=(
            f"⏰ Напоминание!\n\n"
            f"Ваш урок начнётся через 1 час."
        )
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Запись отменена."
    )

    return ConversationHandler.END

app = ApplicationBuilder().token(TOKEN).build()

booking_handler = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.Regex("^📅 Записаться$"),
            book_lesson
        )
    ],

    states={
        NAME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                get_name
            )
        ],

        TIME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                get_time
            )
        ],
    },

    fallbacks=[
        CommandHandler("cancel", cancel)
    ],
)

app.add_handler(CommandHandler("start", start))

app.add_handler(booking_handler)

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    )
)

print("Бот запущен...")

app.run_polling()