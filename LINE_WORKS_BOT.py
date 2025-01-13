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
import unicodedata
import openai


# Flaskアプリケーションの初期化
app = Flask(__name__)

# グローバル変数として user_data_store を定義
user_data_store = {}
user_state = {}

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
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

# ユーザーIDを安全に取得する関数
def get_user_id_from_request(data):
    try:
        user_id = data.get("source", {}).get("userId", None)
        if not user_id:
            raise ValueError("userId is missing in the request data.")
        return user_id
    except Exception as e:
        print(f"Error retrieving user_id: {e}")
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
    {
        "label": "お届け日",
        "variable_name": "delivery_date",
        "prompt_instructions": "以下の整理されたデータから「お届け日」に該当する情報を抽出してください。回答は日付だけにしてください。"
    },
    {
        "label": "ご使用日",
        "variable_name": "use_date",
        "prompt_instructions": "以下の整理されたデータから「ご使用日」に該当する情報を抽出してください。回答は日付だけにしてください。。"
    },
    {
        "label": "学校名",
        "variable_name": "school_name",
        "prompt_instructions": "以下の整理されたデータから「学校名」に該当する情報を抽出してください。回答は学校名だけで良いです。"
    },
    {
        "label": "LINEアカウント名",
        "variable_name": "line_name",
        "prompt_instructions": "以下の整理されたデータから「LINEアカウント名」に該当する情報を抽出してください。回答は表示名をご記入くださいの近くの[]の中の文字です。"
    },
    {
        "label": "クラス団体名",
        "variable_name": "group_name",
        "prompt_instructions": "以下の整理されたデータから「クラス団体名」に該当する情報を抽出してください。回答は団体名の右の座標にある文字です。例:2-2など"
    },
    {
        "label": "学校住所",
        "variable_name": "school_address",
        "prompt_instructions": "以下の整理されたデータから「学校住所」に該当する情報を抽出してください。回答は〒番号と住所だけで良いです。学校名からGoogle検索した学校住所も記載してください。"
    },
    {
        "label": "学校TEL",
        "variable_name": "school_tel",
        "prompt_instructions": "以下の整理されたデータから「学校TEL」に該当する情報を抽出してください。回答はxxxx-xx-xxxxのような10桁の数字だけで良いです"
    },
    {
        "label": "ご担任",
        "variable_name": "boss_furigana",
        "prompt_instructions": "以下の整理されたデータから「ご担任」に該当する情報を抽出してください。回答は漢字の名前とフリガナだけで良いです。。"
    },
    {
        "label": "ご担任(保護者)携帯",
        "variable_name": "boss_mobile",
        "prompt_instructions": "以下の整理されたデータから「ご担任(保護者)携帯」に該当する情報を抽出してください。回答は「ご担任(保護者)携帯]の近くにあってxxx-xxxx-xxxxのような形式の11桁の数字を探してください。"
    },
    {
        "label": "担任(保護者)メール",
        "variable_name": "boss_email",
        "prompt_instructions": "以下の整理されたデータから「担任(保護者)メール」に該当する情報を抽出してください。回答はxxx@xxxのようなemail形式を期待しています。回答は抽出されたemail情報だけで良いです。"
    },
    {
        "label": "デザイン確認方法",
        "variable_name": "design_confirm",
        "prompt_instructions": "以下の整理されたデータから「デザイン確認方法」に該当する情報を抽出してください。回答はLINE代表者 or LINEご担任 or メール代表者 or メールご担任のどれか1つのみで可能性の高いものを選択してください。。"
    },
    {
        "label": "代表者氏名",
        "variable_name": "representative_furigana",
        "prompt_instructions": "以下の整理されたデータから「代表者指名」に該当する情報を抽出してください。回答は漢字の名前とフリガナだけで良いです"
    },
    {
        "label": "代表者携帯",
        "variable_name": "representative_mobile",
        "prompt_instructions": "以下の整理されたデータから「代表者携帯」に該当する情報を抽出してください。回答は「代表者携帯」の右にあってxxx-xxxx-xxxxのような形式の11桁の数字を探してください。"
    },
    {
        "label": "代表者メール",
        "variable_name": "representative_email",
        "prompt_instructions": "以下の整理されたデータから「代表者メール」に該当する情報を抽出してください。回答はxxx@xxxのようなemail形式を期待しています。回答は抽出されたemail情報だけで良いです。"
    },
    {
        "label": "商品名",
        "variable_name": "product_name",
        "prompt_instructions": "以下の整理されたデータから「商品名」に該当する情報を抽出してください。回答は商品名座標の直ぐ下にある回答として洋服の種類を期待しています。記載する内容は抽出された商品名だけで良いです。"
    },
    {
        "label": "商品カラー",
        "variable_name": "product_color",
        "prompt_instructions": "以下の整理されたデータから「商品カラー」に該当する情報を抽出してください。回答は商品カラー座標の直ぐ下にある回答として色を連想させる回答を期待しています。記載する回答は回答だけにしてください。。"
    },
    {
        "label": "S",
        "variable_name": "S",
        "prompt_instructions": "以下の整理されたデータから「S」に該当する情報を抽出してください。回答はSから数10ピクセル以内で真下にある数字です。回答は数字だけにしてください。"
    },
    {
        "label": "M",
        "variable_name": "M",
        "prompt_instructions": "以下の整理されたデータから「M」に該当する情報を抽出してください。回答はMから数10ピクセル以内で真下にある数字です。回答は数字だけにしてください。"
    },
    {
        "label": "L",
        "variable_name": "L",
        "prompt_instructions": "以下の整理されたデータから「L」に該当する情報を抽出してください。回答はLから数10ピクセル以内で真下にある数字です。回答は数字だけにしてください。。"
    },
    {
        "label": "LL",
        "variable_name": "LL(XL)",
        "prompt_instructions": "以下の整理されたデータから「LL」に該当する情報を抽出してください。回答はLLから数10ピクセル以内で真下にある数字です。回答は数字だけにしてください。"
    },
    {
        "label": "3L",
        "variable_name": "3L(XXL)",
        "prompt_instructions": "以下の整理されたデータから「3L」に該当する情報を抽出してください。回答は3Lから数10ピクセル以内で真下にある数字です。回答は数字だけにしてください。"
    },
    {
        "label": "小計",
        "variable_name": "sub_total",
        "prompt_instructions": "以下の整理されたデータから「小計」に該当する情報を抽出してください。回答は数字だけにしてください。。"
    },
    {
        "label": "合計",
        "variable_name": "total",
        "prompt_instructions": "以下の整理されたデータから「合計」に該当する情報を抽出してください。回答は数字だけにしてください。"
    },
    {
        "label": "プリントサイズ",
        "variable_name": "print_size",
        "prompt_instructions": "以下の整理されたデータから「サイズ」に該当する情報を抽出してください。期待する回答はヨコxx cm x タテxx cmという回答です。回答形式はX=xxcm, Y=xxcmです。"
    },
    {
        "label": "プリントカラー/オプション",
        "variable_name": "print_colorl",
        "prompt_instructions": "以下の整理されたデータから「プリントカラー/オプション」に該当する情報を抽出してください。期待する回答は色情報と計xx色という回答です。回答形式は色=a,b,c,d, 計=x色です。"
    },
    {
        "label": "デザインサンプル",
        "variable_name": "print_design",
        "prompt_instructions": "以下の整理されたデータから「デザインサンプル」に該当する情報を抽出してください。期待する回答はD-352のようなアルファベットと数字の組み合わせ情報です。回答形式はx-xxxです。"
    },

]


