import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
import re

# Настройка логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Указываем временную зону по умолчанию
TZ = timezone('Europe/Samara')

# Регулярное выражение для проверки формата времени
TIME_FORMAT_REGEX = re.compile(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')

# Инициализация бота и диспетчера
API_TOKEN = 'Api_token'
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация планировщика
scheduler = AsyncIOScheduler(timezone=TZ)

# Функция для проверки формата времени
def validate_time_format(time_str):
    if TIME_FORMAT_REGEX.match(time_str):
        return True
    return False

@dp.message(Command("start"))
async def start(message: types.Message):
    """Обработчик команды /start"""
    await message.reply(
        'Привет! Я бот-напоминание. Чтобы добавить напоминание, используйте команду '
        '/remind "текст напоминания" HH:MM\n\n '
        'а если хочешь узнать все команды введи команду /help'
    )

    @dp.message(Command("help"))
    async def help_command(message: types.Message):
        """Обработчик команды /help"""
        help_text = (
            "Я бот-напоминание. Вот список моих команд:\n"
            "/start - начать работу со мной.\n"
            "/remind \"текст напоминания\" HH:MM - установить напоминание.\n"
            "/list - показать список текущих напоминаний.\n"
            "/cancel номер_напоминания - удалить конкретное напоминание.\n"
            "/help - получить эту справку."
        )
        await message.reply(help_text)

@dp.message(Command("remind"))
async def remind(message: types.Message):
    """Обработчик команды /remind"""
    chat_id = message.chat.id

    args = message.text.split()[1:]
    if len(args) < 2:
        await message.reply("Не хватает аргументов. Используйте команду в формате: "
                            "/remind \"текст напоминания\" HH:MM")
        return

    text = ' '.join(args[:-1])
    time_str = args[-1]

    if not validate_time_format(time_str):
        await message.reply("Время указано неверно. Пожалуйста, используйте формат HH:MM.")
        return

    try:
        # Проверяем, что текст не пустой
        if not text.strip():
            raise ValueError("Текст напоминания не должен быть пустым")

        # Получаем текущее время в нужной временной зоне
        now = datetime.now(TZ)
        today = now.date()

        # Преобразуем введенное время в объект datetime
        time_obj = datetime.strptime(time_str, '%H:%M').time()

        # Создаем объект datetime с сегодняшней датой и указанным временем
        run_datetime = TZ.localize(datetime.combine(today, time_obj))

        # Если время уже прошло, добавляем один день
        if run_datetime <= now:
            run_datetime += timedelta(days=1)

        logger.info(f"Текущее время: {now}")
        logger.info(f"Время напоминания: {run_datetime}")
        logger.info(f"Временная метка для задачи: {run_datetime.timestamp()}")

        # Добавляем задачу в планировщик
        try:
            scheduler.add_job(
                send_reminder,
                trigger="date",
                run_date=run_datetime,
                args=(bot, chat_id, text),
            )
            logger.info(f'Задача добавлена в планировщик: {run_datetime.strftime("%Y-%m-%d %H:%M")}')
            logger.info(f'Установлено новое напоминание: {text} в {run_datetime.strftime("%Y-%m-%d %H:%M")}')
            await message.reply(
                f'Напоминание установлено: {text} в {run_datetime.astimezone(TZ).strftime("%H:%M")}')
        except Exception as e:
            logger.error(f"Произошла ошибка при создании задачи: {e}")
            await message.reply("Не удалось создать напоминание. Попробуйте позже.")

    except ValueError as e:
        logger.error(f"Произошла ошибка при обработке данных: {e}")
        await message.reply(f"Некорректные данные: {str(e)}. Попробуйте еще раз.")

@dp.message(Command("list"))
async def list_reminders(message: types.Message):
    """Обработчик команды /list"""
    chat_id = message.chat.id

    jobs = scheduler.get_jobs()
    reminders = []

    for i, job in enumerate(jobs):
        if job.args[1] == chat_id:  # Проверяем, что задача принадлежит этому пользователю
            run_date = job.next_run_time.astimezone(TZ)
            text = job.args[2]
            reminders.append(f"{i + 1}) {run_date.strftime('%Y-%m-%d %H:%M')}: {text}")

    if reminders:
        reply_text = "Вот ваши текущие напоминания:\n"
        reply_text += "\n".join(reminders)
    else:
        reply_text = "У вас нет активных напоминаний."

    await message.reply(reply_text)

@dp.message(Command("cancel"))
async def cancel_reminder(message: types.Message):
    """Обработчик команды /cancel"""
    chat_id = message.chat.id
    args = message.text.split()

    if len(args) > 1:
        index = args[1].strip()
        if index.isdigit():
            index = int(index)
            removed = remove_reminder_by_index(scheduler, chat_id, index)
            if removed:
                await message.reply(f"Напоминание под номером {index} было успешно удалено.")
            else:
                await message.reply(f"Не удалось найти напоминание под номером {index}.")
        else:
            await message.reply("Номер напоминания должен быть числом.")
    else:
        await message.reply("Пожалуйста, укажите номер напоминания, которое хотите отменить.")

def remove_reminder_by_index(scheduler, chat_id, index):
    jobs = scheduler.get_jobs()
    user_jobs = [job for job in jobs if job.args[1] == chat_id]

    if index < 1 or index > len(user_jobs):
        return False

    job_to_remove = user_jobs[index - 1]
    job_to_remove.remove()
    return True

async def send_reminder(bot: Bot, chat_id: int, text: str):
    """Функция отправки напоминания"""
    try:
        await bot.send_message(chat_id=chat_id, text=f'Напоминание: {text}')
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")

if __name__ == '__main__':
    import asyncio

    async def main():
        # Запуск планировщика
        scheduler.start()
        # Запуск бота
        await dp.start_polling(bot)

    asyncio.run(main())
