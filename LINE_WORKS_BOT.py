﻿import os
import time
from google.cloud import vision
import io
import jwt  # PyJWTライブラリを使用
import requests
from flask import Flask, request, jsonify

# Flaskアプリケーションの初期化
app = Flask(__name__)

# LINE Works Bot API設定
CLIENT_ID = "FAKUIs1_C7TzbMG9ZoCp"  # 管理画面で取得
CLIENT_SECRET = "n6ugyKvfCf"  # 管理画面で取得
PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7BP6/i48ra5BAqqj8IowXH1DvyfYbDiEx8x3a+pkiTJ55rfCyrDVrtww0fxORNPXf3EEGvqF6nE6lGshPw41gGLRFMwo151Egg9+PQMQdoTSJ2Nv1KbO3Hu5FwEnAcgUwhPeUMpbAg/klfQQASE9lGKfWO0sSIikQHQwiMfVcb938HzFwjm/SizJIUQkXIxcBwUg4qs2qTuUDpsburLha5YLsvpR8diK9EYh4NyYmpOE7TtxlSVz6/0ZWlgi2pbfYaqjEW+vgLWbfPK7zepuCHTsNwYqDKsy5x0Qb2EJ8AzGKUtrzmBlxfnMk3iBRH4+XV7erH3FxrvniuQAu47PRAgMBAAECggEAF76mcim6d5VUadl2fhi2zQLACHSNx4PvlANy5sggJDoyeW7WW3Zri+21jNQWPGlLJG03C6+tbz9O6ZMxG+t5/4RIyGvBX/RVbmQ/61TE8aFzkGLqaRdZMXv/CE0bMBC/TEM9meEjFyCfw/I6TVI2U7bMgcc3x1Qd/uU+kqLhglGcIbMx7/nJvJApl8WTiPLQvp4btYlUvjUCA/MV0dtYqY3SwuCqvOEKaX+HEYQwY0jTIiQ+mf2nC+OWhfSXBf3QERaRf8ESKIvb0w6fnTHRVnutyxW/QgFDcrhBEO1NIlU8qdMIUyG7SKc0eRuNr6aNL2N2lMDpvwXeZ9JxNaaGXwKBgQDTYxvenj/t2ttkCRibv7/6zcYOyuQqk2k7AfN6H98SeQJBr1BQdkd9CLbwGEESeg7ZhjmTUB0om13h4oZckw9pPc0uRyLXyYyOiku/e+I6C3AY2AVO7bOBLy+28VZOfoQlAYHTVlX8JuDdIKSNoZ+MnBkRDCxw9QgYpB/YWaUSPwKBgQDifVgbDXfZ0dj0qRd/djwc/qm66fj2PnmlxcEsIs4fz8rje/Ry39wKncSswt3SGNCYk3Bhtsopdza0BgcZfVo4DjBs2D4SBgD5BK8jAY2A/qgz2e7XwA0Cfif//XB17Uqngbv52gUJNGhrD/38POjKc1II0yzJLn333K3umZeV7wKBgEVzXoi5vY9MRKCNTIR/b3fbe6MIjgZfAEfe0DvjlMrg7xjdnKmS8tHltxUTIu4LJC3bp7b6r1nUEfhREIwB1SJip7L4tD3pfkCmt1RmQ2GGuIGxF61i84MSGb8lc5G+h3QRFrJ0vzNlIqQEQYw2+dCcyK+NLFzAZLST19KhQVbJAoGAWjrvZ8+kyL1GPqpCtz/mUPLPsaxWx9s54WX4QFoZXikNPjV6vG0cn4oc+Wqkrne+WpqacgM9ZOmefHfOSkRbNevJNQOtLsb/ijVohHyw4AwT/Jw8/+z+Adk6nExeikyfqj4QIkjOKs2bL9PuLpghcc4hh2yB8iA4hQ+Ap4a/EjcCgYEAzYBmuYAnIKbjX7YXq14VEeND4wdbQSCD9sZsqTYgG2ABUiZgDPidrzk2qZr4h84xWbwcZ2vrO4RnzttDW3iP8qPQ8P0ANZFE58h2XZ/LKMRmsdSfDdwBNus+mRmn1MkrjHlI1H1d52AXEYYJlJgsmBXhkKChqlSeWD14yuTCCE0=
-----END PRIVATE KEY-----"""  # 管理コンソールで生成された秘密鍵
ISS = "d7ya7.serviceaccount@reichan"  # 管理画面で確認 (Service Account ID)
TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"
API_URL = "https://www.worksapis.com/v1.0/bots/6807091/messages"  # BOT番号を含む
BOT_NO = "6807091"
SCOPE = "bot"

# 保存先ディレクトリ設定
IMAGE_SAVE_PATH = "/tmp/saved_images"
os.makedirs(IMAGE_SAVE_PATH, exist_ok=True)

# JWTを生成する関数
def create_jwt():
    print("Creating JWT...")
    now = int(time.time())
    payload = {
        "iss": CLIENT_ID,  # Client ID
        "sub": ISS,  # Service Account ID
        "iat": now,  # 現在のタイムスタンプ
        "exp": now + 3600,  # 1時間後の有効期限
        "aud": TOKEN_URL  # トークン取得エンドポイント
    }
    # JWTに署名
    token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")
    print("JWT created successfully.")
    return token

# アクセストークンを取得する関数
def get_access_token():
    print("Fetching access token...")
    jwt_token = create_jwt()
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPE
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
            print("Failed to fetch access token. Details: ", response.text)
            return None
    except Exception as e:
        print(f"Error during token request: {e}")
        return None

# メッセージを送信する関数
def send_message(account_id, text):
    print(f"Preparing to send message to userId: {account_id}")
    try:
        # アクセストークンを取得
        token_data = get_access_token()
        if token_data is None or "access_token" not in token_data:
            raise Exception("Failed to obtain access token.")

        access_token = token_data["access_token"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        # 正しいエンドポイント
        url = f"https://www.worksapis.com/v1.0/bots/{BOT_NO}/users/{account_id}/messages"
        payload = {
            "content": {
                "type": "text",
                "text": text
            }
        }
        response = requests.post(url, json=payload, headers=headers)
        print(f"Message send request status code: {response.status_code}")
        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print(f"Failed to send message. Response: {response.text}")
    except Exception as e:
        print(f"Error during message send: {e}")

# fileIdを使って画像URLを取得する関数
def get_file_url(file_id):
    try:
        # アクセストークンを取得
        token_data = get_access_token()
        if token_data is None or "access_token" not in token_data:
            raise Exception("Failed to obtain access token.")

        access_token = token_data["access_token"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        # 添付ファイル情報を取得するエンドポイント
        url = f"https://www.worksapis.com/v1.0/bots/{BOT_NO}/attachments/{file_id}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            file_data = response.json()
            return file_data.get("fileUrl", "")
        else:
            print(f"Failed to fetch file URL. Status Code: {response.status_code}, Response: {response.text}")
            return ""
    except Exception as e:
        print(f"Error fetching file URL: {e}")
        return ""

# Google Vision APIクライアントを初期化
def initialize_vision_client():
    return vision.ImageAnnotatorClient()

# Google Vision APIを使って画像からテキストを抽出する関数
def extract_text_from_image_with_vision_api(image_path):
    client = initialize_vision_client()

    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if response.error.message:
        raise Exception(f"Google Vision API error: {response.error.message}")

    # テキストを抽出（最初の要素が画像全体のテキスト）
    return texts[0].description if texts else ""

# 保存した画像からテキストを抽出して送信する関数
def process_saved_images_and_send_text():
    print("Processing saved images with Google Vision API...")
    try:
        for image_file in sorted(os.listdir(IMAGE_SAVE_PATH)):
            image_path = os.path.join(IMAGE_SAVE_PATH, image_file)

            # Google Vision APIを使ってテキストを抽出
            try:
                text = extract_text_from_image_with_vision_api(image_path)
                print(f"Extracted text from {image_file}: {text}")

                # テキストをLINE Worksユーザーに送信
                user_id = "target_user_id"  # 実際のユーザーIDに置き換えてください
                if text.strip():
                    send_message(user_id, text)
                else:
                    print(f"No text found in {image_file}.")

            except Exception as e:
                print(f"Failed to process {image_file}: {e}")

            # 処理済みの画像を削除
            os.remove(image_path)
            print(f"Processed and removed {image_file}.")

    except Exception as e:
        print(f"Error processing saved images: {e}")

# Webhookエンドポイント
@app.route("/webhook", methods=["POST"])
def webhook():
    print("Webhook called.")
    try:
        data = request.json
        print(f"Received webhook data: {data}")

        if "content" in data:
            content_type = data["content"].get("type", "")

            # テキストメッセージを処理
            if content_type == "text":
                user_message = data["content"]["text"]
                reply_message = user_message  # メッセージをそのまま返信
                print(f"User message: {user_message}, Reply message: {reply_message}")

                if "source" in data and "userId" in data["source"]:
                    user_id = data["source"]["userId"]
                    send_message(user_id, reply_message)
                else:
                    print("エラー: 'userId' が 'source' データにありません。")

            # 画像メッセージを処理
            elif content_type == "image":
                print("画像メッセージを受信しました。")
                file_id = data["content"].get("fileId")
                if file_id:
                    # fileIdを使ってfileUrlを取得
                    file_url = get_file_url(file_id)
                    if file_url:
                        # 画像をダウンロードして保存
                        response = requests.get(file_url, stream=True)
                        if response.status_code == 200:
                            file_name = os.path.join(IMAGE_SAVE_PATH, f"{int(time.time())}.jpg")
                            with open(file_name, "wb") as img_file:
                                for chunk in response.iter_content(1024):
                                    img_file.write(chunk)
                            print(f"画像を保存しました: {file_name}")

                            # 保存した画像を処理
                            process_saved_images_and_send_text()
                        else:
                            print(f"画像のダウンロードに失敗しました。ステータスコード: {response.status_code}")
                    else:
                        print("fileUrlを取得できませんでした。")
                else:
                    print("画像の 'fileId' が見つかりません。")
        else:
            print("Webhookデータに 'content' フィールドが含まれていません。")
    except Exception as e:
        print(f"Webhook処理中のエラー: {e}")
    return jsonify({"status": "ok"}), 200

# アプリケーション起動
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "LINE Works Bot is running!"}), 200

if __name__ == "__main__":
    print("Starting Flask app on port 3000...")
    app.run(port=3000, debug=True, host="0.0.0.0")