def normalize_text(text):
    """
    テキストの正規化（例: 全角→半角、スペース除去）。
    """
    text = unicodedata.normalize('NFKC', text)  # 全角を半角に変換
    text = text.strip()  # 前後のスペースを削除
    return text

import openai
import re
import unicodedata

def process_extracted_text(response, search_coordinates_template):
    """
    OCRレスポンスから指定されたラベルに対応する回答を抽出。
    全OCRデータをOpenAI APIで整理し、整理されたデータからラベルごとに該当する回答を抽出。

    Parameters:
        response (obj): Google Vision APIのレスポンス。
        search_coordinates_template (list[dict]): ラベル情報と範囲情報を含むテンプレート。

    Returns:
        list[dict]: ラベル、変数名、回答、座標をまとめた結果。
    """

    def normalize_text(text):
        """テキストを正規化して比較可能な形に整える。"""
        text = unicodedata.normalize('NFKC', text)  # 全角→半角
        text = re.sub(r"\s+", "", text)            # スペース削除
        return text.lower()

    def extract_blocks_with_coordinates(response):
        """OCRレスポンスから block 単位でテキストと座標情報を抽出。"""
        block_data = []
        if not response.full_text_annotation:
            return []

        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                block_text = "".join(
                    [
                        "".join(symbol.text for symbol in word.symbols) + " "
                        for paragraph in block.paragraphs
                        for word in paragraph.words
                    ]
                )
                coordinates = [(v.x, v.y) for v in block.bounding_box.vertices]
                block_data.append({
                    "text": block_text.strip(),
                    "coordinates": coordinates
                })

        return block_data

    def query_openai_for_analysis(block_data):
        """
        OpenAI APIを使用してブロックデータを整理。
        ドキュメントに沿って openai.chat.completions.create を用いた実装に修正。
        """
        prompt = (
            "以下はOCRで抽出されたテキストブロックと座標のデータです。"
            "データを整理して、人が理解しやすい形式に変換してください。毎回固定処理にしてください。:\n"
            f"{block_data}"
        )
        try:
            response_obj = openai.chat.completions.create(
                model="gpt-3.5-turbo",  # 必要に応じて "gpt-4" 等に変更
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature = 0,
            )
            ai_message = response_obj.choices[0].message.content
            return ai_message
        except Exception as e:
            print(f"OpenAI API Error (analysis): {e}")
            return ""

    def find_label_in_organized_text(organized_text, label, custom_prompt=None):
        """
        整理されたテキストからラベルに対応する回答を探す。
        custom_prompt（独自のプロンプト）を受け取り、なければデフォルト文言を使う。
        """

        # テンプレートで独自のプロンプトが指定されている場合
        if custom_prompt:
            prompt = f"{custom_prompt}\n\n{organized_text}"
        else:
            # 指定がなければ、従来の文言で検索
            prompt = (
                f"以下の整理されたデータから「{label}」に該当する内容を抽出してください:\n"
                f"{organized_text}"
            )

        try:
            response_obj = openai.chat.completions.create(
                model="gpt-3.5-turbo",  # 必要に応じて "gpt-4" 等に変更
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature = 0,
            )
            return response_obj.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API Error (label-search): {e}")
            return ""

    # --- ここからメイン処理 ---

    # 1. OCR結果のブロックを抽出
    block_data = extract_blocks_with_coordinates(response)

    # 2. OpenAI API を使って全ブロックデータを人が理解しやすい形に整理
    organized_text = query_openai_for_analysis(block_data)

    results = []
    # 3. テンプレートの各要素に対してラベルを検索
    for template_item in search_coordinates_template:
        label = template_item["label"]
        variable_name = template_item["variable_name"]

        # テンプレートに"prompt_instructions"があれば使う
        custom_prompt = template_item.get("prompt_instructions", None)

        # find_label_in_organized_text に custom_prompt を渡す
        refined_answer = find_label_in_organized_text(organized_text, label, custom_prompt)

        results.append({
            "テキスト": label,
            "変数名": variable_name,
            "回答": refined_answer,
            "座標": None  # 必要に応じて座標情報を付与するならここで追加
        })

    return results


