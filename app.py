import os
import requests
from flask import Flask, jsonify, request
from google_schedule import (
    get_today_request_status,
    get_next_availability,
    get_shift_summary
)

app = Flask(__name__)

BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN")
BASE_URL = "https://platform-api2.max.ru"

HEADERS = {
    "Authorization": BOT_TOKEN
}

CA_BUNDLE = os.path.join(
    os.path.dirname(__file__),
    "certs",
    "mincit-ca-bundle.pem"
)

PROCESSED_MESSAGE_IDS = set()


@app.route("/")
def home():
    return "GAP Bot is running!"


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "token_configured": bool(BOT_TOKEN)
    })


@app.route("/test-max")
def test_max():
    if not BOT_TOKEN:
        return jsonify({
            "ok": False,
            "error": "MAX_BOT_TOKEN is not configured"
        }), 500

    try:
        response = requests.get(
            f"{BASE_URL}/me",
            headers=HEADERS,
            timeout=10,
            verify=CA_BUNDLE
        )

        return jsonify({
            "http_status": response.status_code,
            "response": response.json()
        }), response.status_code

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@app.route("/test-subscriptions")
def test_subscriptions():
    if not BOT_TOKEN:
        return jsonify({
            "ok": False,
            "error": "MAX_BOT_TOKEN is not configured"
        }), 500

    try:
        response = requests.get(
            f"{BASE_URL}/subscriptions",
            headers=HEADERS,
            timeout=10,
            verify=CA_BUNDLE
        )

        return jsonify({
            "http_status": response.status_code,
            "response": response.json()
        }), response.status_code

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@app.route("/setup-webhook")
def setup_webhook():
    if not BOT_TOKEN:
        return jsonify({
            "ok": False,
            "error": "MAX_BOT_TOKEN is not configured"
        }), 500

    try:
        webhook_secret = os.environ.get("WEBHOOK_SECRET")

        if not webhook_secret:
            return jsonify({
                "ok": False,
                "error": "WEBHOOK_SECRET is not configured"
            }), 500

        payload = {
            "url": "https://gap-bot-dunb.onrender.com/webhook",
            "update_types": [
                "message_created",
                "message_callback",
                "bot_started"
            ],
            "secret": webhook_secret
        }

        response = requests.post(
            f"{BASE_URL}/subscriptions",
            headers={
                **HEADERS,
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10,
            verify=CA_BUNDLE
        )

        return jsonify({
            "http_status": response.status_code,
            "response": response.json()
        }), response.status_code

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


def send_message(user_id, text, attachments=None):
    payload = {
        "text": text
    }

    if attachments:
        payload["attachments"] = attachments

    response = requests.post(
        f"{BASE_URL}/messages",
        params={
            "user_id": user_id
        },
        headers={
            **HEADERS,
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=10,
        verify=CA_BUNDLE
    )

    print(
        "MAX SEND:",
        response.status_code,
        response.text,
        flush=True
    )

    return response


def send_main_menu(user_id):
    attachments = [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "Заявка на производство",
                            "payload": "production_request"
                        }
                    ]
                ]
            }
        }
    ]

    return send_message(
        user_id,
        "Выберите действие:",
        attachments
    )


def answer_callback(callback_id, text):
    response = requests.post(
        f"{BASE_URL}/answers",
        params={
            "callback_id": callback_id
        },
        headers={
            **HEADERS,
            "Content-Type": "application/json"
        },
        json={
            "message": {
                "text": text
            }
        },
        timeout=10,
        verify=CA_BUNDLE
    )

    print(
        "MAX CALLBACK ANSWER:",
        response.status_code,
        response.text,
        flush=True
    )

    return response


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)

    print("MAX WEBHOOK:", data, flush=True)

    if not data:
        return jsonify({
            "ok": True
        }), 200

    # ========================================================
    # Нажатие inline-кнопки
    # ========================================================

    update_type = data.get("update_type")

    if update_type == "message_callback":
        callback = data.get("callback", {})
        callback_id = callback.get("callback_id")
        callback_payload = callback.get("payload")

        print(
            "MAX CALLBACK:",
            callback_id,
            callback_payload,
            flush=True
        )

        if callback_id:
            if callback_payload == "production_request":
                answer_callback(
                    callback_id,
                    "Заявка на производство: кнопка получена."
                )
            else:
                answer_callback(
                    callback_id,
                    "Кнопка получена."
                )

        return jsonify({
            "ok": True
        }), 200

    # ========================================================
    # Обычные сообщения
    # ========================================================

    message = data.get("message", {})
    sender = message.get("sender", {})

    if sender.get("is_bot") is True:
        print(
            "MAX WEBHOOK: ignoring bot message",
            flush=True
        )
        return jsonify({
            "ok": True
        }), 200

    body = message.get("body", {})
    text = body.get("text")
    mid = body.get("mid")

    if mid and mid in PROCESSED_MESSAGE_IDS:
        print(
            "MAX WEBHOOK: ignoring duplicate message",
            mid,
            flush=True
        )
        return jsonify({
            "ok": True
        }), 200

    sender_id = sender.get("user_id")
    chat_type = message.get("recipient", {}).get("chat_type")

    if text and sender_id and chat_type == "dialog":

        if text.strip() == "1":
            reply = get_today_request_status()

        elif text.strip() == "2":
            reply = get_next_availability()

        elif text.strip() == "0":
            reply = get_shift_summary()

        else:
            reply = f"Получил: {text}"

        response = send_message(
            sender_id,
            reply
        )

        if response.status_code == 200 and mid:
            PROCESSED_MESSAGE_IDS.add(mid)

    return jsonify({
        "ok": True
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

