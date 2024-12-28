import os
import requests
from flask import Flask, request, jsonify, redirect

# Flaskアプリケーションの初期化
app = Flask(__name__)

# LINE Works Bot API設定
CLIENT_ID = "FAKUIs1_C7TzbMG9ZoCp"  # 管理コンソールで取得
CLIENT_SECRET = "n6ugyKvfCf"  # 管理コンソールで取得
TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"
AUTH_URL = "https://auth.worksmobile.com/oauth2/v2.0/authorize"
API_URL = "https://www.worksapis.com/v1.0/bots/6807091/messages"  # BOT番号を含む
REDIRECT_URI = "https://line-works-bot-1.onrender.com/callback"  # 管理コンソールに登録
BOT_NO = "6807091"

# トークンキャッシュ
token_cache = {"access_token": None, "refresh_token": None, "expires_in": 0}

# 認可リクエストを生成するエンドポイント
@app.route("/authorize", methods=["GET"])
def authorize():
    auth_url = (
        f"{AUTH_URL}?"
        f"response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope=bot"
    )
    return redirect(auth_url)

# コールバックエンドポイント
@app.route("/callback", methods=["GET"])
def callback():
    auth_code = request.args.get("code")
    if not auth_code:
        return jsonify({"error": "Authorization code not found."}), 400

    token_data = get_access_token(auth_code)
    if token_data:
        token_cache["access_token"] = token_data.get("access_token")
        token_cache["refresh_token"] = token_data.get("refresh_token")
        token_cache["expires_in"] = token_data.get("expires_in")
        return jsonify({"message": "Access token obtained successfully.", "data": token_data}), 200
    else:
        return jsonify({"error": "Failed to fetch access token."}), 400

# アクセストークンを取得する関数
def get_access_token(auth_code):
    print("Fetching access token...")
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": auth_code
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        response = requests.post(TOKEN_URL, data=payload, headers=headers)
        print(f"Token request status code: {response.status_code}")
        print(f"Token request response: {response.text}")

        if response.status_code == 200:
            token_data = response.json()
            print("Access token fetched successfully.")
            return token_data
        else:
            print("Failed to fetch access token.")
            print(f"Error details: {response.text}")
            return None
    except Exception as e:
        print(f"Error during token request: {e}")
        return None

# アクセストークンの状態を確認するエンドポイント
@app.route("/check_token", methods=["GET"])
def check_token():
    if token_cache["access_token"]:
        return jsonify({
            "status": "ok",
            "access_token": token_cache["access_token"],
            "expires_in": token_cache["expires_in"]
        }), 200
    else:
        return jsonify({"status": "error", "message": "No access token available."}), 400

# リフレッシュトークンを使用してアクセストークンを更新する関数
def refresh_access_token():
    print("Refreshing access token...")
    if not token_cache.get("refresh_token"):
        print("No refresh token available. Please re-authorize.")
        # 再認証を要求
        return None

    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": token_cache["refresh_token"]
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        response = requests.post(TOKEN_URL, data=payload, headers=headers)
        print(f"Refresh token request status code: {response.status_code}")
        print(f"Refresh token request response: {response.text}")

        if response.status_code == 200:
            token_data = response.json()
            token_cache["access_token"] = token_data.get("access_token")
            token_cache["expires_in"] = token_data.get("expires_in")
            print("Access token refreshed successfully.")
            return token_data.get("access_token")
        else:
            print("Failed to refresh access token.")
            print(f"Error details: {response.text}")
            return None
    except Exception as e:
        print(f"Error during refresh token request: {e}")
        return None

# メッセージを送信する関数
def send_message(account_id, text):
    print("Preparing to send message...")
    access_token = token_cache.get("access_token")
    if not access_token:
        print("Access token is not available. Trying to refresh...")
        access_token = refresh_access_token()
        if not access_token:
            print("Failed to refresh access token. Cannot send message.")
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
        response = requests.post(API_URL, json=payload, headers=headers)
        print(f"Message send request status code: {response.status_code}")
        print(f"Message send request response: {response.text}")

        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print("Failed to send message. Check API response.")
    except Exception as e:
        print(f"Error during message send: {e}")

# Webhookエンドポイント
@app.route("/webhook", methods=["POST"])
def webhook():
    print("Webhook called.")
    try:
        data = request.json
        print(f"Received webhook data: {data}")

        if "content" in data and "text" in data["content"]:
            user_message = data["content"]["text"]
            reply_message = user_message  # オウム返し
            print(f"User message: {user_message}, Reply message: {reply_message}")

            if "source" in data and "userId" in data["source"]:
                user_id = data["source"]["userId"]
                send_message(user_id, reply_message)
            else:
                print("Error: Missing 'userId' in source data.")
        else:
            print("Webhook data does not contain expected 'content' or 'text' fields.")
    except Exception as e:
        print(f"Error in webhook processing: {e}")

    return jsonify({"status": "ok"}), 200

# アプリケーション起動
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "LINE Works Bot is running!"}), 200

if __name__ == "__main__":
    print("Starting Flask app on port 3000...")
    app.run(port=3000, debug=True, host="0.0.0.0")