def process_and_send_text_from_image(image_path=None):
    """
    Google Vision APIを使用して画像からテキストを抽出し、
    抽出したテキストを処理および送信する関数。
    """
    print("Processing images with Google Vision API...")
    image_files = [image_path] if image_path else sorted(os.listdir(IMAGE_SAVE_PATH))
    
    # 変数名ごとの回答を保存する辞書
    organized_data = {}

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

                # デバッグ用ログ
                print("Processed results:", processed_results)

                # 結果をLINE Worksユーザーに送信
                user_id = "9295462e-77df-4410-10a1-05ed80ea849d"  # 実際のユーザーIDに置き換え
                for result in processed_results:
                    label = result["テキスト"]
                    answer = result["回答"]
                    variable_name = result["変数名"]

                    # `回答`がリストの場合を考慮
                    if isinstance(answer, list):
                        # リスト内の要素を結合して1つの文字列にする
                        answer = " ".join(map(str, answer))

                    # `回答`が文字列であることを確認
                    if isinstance(answer, str) and answer.strip():
                        # 結果を保存
                        organized_data[variable_name] = answer.strip()
                        try:
                            send_message(user_id, f"{label}: {variable_name}: {answer.strip()}")
                        except Exception as send_error:
                            print(f"Failed to send message for label '{label}': {send_error}")
                    else:
                        print(f"No meaningful answer found for label '{label}' in {current_image_path}.")
            except Exception as e:
                print(f"Failed to process {current_image_path}: {e}")

            # 処理済み画像を削除
            if not image_path:
                try:
                    os.remove(current_image_path)
                    print(f"Processed and removed {current_image_path}.")
                except Exception as remove_error:
                    print(f"Failed to remove {current_image_path}: {remove_error}")
    except Exception as e:
        print(f"Error processing images: {e}")
    
    # 結果の保存を確認
    print("Organized data:")
    for key, value in organized_data.items():
        print(f"{key}: {value}")

    return organized_data

