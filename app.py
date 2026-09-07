import os
import time
import threading
from flask import Flask, request, jsonify
from maxbot_api_client_python import MaxBotApi  #

app = Flask(__name__)

# Токен бота
BOT_TOKEN = os.environ.get("f9LHodD0cOLhLxIlbnaconuLVcqQD3gMi0Ocx9b4fgDqEmIJdzd9slHXlCaMBQjmhmQrOztl0xhOg6lRsIGa")

# Инициализация клиента
bot = MaxBotApi(BOT_TOKEN)

# Функция для опроса новых сообщений
def poll_messages():
    last_update_id = 0
    while True:
        try:
            updates = bot.get_updates(offset=last_update_id + 1, timeout=30)
            for update in updates:
                last_update_id = update['update_id']
                if 'message' in update:
                    chat_id = update['message']['chat']['id']
                    text = update['message'].get('text', '')
                    
                    # Обработка команд
                    if text == '/помощь':
                        bot.send_message(chat_id, "Доступные команды: /свободен [дата], /помощь")
                    elif text.startswith('/свободен'):
                        # Здесь вызов google_schedule.py
                        bot.send_message(chat_id, f"Проверяем доступность для {text}")
                    else:
                        bot.send_message(chat_id, "Неизвестная команда. Напишите /помощь")
        except Exception as e:
            print(f"Ошибка при опросе: {e}")
        time.sleep(2)

# Запуск опроса в фоновом потоке
threading.Thread(target=poll_messages, daemon=True).start()

# Flask-эндпоинты (для /health и /)
@app.route('/')
def home():
    return "GAP Bot is running!"

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)