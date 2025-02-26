import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
import re
import sqlite3
import asyncio
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

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
            [KeyboardButton(text="Добавить напоминание")],
            [KeyboardButton(text="Удалить напоминание")],
            [KeyboardButton(text="Список напоминаний")],
            [KeyboardButton(text="Команды")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    return keyboard

# Состояния для пошагового добавления и удаления напоминания
class ReminderStates(StatesGroup):
    WAITING_FOR_TEXT = State()  # Ожидание текста напоминания
    WAITING_FOR_DATETIME = State()  # Ожидание даты и времени
    WAITING_FOR_REMINDER_ID = State()  # Ожидание номера напоминания для удаления
    CONFIRM_DELETE = State()  # Ожидание подтверждения удаления

# Обработчик кнопки "/start"
@dp.message(lambda message: message.text == "/start")
async def start(message: types.Message):
    """Обработчик кнопки 'Начать'"""
    await message.reply(
        'Привет! Я бот-напоминание. Чтобы добавить напоминание, используйте кнопку '
        '"Добавить напоминание".\n\n'
        'Чтобы узнать все команды, нажмите "Команды".',
        reply_markup=get_command_keyboard()
    )

# Обработчик кнопки "Добавить напоминание"
@dp.message(lambda message: message.text == "Добавить напоминание")
async def remind(message: types.Message, state: FSMContext):
    logger.info("Обработчик 'Добавить напоминание' вызван")
    await message.reply("Введите текст напоминания:")
    await state.set_state(ReminderStates.WAITING_FOR_TEXT)

@dp.message(ReminderStates.WAITING_FOR_TEXT)
async def process_text(message: types.Message, state: FSMContext):
    logger.info("Обработчик 'WAITING_FOR_TEXT' вызван")
    await state.update_data(text=message.text)
    await message.reply("Теперь введите дату и время в формате YYYY-MM-DD HH:MM или просто время в формате HH:MM:")
    await state.set_state(ReminderStates.WAITING_FOR_DATETIME)

@dp.message(ReminderStates.WAITING_FOR_DATETIME)
async def process_datetime(message: types.Message, state: FSMContext):
    logger.info("Обработчик 'WAITING_FOR_DATETIME' вызван")
    user_data = await state.get_data()
    text = user_data.get("text")

    input_text = message.text.strip()
    datetime_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})$', input_text)
    time_match = re.search(r'(\d{2}:\d{2})$', input_text)

    if datetime_match:
        datetime_str = datetime_match.group(1)
        run_datetime = TZ.localize(datetime.strptime(datetime_str, '%Y-%m-%d %H:%M'))
    elif time_match:
        time_str = time_match.group(1)
        now = datetime.now(TZ)
        time_part = datetime.strptime(time_str, '%H:%M').time()
        run_datetime = TZ.localize(datetime.combine(now.date(), time_part))
    else:
        await message.reply("Формат даты и времени указан неверно. Пожалуйста, используйте формат YYYY-MM-DD HH:MM или HH:MM.")
        return

    if run_datetime <= datetime.now(TZ):
        await message.reply("Указанная дата и время уже прошли. Пожалуйста, укажите будущую дату и время.")
        return

    scheduler.add_job(
        send_reminder,
        trigger="date",
        run_date=run_datetime,
        args=(bot, message.chat.id, text),
    )
    add_reminder_to_db(message.chat.id, text, run_datetime)
    logger.info(f'Задача добавлена в планировщик: {run_datetime.strftime("%Y-%m-%d %H:%M")}')
    logger.info(f'Установлено новое напоминание: {text} в {run_datetime.strftime("%Y-%m-%d %H:%M")}')
    await message.reply(
        f'Напоминание установлено: {text} в {run_datetime.astimezone(TZ).strftime("%Y-%m-%d %H:%M")}',
        reply_markup=get_command_keyboard())
    await state.clear()

# Обработчик кнопки "Удалить напоминание"
@dp.message(lambda message: message.text == "Удалить напоминание")
async def cancel_reminder(message: types.Message, state: FSMContext):
    """Обработчик кнопки 'Удалить напоминание'"""
    reminders = get_reminders_from_db(message.chat.id)
    if not reminders:
        await message.reply("У вас нет активных напоминаний.", reply_markup=get_command_keyboard())
        return

    reply_text = "Вот ваши текущие напоминания. Введите номер напоминания, которое хотите удалить:\n"
    for i, (reminder_id, text, run_datetime) in enumerate(reminders):
        run_datetime = datetime.fromisoformat(run_datetime)
        reply_text += f"{i + 1}) {run_datetime.astimezone(TZ).strftime('%Y-%m-%d %H:%M')}: {text}\n"

    await message.reply(reply_text, reply_markup=get_command_keyboard())
    await state.set_state(ReminderStates.WAITING_FOR_REMINDER_ID)

# Обработчик кнопки "Список напоминаний"
@dp.message(lambda message: message.text == "Список напоминаний")
async def list_reminders(message: types.Message):
    """Обработчик кнопки 'Список напоминаний'"""
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

# Обработчик кнопки "Команды"
@dp.message(lambda message: message.text == "Команды")
async def help_command(message: types.Message):
    """Обработчик кнопки 'Команды'"""
    help_text = (
        "Я бот-напоминание. Вот список доступных действий:\n"
        "1. Добавить напоминание - установить новое напоминание.\n"
        "2. Удалить напоминание - удалить существующее напоминание.\n"
        "3. Список напоминаний - показать все активные напоминания.\n"
        "4. Команды - получить эту справку."
    )
    await message.reply(help_text, reply_markup=get_command_keyboard())

# Обработчик ввода номера напоминания для удаления
@dp.message(ReminderStates.WAITING_FOR_REMINDER_ID)
async def process_reminder_id(message: types.Message, state: FSMContext):
    """Обработка номера напоминания для удаления"""
    try:
        index = int(message.text.strip())
        reminders = get_reminders_from_db(message.chat.id)
        if 1 <= index <= len(reminders):
            reminder_id = reminders[index - 1][0]
            await state.update_data(reminder_id=reminder_id)  # Сохраняем ID напоминания
            await message.reply(
                f"Вы уверены, что хотите удалить напоминание под номером {index}? (да/нет)",
                reply_markup=get_command_keyboard()
            )
            await state.set_state(ReminderStates.CONFIRM_DELETE)
        else:
            await message.reply("Неверный номер напоминания. Пожалуйста, попробуйте снова.", reply_markup=get_command_keyboard())
    except ValueError:
        await message.reply("Пожалуйста, введите число.", reply_markup=get_command_keyboard())

# Обработчик подтверждения удаления
@dp.message(ReminderStates.CONFIRM_DELETE)
async def confirm_delete(message: types.Message, state: FSMContext):
    """Обработка подтверждения удаления"""
    user_data = await state.get_data()
    reminder_id = user_data.get("reminder_id")

    if message.text.lower() == "да":
        remove_reminder_from_db(reminder_id)
        await message.reply("Напоминание успешно удалено.", reply_markup=get_command_keyboard())
    else:
        await message.reply("Удаление отменено.", reply_markup=get_command_keyboard())

    await state.clear()  # Завершаем процесс

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