def normalize_product_name(product_name):
    """
    商品名を正規化して不要なスペースや文字を除去する関数。
    """
    return product_name.replace(" ", "").strip()

def calculate_invoice(user_id, price_table, user_data_store):
    """
    user_data_store に保存された organized_data から請求金額を計算し、結果を保存する関数。

    Parameters:
        user_id (str): ユーザーID。
        price_table (dict): 商品名をキー、価格を値とする価格表。
        user_data_store (dict): ユーザーごとのデータを保存する辞書。

    Returns:
        dict: 請求金額を追加した organized_data。
    """
    try:
        # organized_data を取得
        organized_data = user_data_store.get(user_id, None)
        if not organized_data:
            print(f"Error: No organized_data found for user_id {user_id}.")
            return None

        # 商品名を取得
        product_name = organized_data.get("product_name", "").strip()
        if not product_name:
            print(f"Error: No product_name found in organized_data for user_id {user_id}.")
            return organized_data

        normalized_product_name = normalize_product_name(product_name)

        # 部分一致で商品の価格を取得
        product_price = None
        for key in price_table.keys():
            if normalize_product_name(key) in normalized_product_name:
                product_price = price_table[key]
                break

        if product_price is None:
            print(f"Error: No matching product found for '{product_name}' in price table.")
            return organized_data

        # 数量を取得
        quantities = {}
        for size in ["S", "M", "L", "LL(XL)", "3L(XXL)"]:
            value = organized_data.get(size, "0")
            try:
                quantities[size] = int(value)
            except ValueError:
                print(f"Warning: Invalid quantity value '{value}' for size '{size}'. Setting it to 0.")
                quantities[size] = 0

        # 合計数量を計算
        total_quantity = sum(quantities.values())
        if total_quantity == 0:
            print(f"Error: No valid quantities found for product '{product_name}'.")
            return organized_data

        # 合計金額を計算
        total_amount = product_price * total_quantity

        # 結果を organized_data に保存
        organized_data["total_amount"] = total_amount
        user_data_store[user_id] = organized_data

        print(f"Invoice calculated and updated in user_data_store: {product_name} x {total_quantity} = {total_amount}円")
        return organized_data

    except Exception as e:
        print(f"Error calculating invoice: {e}")
        return None


# 使用例
price_table = {
    "フードスウェット": 5000,
    "Tシャツ": 2000,
    "パーカー": 4000
}

