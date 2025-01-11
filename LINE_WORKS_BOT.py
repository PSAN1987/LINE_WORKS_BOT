import os
import time
from google.cloud import vision
from google.cloud.vision_v1 import types
import io
import jwt  # PyJWTライブラリを使用
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Flaskアプリケーションの初期化
app = Flask(__name__)

# LINE Works Bot API設定
CLIENT_ID = "FAKUIs1_C7TzbMG9ZoCp"  # 管理画面で取得
CLIENT_SECRET = "n6ugyKvfCf"  # 管理画面で取得
PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
...YOUR_PRIVATE_KEY...
-----END PRIVATE KEY-----"""
ISS = "d7ya7.serviceaccount@reichan"  # 管理画面で確認 (Service Account ID)
TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"
BOT_NO = "6807091"
SCOPE = "bot"

# 環境変数の取得
load_dotenv()
google_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path

# 保存先ディレクトリ設定
IMAGE_SAVE_PATH = "/tmp/saved_images"
os.makedirs(IMAGE_SAVE_PATH, exist_ok=True)

# Vision API クライアント初期化
client = vision.ImageAnnotatorClient()

# JWTを生成する関数
def create_jwt():
    now = int(time.time())
    payload = {
        "iss": CLIENT_ID,
        "sub": ISS,
        "iat": now,
        "exp": now + 3600,
        "aud": TOKEN_URL
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")

# アクセストークンを取得する関数
def get_access_token():
    jwt_token = create_jwt()
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPE
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to fetch access token.", response.text)
        return None

# メッセージを送信する関数
def send_message(account_id, text):
    token_data = get_access_token()
    if not token_data or "access_token" not in token_data:
        raise Exception("Failed to obtain access token.")

    access_token = token_data["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"https://www.worksapis.com/v1.0/bots/{BOT_NO}/users/{account_id}/messages"
    payload = {"content": {"type": "text", "text": text}}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        print("Message sent successfully!")
    else:
        print("Failed to send message.", response.text)

# 画像からテキストを抽出する関数
def process_image_for_text(image_path):
    try:
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        image = types.Image(content=content)
        response = client.text_detection(image=image)
        if response.error.message:
            raise Exception(f"Vision API Error: {response.error.message}")
        texts = response.text_annotations
        return texts[0].description if texts else ""
    except Exception as e:
        print(f"Error extracting text from {image_path}: {e}")
        return ""

# OCR結果をLINE Worksユーザーに送信する関数
def send_text_from_image(user_id, text):
    if text.strip():
        send_message(user_id, text)
    else:
        print("No text to send.")

# 統合処理関数
def process_and_send_text_from_image(image_path=None, user_id="default_user_id"):
    print(f"Processing image: {image_path}")
    extracted_text = process_image_for_text(image_path)
    send_text_from_image(user_id, extracted_text)

# Webhookエンドポイント
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        if "content" in data:
            content_type = data["content"].get("type", "")
            if content_type == "text":
                user_message = data["content"]["text"]
                user_id = data["source"].get("userId", "default_user_id")
                send_message(user_id, user_message)
            elif content_type == "image":
                file_id = data["content"].get("fileId")
                if file_id:
                    file_url = get_file_url(file_id)
                    if file_url:
                        token_data = get_access_token()
                        if token_data and "access_token" in token_data:
                            access_token = token_data["access_token"]
                            downloaded_file = download_attachment(file_url, access_token)
                            if downloaded_file:
                                process_and_send_text_from_image(downloaded_file, data["source"].get("userId", "default_user_id"))
                            else:
                                print("Failed to download the image.")
                        else:
                            print("Failed to obtain access token.")
                    else:
                        print("Failed to fetch file URL.")
                else:
                    print("Image 'fileId' not found.")
        else:
            print("Invalid webhook data.")
    except Exception as e:
        print(f"Error handling webhook: {e}")
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    print("Starting Flask app on port 3000...")
    app.run(port=3000, debug=True, host="0.0.0.0")
