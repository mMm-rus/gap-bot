import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN")
BASE_URL = "https://platform-api2.max.ru"

HEADERS = {
    "Authorization": BOT_TOKEN
}


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
            timeout=10
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)