# ユーザーデータ管理用の辞書
user_data_store = {
    "9295462e-77df-4410-10a1-05ed80ea849d": {
        "product_name": "フードスウェット",
        "S": "2",
        "M": "1",
        "L": "3",
        "LL(XL)": "0",
        "3L(XXL)": "0"
    }
}

# サンプルユーザーID
user_id = "9295462e-77df-4410-10a1-05ed80ea849d"

# 請求金額を計算
updated_data = calculate_invoice(user_id, price_table, user_data_store)

# organized_data の内容を確認
print(updated_data)

# user_data_store の内容を確認
print(user_data_store)


def create_flex_message(organized_data):
    """
    organized_dataをFlex Message形式で整形する関数。
    """
    flex_message = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "注文内容確認",
                    "weight": "bold",
                    "size": "lg",
                    "margin": "md"
                },
                {
                    "type": "separator",
                    "margin": "md"
                }
            ] + [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": f"{key}:", "flex": 2, "weight": "bold"},
                        {"type": "text", "text": str(value), "flex": 4}
                    ]
                }
                for key, value in organized_data.items()
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "修正", "text": "修正を開始"},
                    "style": "primary",
                    "color": "#FF6F61"
                },
                {
                    "type": "button",
                    "action": {"type": "message", "label": "確定", "text": "注文を確定する"},
                    "style": "primary",
                    "color": "#4CAF50"
                }
            ]
        }
    }
    return flex_message

def send_quick_reply_for_edit(user_id, organized_data):
    """
    修正可能な項目をQuick Reply形式でユーザーに提示する。
    """
    quick_reply_items = [
        {
            "type": "action",
            "action": {
                "type": "message",
                "label": key,
                "text": f"{key}を修正"
            }
        }
        for key in organized_data.keys()
    ]

    payload = {
        "content": {
            "type": "text",
            "text": "修正したい項目を選択してください。",
            "quickReply": {
                "items": quick_reply_items
            }
        }
    }

    # アクセストークンを使ってメッセージを送信
    try:
        token_data = get_access_token()
        if token_data and "access_token" in token_data:
            access_token = token_data["access_token"]
            url = f"https://www.worksapis.com/v1.0/bots/{BOT_NO}/users/{user_id}/messages"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                print("Quick Reply sent successfully!")
            else:
                print(f"Failed to send Quick Reply. Status Code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Error sending Quick Reply: {e}")


def send_flex_message(user_id, flex_message):
    """
    Flex MessageをLINE WORKSユーザーに送信する関数。

    Parameters:
        user_id (str): メッセージを送信するユーザーのID。
        flex_message (dict): Flex Messageのデータ構造。

    Returns:
        None
    """
    try:
        # アクセストークンを取得
        token_data = get_access_token()
        if token_data and "access_token" in token_data:
            access_token = token_data["access_token"]
            url = f"https://www.worksapis.com/v1.0/bots/{BOT_NO}/users/{user_id}/messages"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "content": {
                    "type": "flex",
                    "altText": "注文内容の確認",  # 必須のaltTextパラメータを追加
                    "contents": flex_message
                }
            }
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                print("Flex Message sent successfully!")
            else:
                print(f"Failed to send Flex Message. Status Code: {response.status_code}, Response: {response.text}")
        else:
            print("Failed to fetch access token.")
    except Exception as e:
        print(f"Error sending Flex Message: {e}")



