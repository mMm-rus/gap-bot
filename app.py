import os
import threading
from flask import Flask, request, jsonify
from google_schedule import get_availability
from maxbot_chatbot_python import Bot, Dispatcher, MapStateManager

app = Flask(__name__)

# Инициализация бота MAX
BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN")
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
dp.state_manager = MapStateManager(init_data={})

# Обработчик команды /свободен
@dp.message_created(lambda event: event.message.body.text.startswith("/свободен"))
async def availability_handler(event):
    text = event.message.body.text
    # Извлекаем дату из команды (например, /свободен 2026-09-10)
    parts = text.split()
    if len(parts) > 1:
        date = parts[1]
        result = get_availability(date)
        await event.message.answer(result)
    else:
        await event.message.answer("Укажите дату, например: /свободен 2026-09-10")

# Обработчик команды /помощь
@dp.message_created(lambda event: event.message.body.text == "/помощь")
async def help_handler(event):
    help_text = """
    Доступные команды:
    /свободен [дата] - проверить доступность
    /помощь - показать это сообщение
    """
    await event.message.answer(help_text)

# Flask endpoint для health check
@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

# Запуск бота в отдельном потоке
def run_bot():
    import asyncio
    # Используем Long Polling для простоты[citation:2][citation:10]
    asyncio.run(dp.start_polling(bot))

if __name__ == '__main__':
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    # Запускаем Flask для Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)