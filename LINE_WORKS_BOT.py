import os
import requests
from flask import Flask, request, jsonify, redirect

# Flaskアプリケーションの初期化
app = Flask(__name__)

# LINE Works Bot API設定
CLIENT_ID = "FAKUIs1_C7TzbMG9ZoCp"  # 管理画面で取得
CLIENT_SECRET = "n6ugyKvfCf"  # 管理画面で取得
TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"
REDIRECT_URI = "http://localhost:3000/callback"  # 必ず管理コンソールに登録

# グローバルキャッシュ
token_cache = {"access_token": None, "refresh_token": None, "expires_in": 0}

# 認可リクエストを生成するエンドポイント
@app.route("/authorize", methods=["GET"])
def authorize():
    auth_url = (
        f"https://auth.worksmobile.com/oauth2/v2.0/authorize?"
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
            return response.json()
        else:
            print("Failed to fetch access token.")
            return None
    except Exception as e:
        print(f"Error during token request: {e}")
        return None

# リフレッシュトークンを使用してアクセストークンを更新する関数
def refresh_access_token():
    print("Refreshing access token...")
    if not token_cache.get("refresh_token"):
        print("No refresh token available.")
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
            return token_data
        else:
            print("Failed to refresh access token.")
            return None
    except Exception as e:
        print(f"Error during refresh token request: {e}")
        return None

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

            # Webhookでは特に応答しない
        else:
            print("Webhook data does not contain expected 'content' or 'text' fields.")
    except Exception as e:
        print(f"Error in webhook processing: {e}")

    return jsonify({"status": "ok"}), 200

# アプリケーション起動
if __name__ == "__main__":
    print("Starting Flask app on port 3000...")
    app.run(port=3000, debug=True, host="0.0.0.0")