# Webhookエンドポイント
@app.route("/webhook", methods=["POST"])
def webhook():
    print("Webhook called.")
    try:
        data = request.json
        print(f"Received webhook data: {data}")

        # 初期化
        organized_data = None
        user_id = data.get("source", {}).get("userId", None)

        if not user_id:
            print("エラー: userId がリクエストデータに含まれていません。")
            return jsonify({"status": "error", "message": "Missing userId"}), 400

        if "content" in data:
            content_type = data["content"].get("type", "")

            # テキストメッセージを処理
            if content_type == "text":
                user_message = data["content"].get("text", "").strip()
                user_id = data.get("source", {}).get("userId", None)
                if user_id:
                    user_data_store[user_id] = organized_data
                    print(f"Updated user_data_store for user_id {user_id}: {organized_data}")

                if not user_id:
                    print("エラー: userId がリクエストデータに含まれていません。")
                    return jsonify({"status": "error", "message": "Missing userId"}), 400

                # 注文内容確認フロー
                if user_message == "注文を確認":
                    # user_data_store から organized_data を取得
                    organized_data = user_data_store.get(user_id, None)
                    if not organized_data:
                        send_message(user_id, "注文データが見つかりません。")
                        return

                    # organized_data の全ての変数を確認してログに出力
                    print(f"Organized data for user {user_id}: {organized_data}")

                    # Flex Messageで確認メッセージを送信
                    flex_message = create_flex_message(organized_data)
                    send_flex_message(user_id, flex_message)
                # 修正プロセス
                elif user_message == "修正を開始":
                    if user_id in user_data_store:
                        organized_data = user_data_store[user_id]
                        send_quick_reply_for_edit(user_id, organized_data)
                    else:
                        send_message(user_id, "修正可能なデータが見つかりません。")

                elif "を修正" in user_message:
                    # 修正対象の項目を取得
                    key_to_edit = user_message.replace("を修正", "").strip()
                    if user_id in user_data_store and key_to_edit in user_data_store[user_id]:
                        send_message(user_id, f"新しい{key_to_edit}を入力してください。")
                        user_state[user_id] = {"action": "edit", "key": key_to_edit}
                    else:
                        send_message(user_id, f"'{key_to_edit}' は修正できる項目ではありません。")

                elif user_id in user_state and user_state[user_id].get("action") == "edit":
                    # ユーザーが新しい値を入力した場合の処理
                    key_to_edit = user_state[user_id]["key"]
                    organized_data = user_data_store.get(user_id, {})
                    organized_data[key_to_edit] = user_message  # 新しい値を保存
                    user_data_store[user_id] = organized_data  # データを更新
                    send_message(user_id, f"{key_to_edit} を {user_message} に更新しました。")
                    del user_state[user_id]  # 状態をリセット

                # 注文確定
                elif user_message == "注文を確定する":
                    send_message(user_id, "注文が確定されました。ありがとうございます！")

                else:
                    send_message(user_id, "注文を確認したい場合は『注文を確認』と送信してください。")

            # 画像メッセージを処理
            elif content_type == "image":
                print("画像メッセージを受信しました。")
                file_id = data["content"].get("fileId")
                if file_id:
                    file_url = get_file_url(file_id)
                    if file_url:
                        token_data = get_access_token()
                        if token_data and "access_token" in token_data:
                            access_token = token_data["access_token"]
                            downloaded_file = download_attachment(file_url, access_token)
                            if downloaded_file:
                                print(f"Downloaded file saved at {downloaded_file}")

                                # 保存した画像を処理
                                organized_data = process_and_send_text_from_image(downloaded_file)

                                if organized_data:
                                    user_data_store[user_id] = organized_data
                                     # 保存内容をログ出力
                                    print(f"Updated user_data_store for user_id {user_id}: {user_data_store[user_id]}")
                                    send_message(user_id, "データが保存されました。修正を開始できます。")

                                    # 請求金額を計算
                                    price_table = {
                                        "フードスウェット": 5000,
                                        "Tシャツ": 2000,
                                        "パーカー": 4000
                                    }
                                    updated_data = calculate_invoice(user_id, price_table, user_data_store)

                                    if "total_amount" in updated_data:
                                        total_amount = updated_data["total_amount"]
                                        product_name = updated_data.get("product_name", "不明")
                                        send_message(user_id, f"請求金額: {product_name} の合計は {total_amount}円です。")
                                else:
                                    send_message(user_id, "データの保存に失敗しました。")
                            else:
                                send_message(user_id, "画像のダウンロードに失敗しました。")
                        else:
                            send_message(user_id, "アクセストークンを取得できませんでした。")
                    else:
                        send_message(user_id, "fileUrlを取得できませんでした。")
                else:
                    send_message(user_id, "画像の 'fileId' が見つかりません。")
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
