import os
import time
import threading
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
BOT_TOKEN = os.environ.get("f9LHodD0cOJfjaB0P9RQ4Aoq2pyZvxav3zgeGk_SfOx8aAxBkZ0HHhkSQaaXjQ7zXouJdInNM5yEDPUHKNel")
BASE_URL = "https://api.max.ru/v1/bots"


def send_message(chat_id, text):
    """Отправляет сообщение через API MAX."""
    url = f"{BASE_URL}/{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            print(f"Ошибка отправки: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Ошибка отправки: {e}")


def poll_messages():
    """Опрашивает новые сообщения."""
    last_update_id = 0
    while True:
        try:
            url = f"{BASE_URL}/{BOT_TOKEN}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 30}
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                updates = response.json()
                for update in updates.get("result", []):
                    last_update_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"].get("text", "")

                        if text == "/help":
                            send_message(chat_id, "Доступные команды: /help, /status, /свободен [дата]")
                        elif text == "/status":
                            send_message(chat_id, "Бот работает!")
                        elif text.startswith("/свободен"):
                            send_message(chat_id, f"Проверяем доступность для {text}... (функция временно не активна)")
                        else:
                            send_message(chat_id, f"Неизвестная команда. Напишите /help")
            else:
                print(f"Ошибка опроса: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Ошибка опроса: {e}")
        time.sleep(2)


# Запускаем опрос в фоновом потоке
if BOT_TOKEN:
    threading.Thread(target=poll_messages, daemon=True).start()
else:
    print("⚠️ ВНИМАНИЕ: MAX_BOT_TOKEN не найден! Бот не будет опрашивать сообщения.")


@app.route('/')
def home():
    return "GAP Bot is running!"


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик для Webhook (если будет работать)."""
    return jsonify({"status": "ok"}), 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)