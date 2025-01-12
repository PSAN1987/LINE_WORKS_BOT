﻿import os
import time
from google.cloud import vision
from google.cloud.vision_v1 import types
import io
import jwt  # PyJWTライブラリを使用
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import re

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

# .envファイルを読み込む
load_dotenv()
# 環境変数の取得
google_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
# Google Cloud Vision APIの認証設定
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path

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
    print(f"JWT Payload: {payload}")
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
        if response.status_code == 201:
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
        print(f"Requesting file URL with: {url}")
        print(f"Request Headers: {headers}")

        # リクエストを送信
        response = requests.get(url, headers=headers, allow_redirects=False)
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Headers: {response.headers}")

        # 302リダイレクトの場合
        if response.status_code == 302 and "Location" in response.headers:
            file_url = response.headers["Location"]
            print(f"Redirected file URL: {file_url}")
            return file_url
        else:
            print(f"Failed to fetch file URL. Status Code: {response.status_code}, Response: {response.text}")
            return ""
    except Exception as e:
        print(f"Error fetching file URL: {e}")
        return ""
    
# 添付ファイルをダウンロードする関数
def download_attachment(file_url, access_token):
    """
    添付ファイルをダウンロードする関数
    """
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        print(f"Downloading file from: {file_url}")
        response = requests.get(file_url, headers=headers, stream=True)
        print(f"Response Status Code: {response.status_code}")

        if response.status_code == 200:
            file_name = os.path.join(IMAGE_SAVE_PATH, f"downloaded_image_{int(time.time())}.jpg")
            with open(file_name, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"File saved as {file_name}")
            return file_name
        else:
            print(f"Failed to download the file. Status Code: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        print(f"Error occurred while downloading the file: {e}")
        return None
    
# 環境変数 GOOGLE_APPLICATION_CREDENTIALS をログに記録
def verify_google_application_credentials():
    try:
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_path and os.path.exists(credentials_path):
            print(f"GOOGLE_APPLICATION_CREDENTIALS is set correctly: {credentials_path}")
        else:
            print("Error: GOOGLE_APPLICATION_CREDENTIALS is not set or the file does not exist.")
    except Exception as e:
        print(f"Error verifying GOOGLE_APPLICATION_CREDENTIALS: {e}")

# Vision API クライアント作成前に呼び出し
verify_google_application_credentials()
client = vision.ImageAnnotatorClient()

# Google Vision APIクライアントを初期化
def initialize_vision_client():
    return vision.ImageAnnotatorClient()

search_coordinates_template = [
    {"label": "お届け日", "variable_name": "delivery_date", "search_range": [(50, 100), (200, 150)]},
    {"label": "商品のご使用日", "variable_name": "use_date", "search_range": [(250, 100), (400, 150)]},
    {"label": "学校名", "variable_name": "school_name", "search_range": [(50, 200), (300, 250)]},
    {"label": "学校住所", "variable_name": "school_address", "search_range": [(50, 300), (500, 350)]},
    {"label": "学校TEL", "variable_name": "school_tel", "search_range": [(550, 300), (700, 350)]},
    {"label": "代表者 氏名 フリガナ", "variable_name": "representative_furigana", "search_range": [(50, 400), (300, 450)]},
    {"label": "代表者 携帯", "variable_name": "representative_mobile", "search_range": [(350, 400), (600, 450)]},
    {"label": "商品名", "variable_name": "product_name", "search_range": [(50, 500), (300, 550)]},
    {"label": "商品カラー", "variable_name": "product_color", "search_range": [(350, 500), (600, 550)]},
]

# OCR処理後のテキスト処理
def process_extracted_text(response, search_coordinates_template):
    """
    Google Vision APIのレスポンスを使用して、テキストを処理し、
    指定した座標範囲内で回答を検索します。

    Parameters:
        response (obj): Google Vision APIのレスポンス
        search_coordinates_template (list[dict]): 各パラメータごとの座標範囲を指定する辞書のリスト
        （例: [{"label": "お届け日", "variable_name": "delivery_date", "search_range": [(x_min, y_min), (x_max, y_max)]}]）

    Returns:
        list[dict]: テキスト、変数名、手書き回答、座標情報をまとめたリスト
    """

    def extract_text_with_coordinates(response):
        """
        Google Vision APIのレスポンスからテキストとその座標情報を抽出
        """
        text_data = []
        for text in response.text_annotations:
            # テキストとバウンディングボックスの座標を取得
            description = text.description
            vertices = text.bounding_poly.vertices
            coordinates = [(v.x, v.y) for v in vertices]
            text_data.append({
                "text": description,
                "coordinates": coordinates
            })
        return text_data

    def is_within_coordinates(coords, search_range):
        """
        座標が指定された範囲内にあるか判定
        """
        x_min, y_min = search_range[0]
        x_max, y_max = search_range[1]
        x, y = coords[0]  # 左上の座標のみ使用

        return x_min <= x <= x_max and y_min <= y <= y_max

    def find_text_in_range(label, text_data, search_range):
        """
        指定された範囲内でラベルに対応するテキストを検索
        """
        result = {"label": label, "answer": "", "label_coordinates": None, "answer_coordinates": None}

        # 指定された範囲内でテキストを検索
        for item in text_data:
            if is_within_coordinates(item["coordinates"], search_range):
                result["answer"] = item["text"]
                result["answer_coordinates"] = item["coordinates"]
                break

        return result

    def normalize_text(value):
        """
        OCRで抽出された手書き回答を正規化する
        """
        if not value:
            return ""

        # 電話番号のフォーマットを整える
        value = re.sub(r"(\d{3})(\d{4})(\d{4})", r"\1-\2-\3", value)

        # 特殊文字を削除
        value = re.sub(r"[^\w\s\(\):\-]", "", value)

        # 不要な空白を削除
        value = value.strip()

        return value

    # Google Vision APIレスポンスからデータを抽出
    text_data = extract_text_with_coordinates(response)

    results = []
    for item in search_coordinates_template:
        label = item.get("label")
        variable_name = item.get("variable_name")
        search_range = item.get("search_range")

        if not search_range:
            print(f"No search range defined for label '{label}'")
            continue

        result = find_text_in_range(label, text_data, search_range)
        results.append({
            "テキスト": label,
            "変数名": variable_name,
            "手書き回答": normalize_text(result["answer"]),
            "ラベル座標": result["label_coordinates"],
            "回答座標": result["answer_coordinates"]
        })

    return results


def process_and_send_text_from_image(image_path=None):
    """
    Google Vision APIを使用して画像からテキストを抽出し、
    抽出したテキストを処理および送信する関数。
    """
    print("Processing images with Google Vision API...")
    image_files = [image_path] if image_path else sorted(os.listdir(IMAGE_SAVE_PATH))
    try:
        for image_file in image_files:
            current_image_path = image_path if image_path else os.path.join(IMAGE_SAVE_PATH, image_file)
            try:
                # 画像ファイルを読み込む
                with open(current_image_path, "rb") as image_file:
                    content = image_file.read()

                # Google Vision APIのリクエストを準備
                image = vision.Image(content=content)
                response = client.text_detection(image=image)

                # APIレスポンスのエラーチェック
                if response.error.message:
                    raise Exception(f"Vision API Error: {response.error.message}")

                # レスポンスからテキストを抽出
                if not response.text_annotations:
                    print(f"No text found in {current_image_path}.")
                    continue

                print(f"Extracting text from {current_image_path}...")
                # search_coordinates_template を渡す
                processed_results = process_extracted_text(response, search_coordinates_template)

                # 結果をLINE Worksユーザーに送信
                user_id = "9295462e-77df-4410-10a1-05ed80ea849d"  # 実際のユーザーIDに置き換え
                for result in processed_results:
                    label = result["テキスト"]
                    answer = result["手書き回答"]
                    if answer.strip():
                        send_message(user_id, f"{label}: {answer}")
                    else:
                        print(f"No meaningful answer found for label '{label}' in {current_image_path}.")

            except Exception as e:
                print(f"Failed to process {current_image_path}: {e}")

            # 処理済み画像を削除
            if not image_path:
                os.remove(current_image_path)
                print(f"Processed and removed {current_image_path}.")
    except Exception as e:
        print(f"Error processing images: {e}")

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
                        # アクセストークンを取得
                        token_data = get_access_token()
                        if token_data and "access_token" in token_data:
                            access_token = token_data["access_token"]
                            # 添付ファイルをダウンロード
                            downloaded_file = download_attachment(file_url, access_token)
                            if downloaded_file:
                                print(f"Downloaded file saved at {downloaded_file}")

                                # 保存した画像を処理
                                process_and_send_text_from_image(downloaded_file)
                            else:
                                print("画像のダウンロードに失敗しました。")
                        else:
                            print("アクセストークンを取得できませんでした。")
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
