﻿import os
import time
import jwt  # PyJWTライブラリを使用
import requests
from flask import Flask, request, jsonify, redirect

# Flaskアプリケーションの初期化
app = Flask(__name__)

# LINE Works Bot API設定
CLIENT_ID = "FAKUIs1_C7TzbMG9ZoCp"  # 管理画面で取得
CLIENT_SECRET = "n6ugyKvfCf"  # 管理画面で取得
PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7BP6/i48ra5BA
qqj8IowXH1DvyfYbDiEx8x3a+pkiTJ55rfCyrDVrtww0fxORNPXf3EEGvqF6nE6l
GshPw41gGLRFMwo151Egg9+PQMQdoTSJ2Nv1KbO3Hu5FwEnAcgUwhPeUMpbAg/kl
fQQASE9lGKfWO0sSIikQHQwiMfVcb938HzFwjm/SizJIUQkXIxcBwUg4qs2qTuUD
psburLha5YLsvpR8diK9EYh4NyYmpOE7TtxlSVz6/0ZWlgi2pbfYaqjEW+vgLWbf
PK7zepuCHTsNwYqDKsy5x0Qb2EJ8AzGKUtrzmBlxfnMk3iBRH4+XV7erH3Fxrvni
uQAu47PRAgMBAAECggEAF76mcim6d5VUadl2fhi2zQLACHSNx4PvlANy5sggJDoy
eW7WW3Zri+21jNQWPGlLJG03C6+tbz9O6ZMxG+t5/4RIyGvBX/RVbmQ/61TE8aFz
kGLqaRdZMXv/CE0bMBC/TEM9meEjFyCfw/I6TVI2U7bMgcc3x1Qd/uU+kqLhglGc
IbMx7/nJvJApl8WTiPLQvp4btYlUvjUCA/MV0dtYqY3SwuCqvOEKaX+HEYQwY0jT
IiQ+mf2nC+OWhfSXBf3QERaRf8ESKIvb0w6fnTHRVnutyxW/QgFDcrhBEO1NIlU8
qdMIUyG7SKc0eRuNr6aNL2N2lMDpvwXeZ9JxNaaGXwKBgQDTYxvenj/t2ttkCRib
v7/6zcYOyuQqk2k7AfN6H98SeQJBr1BQdkd9CLbwGEESeg7ZhjmTUB0om13h4oZc
kw9pPc0uRyLXyYyOiku/e+I6C3AY2AVO7bOBLy+28VZOfoQlAYHTVlX8JuDdIKSN
oZ+MnBkRDCxw9QgYpB/YWaUSPwKBgQDifVgbDXfZ0dj0qRd/djwc/qm66fj2Pnml
xcEsIs4fz8rje/Ry39wKncSswt3SGNCYk3Bhtsopdza0BgcZfVo4DjBs2D4SBgD5
BK8jAY2A/qgz2e7XwA0Cfif//XB17Uqngbv52gUJNGhrD/38POjKc1II0yzJLn33
3K3umZeV7wKBgEVzXoi5vY9MRKCNTIR/b3fbe6MIjgZfAEfe0DvjlMrg7xjdnKmS
8tHltxUTIu4LJC3bp7b6r1nUEfhREIwB1SJip7L4tD3pfkCmt1RmQ2GGuIGxF61i
84MSGb8lc5G+h3QRFrJ0vzNlIqQEQYw2+dCcyK+NLFzAZLST19KhQVbJAoGAWjrv
Z8+kyL1GPqpCtz/mUPLPsaxWx9s54WX4QFoZXikNPjV6vG0cn4oc+Wqkrne+Wpqa
cgM9ZOmefHfOSkRbNevJNQOtLsb/ijVohHyw4AwT/Jw8/+z+Adk6nExeikyfqj4Q
IkjOKs2bL9PuLpghcc4hh2yB8iA4hQ+Ap4a/EjcCgYEAzYBmuYAnIKbjX7YXq14V
EeND4wdbQSCD9sZsqTYgG2ABUiZgDPidrzk2qZr4h84xWbwcZ2vrO4RnzttDW3iP
8qPQ8P0ANZFE58h2XZ/LKMRmsdSfDdwBNus+mRmn1MkrjHlI1H1d52AXEYYJlJgs
mBXhkKChqlSeWD14yuTCCE0=
-----END PRIVATE KEY-----"""  # 管理コンソールで生成された秘密鍵
ISS = "d7ya7.serviceaccount@reichan"  # 管理画面で確認 (Service Account ID)
TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"
API_URL = "https://www.worksapis.com/v1.0/bots/6807091/messages"  # BOT番号を含む
BOT_NO = "6807091"

# トークンキャッシュ
token_cache = {"access_token": None, "refresh_token": None, "expires_in": 0}

# JWTを生成する関数
def create_jwt():
    print("Creating JWT...")
    now = int(time.time())
    payload = {
        "iss": ISS,  # Service Account ID
        "sub": ISS,  # 同じくService Account ID
        "iat": now,  # 現在のタイムスタンプ
        "exp": now + 3600,  # 1時間後の有効期限
        "aud": TOKEN_URL  # トークン取得エンドポイント
    }
    # JWTに署名
    token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")
    print("JWT created successfully.")
    return token

# アクセストークンを取得する関数
def get_access_token_with_jwt():
    print("Fetching access token with JWT...")
    jwt_token = create_jwt()
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token
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
            return None
    except Exception as e:
        print(f"Error during token request: {e}")
        return None

# メッセージを送信する関数
def send_message(account_id, text):
    print("Preparing to send message...")
    access_token = token_cache.get("access_token")
    if not access_token:
        print("Access token is not available. Fetching with JWT...")
        token_data = get_access_token_with_jwt()
        if token_data:
            access_token = token_data.get("access_token")
            token_cache["access_token"] = access_token
        else:
            print("Failed to fetch access token. Cannot send message.")
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
