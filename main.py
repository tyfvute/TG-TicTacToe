import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from pytz import timezone
import re

# Настройка логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Указываем временную зону по умолчанию
TZ = timezone('Asia/Yekaterinburg')

# Регулярное выражение для проверки формата времени
TIME_FORMAT_REGEX = re.compile(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')


# Функция для проверки формата времени
def validate_time_format(time_str):
    if TIME_FORMAT_REGEX.match(time_str):
        return True
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        'Привет! Я бот-напоминание. Чтобы добавить напоминание, используйте команду '
        '/remind "текст напоминания" HH:MM\n\n'
    )


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /remind"""
    chat_id = update.effective_chat.id

    if len(context.args) < 2:
        await update.message.reply_text("Не хватает аргументов. Используйте команду в формате: "
                                        "/remind \"текст напоминания\" HH:MM")
        return

    args = context.args
    text = ' '.join(args[:-1])
    time_str = args[-1]

    if not validate_time_format(time_str):
        await update.message.reply_text("Время указано неверно. Пожалуйста, используйте формат HH:MM.")
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

        # Добавляем задачу в очередь
        try:
            job = context.job_queue.run_once(send_reminder, run_datetime.timestamp(),
                                             data={'chat_id': chat_id, 'text': text}, name=str(chat_id))
            logger.info(f'Задача добавлена в очередь: {job.name} ({job.next_t})')
            logger.info(f'Установлено новое напоминание: {text} в {run_datetime.strftime("%Y-%m-%d %H:%M")}')
            await update.message.reply_text(
                f'Напоминание установлено: {text} в {run_datetime.astimezone(TZ).strftime("%H:%M")}')
        except Exception as e:
            logger.error(f"Произошла ошибка при создании задачи: {e}")
            await update.message.reply_text(f"Не удалось создать напоминание. Попробуйте позже.")

    except ValueError as e:
        logger.error(f"Произошла ошибка при обработке данных: {e}")
        await update.message.reply_text(f"Некорректные данные: {str(e)}. Попробуйте еще раз.")


async def cancel_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel"""
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))

    if not jobs:
        await update.message.reply_text("У вас нет активных напоминаний.")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("Все ваши напоминания были отменены.")


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Функция отправки напоминания"""
    job = context.job
    try:
        await context.bot.send_message(chat_id=job.data['chat_id'], text=f'Напоминание: {job.data["text"]}')
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")


def main():
    app = ApplicationBuilder().token("Token_bot").build()

    start_handler = CommandHandler('start', start)
    remind_handler = CommandHandler('remind', remind)
    cancel_handler = CommandHandler('cancel', cancel_reminder)

    app.add_handler(start_handler)
    app.add_handler(remind_handler)
    app.add_handler(cancel_handler)

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == '__main__':
    main()

