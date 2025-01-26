import telebot;
bot = telebot.TeleBot('');
@bot.message_handler(content_types=['text'])
def get_text_messages(message):
if message.text == "/start":
    bot.send_message(message.from_user.id, "Привет, если хочешь начать новую игру, напиши /new game.") 
