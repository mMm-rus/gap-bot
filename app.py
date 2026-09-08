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


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)

    print("MAX WEBHOOK:", data, flush=True)

    if not data:
        return jsonify({
            "ok": True
        }), 200

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

        response = requests.post(
            f"{BASE_URL}/messages",
            params={
                "user_id": sender_id
            },
            headers={
                **HEADERS,
                "Content-Type": "application/json"
            },
            json={
                "text": reply
            },
            timeout=10,
            verify=CA_BUNDLE
        )

        print(
            "MAX SEND:",
            response.status_code,
            response.text,
            flush=True
        )

        if response.status_code == 200 and mid:
            PROCESSED_MESSAGE_IDS.add(mid)

    return jsonify({
        "ok": True
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)