import os
import requests
from flask import Flask, request, jsonify

# Flaskアプリケーションの初期化
app = Flask(__name__)

# LINE Works Bot API設定
CLIENT_ID = "FAKUIs1_C7TzbMG9ZoCp"  # 管理画面で取得
CLIENT_SECRET = "n6ugyKvfCf"  # 管理画面で取得
TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"
BOT_NO = "6807091"  # Botの番号
API_URL = f"https://www.worksapis.com/v1.0/bots/{BOT_NO}/messages"


# トークンを取得する関数
def get_access_token():
    print("Fetching access token...")
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "bot"
    }
    try:
        response = requests.post(TOKEN_URL, data=payload)
        print(f"Token request status code: {response.status_code}")
        print(f"Token request response: {response.text}")

        if response.status_code == 200:
            token_data = response.json()
            print("Access token fetched successfully.")
            return token_data.get("access_token")
        else:
            print("Failed to fetch access token.")
            return None
    except Exception as e:
        print(f"Error during token request: {e}")
        return None


# Webhookエンドポイント
@app.route("/webhook", methods=["POST"])
def webhook():
    print("Webhook called.")
    try:
        # ユーザーからのメッセージを受信
        data = request.json
        print(f"Received webhook data: {data}")

        if "content" in data and "text" in data["content"]:
            user_message = data["content"]["text"]
            reply_message = user_message  # オウム返し
            print(f"User message: {user_message}, Reply message: {reply_message}")

            # メッセージ送信
            send_message(data["source"]["accountId"], reply_message)
        else:
            print("Webhook data does not contain expected 'content' or 'text' fields.")
    except Exception as e:
        print(f"Error in webhook processing: {e}")

    return jsonify({"status": "ok"}), 200


# メッセージを送信する関数
def send_message(account_id, text):
    print("Sending message...")
    access_token = get_access_token()
    if not access_token:
        print("Error: Unable to retrieve access token.")
        return

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "botNo": BOT_NO,
        "accountId": account_id,
        "content": {
            "type": "text",
            "text": text
        }
    }
    try:
        print(f"Message payload: {payload}")
        response = requests.post(API_URL, headers=headers, json=payload)
        print(f"Message send status code: {response.status_code}")
        print(f"Message send response: {response.text}")

        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print("Failed to send message.")
    except Exception as e:
        print(f"Error during message send: {e}")


# ルートエンドポイント
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "GET":
        return jsonify({"status": "ok", "message": "LINE Works Bot is running!"}), 200
    elif request.method == "POST":
        return jsonify({"status": "ok", "message": "POST request received!"}), 200


# アプリケーション起動
if __name__ == "__main__":
    print("Starting Flask app on port 3000...")
    app.run(port=3000, debug=True, host="0.0.0.0")
