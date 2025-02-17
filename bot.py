import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
import re
import sqlite3
import asyncio


# Настройка логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Указываем временную зону по умолчанию
TZ = timezone('Europe/Samara')

# Регулярное выражение для проверки формата времени (HH:MM)
TIME_FORMAT_REGEX = re.compile(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')

# Регулярное выражение для проверки формата даты и времени (YYYY-MM-DD HH:MM)
DATETIME_FORMAT_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')

# Инициализация бота и диспетчера
API_TOKEN = 'Api_token'  # Замените на ваш токен
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация планировщика
scheduler = AsyncIOScheduler(timezone=TZ)

# Инициализация базы данных
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  chat_id INTEGER,
                  text TEXT,
                  run_datetime TEXT)''')
    conn.commit()
    conn.close()

# Добавление напоминания в базу данных
def add_reminder_to_db(chat_id, text, run_datetime):
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("INSERT INTO reminders (chat_id, text, run_datetime) VALUES (?, ?, ?)",
              (chat_id, text, run_datetime.isoformat()))
    conn.commit()
    conn.close()
    logger.info(f"Напоминание добавлено в базу данных: {text} в {run_datetime}")

# Получение напоминаний из базы данных
def get_reminders_from_db(chat_id):
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT id, text, run_datetime FROM reminders WHERE chat_id=?", (chat_id,))
    reminders = c.fetchall()
    conn.close()
    return reminders

# Удаление напоминания из базы данных
def remove_reminder_from_db(reminder_id):
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()

# Удаление устаревших напоминаний из базы данных
def remove_old_reminders(chat_id, run_datetime_str):
    """Удаление устаревших напоминаний из базы данных"""
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("DELETE FROM reminders WHERE chat_id=? AND run_datetime=?", (chat_id, run_datetime_str))
    conn.commit()
    conn.close()

# Восстановление задач из базы данных
async def restore_reminders():
    """Восстановление задач из базы данных в планировщик"""
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT chat_id, text, run_datetime FROM reminders")
    reminders = c.fetchall()
    conn.close()

    for chat_id, text, run_datetime_str in reminders:
        run_datetime = datetime.fromisoformat(run_datetime_str)
        # Проверяем, не прошло ли уже время напоминания
        if run_datetime > datetime.now(TZ):
            scheduler.add_job(
                send_reminder,
                trigger="date",
                run_date=run_datetime,
                args=(bot, chat_id, text),
            )
            logger.info(f"Восстановлено напоминание: {text} в {run_datetime.strftime('%Y-%m-%d %H:%M')}")
        else:
            # Если время напоминания уже прошло, удаляем его из базы данных
            remove_old_reminders(chat_id, run_datetime_str)
            logger.info(f"Удалено устаревшее напоминание: {text} в {run_datetime.strftime('%Y-%m-%d %H:%M')}")

# Функция для проверки формата времени (HH:MM)
def validate_time_format(time_str):
    if TIME_FORMAT_REGEX.match(time_str):
        return True
    return False

# Функция для проверки формата даты и времени (YYYY-MM-DD HH:MM)
def validate_datetime_format(datetime_str):
    if DATETIME_FORMAT_REGEX.match(datetime_str):
        return True
    return False

# Создаем клавиатуру с кнопками
def get_command_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/start")],
            [KeyboardButton(text="/help")],
            [KeyboardButton(text="/list")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    return keyboard

@dp.message(Command("start"))
async def start(message: types.Message):
    """Обработчик команды /start"""
    await message.reply(
        'Привет! Я бот-напоминание. Чтобы добавить напоминание, используйте команду '
        '/remind "текст напоминания" YYYY-MM-DD HH:MM\n\n'
        'Если дата не указана, будет использоваться сегодняшняя дата.\n\n'
        'Чтобы узнать все команды, введите /help.',
        reply_markup=get_command_keyboard()
    )

@dp.message(Command("help"))
async def help_command(message: types.Message):
    """Обработчик команды /help"""
    help_text = (
        "Я бот-напоминание. Вот список моих команд:\n"
        "/start - начать работу со мной.\n"
        "/remind \"текст напоминания\" YYYY-MM-DD HH:MM - установить напоминание.\n"
        "/list - показать список текущих напоминаний.\n"
        "/cancel номер_напоминания - удалить конкретное напоминание.\n"
        "/help - получить эту справку."
    )
    await message.reply(help_text, reply_markup=get_command_keyboard())

@dp.message(Command("remind"))
async def remind(message: types.Message):
    """Обработчик команды /remind"""
    chat_id = message.chat.id

    try:
        # Убираем команду /remind из текста сообщения
        args = message.text.split(maxsplit=1)  # Разделяем на 2 части: команда и остальное
        if len(args) < 2:
            await message.reply("Не хватает аргументов. Используйте команду в формате: "
                               "/remind текст напоминания YYYY-MM-DD HH:MM или /remind текст напоминания HH:MM",
                               reply_markup=get_command_keyboard())
            return

        # Ищем дату и время в конце строки
        input_text = args[1].strip()
        datetime_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})$', input_text)  # Ищем дату и время в формате YYYY-MM-DD HH:MM
        time_match = re.search(r'(\d{2}:\d{2})$', input_text)  # Ищем время в формате HH:MM

        if datetime_match:
            # Если найдена полная дата и время
            datetime_str = datetime_match.group(1)
            text = input_text[:datetime_match.start()].strip()  # Текст до даты/времени
            run_datetime = TZ.localize(datetime.strptime(datetime_str, '%Y-%m-%d %H:%M'))
        elif time_match:
            # Если найдено только время
            time_str = time_match.group(1)
            text = input_text[:time_match.start()].strip()  # Текст до времени
            now = datetime.now(TZ)
            time_part = datetime.strptime(time_str, '%H:%M').time()
            run_datetime = TZ.localize(datetime.combine(now.date(), time_part))
        else:
            await message.reply("Формат даты и времени указан неверно. Пожалуйста, используйте формат YYYY-MM-DD HH:MM или HH:MM.",
                               reply_markup=get_command_keyboard())
            return

        # Проверяем, что дата и время не в прошлом
        if run_datetime <= datetime.now(TZ):
            await message.reply("Указанная дата и время уже прошли. Пожалуйста, укажите будущую дату и время.",
                                reply_markup=get_command_keyboard())
            return

        # Добавляем задачу в планировщик
        scheduler.add_job(
            send_reminder,
            trigger="date",
            run_date=run_datetime,
            args=(bot, chat_id, text),
        )
        # Добавляем напоминание в базу данных
        add_reminder_to_db(chat_id, text, run_datetime)
        logger.info(f'Задача добавлена в планировщик: {run_datetime.strftime("%Y-%m-%d %H:%M")}')
        logger.info(f'Установлено новое напоминание: {text} в {run_datetime.strftime("%Y-%m-%d %H:%M")}')
        await message.reply(
            f'Напоминание установлено: {text} в {run_datetime.astimezone(TZ).strftime("%Y-%m-%d %H:%M")}',
            reply_markup=get_command_keyboard())
    except Exception as e:
        logger.error(f"Произошла ошибка при создании задачи: {e}")
        await message.reply("Не удалось создать напоминание. Попробуйте позже.", reply_markup=get_command_keyboard())

@dp.message(Command("list"))
async def list_reminders(message: types.Message):
    """Обработчик команды /list"""
    chat_id = message.chat.id

    reminders = get_reminders_from_db(chat_id)

    if reminders:
        reply_text = "Вот ваши текущие напоминания:\n"
        for i, (reminder_id, text, run_datetime) in enumerate(reminders):
            run_datetime = datetime.fromisoformat(run_datetime)
            reply_text += f"{i + 1}) {run_datetime.astimezone(TZ).strftime('%Y-%m-%d %H:%M')}: {text}\n"
    else:
        reply_text = "У вас нет активных напоминаний."

    await message.reply(reply_text, reply_markup=get_command_keyboard())

@dp.message(Command("cancel"))
async def cancel_reminder(message: types.Message):
    """Обработчик команды /cancel"""
    chat_id = message.chat.id
    args = message.text.split()

    if len(args) > 1:
        index = args[1].strip()
        if index.isdigit():
            index = int(index)
            reminders = get_reminders_from_db(chat_id)
            if 1 <= index <= len(reminders):
                reminder_id = reminders[index - 1][0]
                remove_reminder_from_db(reminder_id)
                await message.reply(f"Напоминание под номером {index} было успешно удалено.", reply_markup=get_command_keyboard())
            else:
                await message.reply(f"Не удалось найти напоминание под номером {index}.", reply_markup=get_command_keyboard())
        else:
            await message.reply("Номер напоминания должен быть числом.", reply_markup=get_command_keyboard())
    else:
        await message.reply("Пожалуйста, укажите номер напоминания, которое хотите отменить.", reply_markup=get_command_keyboard())

async def send_reminder(bot: Bot, chat_id: int, text: str):
    """Функция отправки напоминания"""
    try:
        await bot.send_message(chat_id=chat_id, text=f'Напоминание: {text}', reply_markup=get_command_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")

async def main():
    # Инициализация базы данных
    init_db()

    # Восстановление задач из базы данных
    await restore_reminders()

    # Запуск планировщика
    scheduler.start()

    # Запуск бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
