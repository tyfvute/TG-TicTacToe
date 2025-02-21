**⏳ TelegramReminderBot @ReminderBotVeryUsefull**
=
>Бот-напоминание для Telegram.
>Этот бот предназначен для создания и управления напоминаниями через Telegram. Пользователи могут установить напоминания на определённое время, а затем получать уведомления в нужный момент.

Комманды:
-
- /start (Команда для начала взаимодействия с ботом. Она выводит краткую информацию о том, как пользоваться ботом)
- /reminder (Устанавливает напоминание на заданное время. Время должно быть указано в формате YYYY-MM-DD HH:MM)
- /cancel (Эта команда отменяет все установленные напоминания)
- /list (Показывает список напоминаний)
- /help (Показывает все команды)

Пример использования:
-
1. Отправьте команду /start, чтобы начать работу с ботом.
2. Используйте команду /remind "текст напоминания" YYYY-MM-DD HH:MM для установки напоминания.
3. Когда наступит установленное время, бот пришлёт вам уведомление с текстом напоминания.
4. Вы можете отменить все свои напоминания командой /cancel.

Технологии:
-

- Бот сохраняет данные в базу данных SQLite
- logging — для логирования событий.
- datetime и timedelta — для работы с датами и временем.
- aiogram — для создания и управления Telegram-ботом.
- apscheduler — для планирования напоминаний.
- pytz — для работы с временными зонами.
- re — для проверки формата времени.
- asyncio — для асинхронного выполнения задач.

**Установка:**
-

1. Скопируйте репозиторий.

       git clone https://github.com/tyfvute/TG-ReminderBot
       cd TG-ReminderBot

3. Для запуска бота, вам надо установить библиотеки:

       pip install aiogram

       pip install apscheduler

       pip install pytz

4. Замените в коде токен:

>В файле `bot.py` замените `API_TOKEN = 'Api_token'` на свой токен.

4. Запустите бота через терминал:

       python bot.py
      
