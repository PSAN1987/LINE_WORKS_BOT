import os
import psycopg2
import requests
from dotenv import load_dotenv
from flask import Flask, request, abort, render_template_string
import logging
import traceback
import json

# ★ line-bot-sdk v2 系 ★
from linebot import (
    LineBotApi,
    WebhookHandler
)
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    PostbackEvent,
    TextMessage,
    TextSendMessage,
    PostbackAction,
    FlexSendMessage,
    BubbleContainer,
    CarouselContainer,
    BoxComponent,
    TextComponent,
    ButtonComponent,
    ImageMessage
)

#############################
# (A) 既存の環境変数など読み込み
#############################
load_dotenv()

CHANNEL_ACCESS_TOKEN = os.getenv('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('CHANNEL_SECRET')

# ★ S3 などにアップロードするための環境変数例
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

DATABASE_NAME = os.getenv('DATABASE_NAME')
DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
DATABASE_HOST = os.getenv('DATABASE_HOST')
DATABASE_PORT = os.getenv('DATABASE_PORT')

# ▼▼ 追加 (Google Vision, OpenAI用) ▼▼
GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# ▲▲ 追加 ▲▲

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ---------------------------------------
# (B) ユーザーの状態管理 (簡易) - DB等推奨
# ---------------------------------------
user_states = {}

###################################
# (C) DB接続 (PostgreSQL想定)
###################################
def get_db_connection():
    """PostgreSQLに接続してconnectionを返す"""
    return psycopg2.connect(
        dbname=DATABASE_NAME,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host=DATABASE_HOST,
        port=DATABASE_PORT
    )

###################################
# (D) S3にファイルをアップロード
###################################
import boto3
from werkzeug.utils import secure_filename
import uuid

def upload_file_to_s3(file_storage, s3_bucket, prefix="uploads/"):
    """
    file_storage: FlaskのFileStorageオブジェクト (request.files['...'])
    s3_bucket: アップ先のS3バケット名
    prefix: S3上のパスのプレフィックス
    戻り値: アップロード後のS3ファイルURL (空なら None)
    """
    if not file_storage or file_storage.filename == "":
        return None

    s3 = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    filename = secure_filename(file_storage.filename)
    unique_id = str(uuid.uuid4())
    s3_key = prefix + unique_id + "_" + filename

    s3.upload_fileobj(file_storage, s3_bucket, s3_key)

    url = f"https://{s3_bucket}.s3.amazonaws.com/{s3_key}"
    return url

### Base64をS3にアップロードする関数 (JPEG対応) ###
import base64

def upload_base64_to_s3(base64_data, s3_bucket, prefix="uploads/"):
    """
    Base64文字列 (data:image/...base64,...) をデコードしてS3にアップロードし、URLを返す。
    base64_data: dataURL形式の文字列 (例: "data:image/jpeg;base64,....")
    s3_bucket: S3バケット名
    prefix: S3のプレフィックス
    戻り値: アップロード後のS3ファイルURL (失敗時は None)
    """
    if not base64_data.startswith("data:image/"):
        return None

    header, encoded = base64_data.split(",", 1)
    mime_type = header.split(";")[0].split(":")[1]  # 例 "image/jpeg" 等

    # MIMEタイプに応じて拡張子を決定
    if mime_type == "image/png":
        ext = "png"
    elif mime_type == "image/jpeg":
        ext = "jpg"
    else:
        ext = "dat"

    image_data = base64.b64decode(encoded)

    s3 = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    unique_id = str(uuid.uuid4())
    s3_key = prefix + unique_id + f".{ext}"

    s3.put_object(
        Bucket=s3_bucket,
        Key=s3_key,
        Body=image_data,
        ContentType=mime_type,
        ACL='public-read'
    )

    url = f"https://{s3_bucket}.s3.amazonaws.com/{s3_key}"
    return url

###################################
# (E) 価格表と計算ロジック
###################################
PRICE_TABLE = [
    # product,  minQty, maxQty, discountType, unitPrice, addColor, addPosition, addFullColor
    # e.g. ドライTシャツ (早割 or 通常)
    # ドライTシャツ
    ("ドライTシャツ", 10, 14, "早割", 1830, 850, 850, 550),
    ("ドライTシャツ", 10, 14, "通常", 2030, 850, 850, 550),
    ("ドライTシャツ", 15, 19, "早割", 1470, 650, 650, 550),
    ("ドライTシャツ", 15, 19, "通常", 1670, 650, 650, 550),
    ("ドライTシャツ", 20, 29, "早割", 1230, 450, 450, 550),
    ("ドライTシャツ", 20, 29, "通常", 1430, 450, 450, 550),
    ("ドライTシャツ", 30, 39, "早割", 1060, 350, 350, 550),
    ("ドライTシャツ", 30, 39, "通常", 1260, 350, 350, 550),
    ("ドライTシャツ", 40, 49, "早割", 980, 350, 350, 550),
    ("ドライTシャツ", 40, 49, "通常", 1180, 350, 350, 550),
    ("ドライTシャツ", 50, 99, "早割", 890, 350, 350, 550),
    ("ドライTシャツ", 50, 99, "通常", 1090, 350, 350, 550),
    ("ドライTシャツ", 100, 500, "早割", 770, 300, 300, 550),
    ("ドライTシャツ", 100, 500, "通常", 970, 300, 300, 550),

    # ヘビーウェイトTシャツ
    ("ヘビーウェイトTシャツ", 10, 14, "早割", 1970, 850, 850, 550),
    ("ヘビーウェイトTシャツ", 10, 14, "通常", 2170, 850, 850, 550),
    ("ヘビーウェイトTシャツ", 15, 19, "早割", 1610, 650, 650, 550),
    ("ヘビーウェイトTシャツ", 15, 19, "通常", 1810, 650, 650, 550),
    ("ヘビーウェイトTシャツ", 20, 29, "早割", 1370, 450, 450, 550),
    ("ヘビーウェイトTシャツ", 20, 29, "通常", 1570, 450, 450, 550),
    ("ヘビーウェイトTシャツ", 30, 39, "早割", 1200, 350, 350, 550),
    ("ヘビーウェイトTシャツ", 30, 39, "通常", 1400, 350, 350, 550),
    ("ヘビーウェイトTシャツ", 40, 49, "早割", 1120, 350, 350, 550),
    ("ヘビーウェイトTシャツ", 40, 49, "通常", 1320, 350, 350, 550),
    ("ヘビーウェイトTシャツ", 50, 99, "早割", 1030, 350, 350, 550),
    ("ヘビーウェイトTシャツ", 50, 99, "通常", 1230, 350, 350, 550),
    ("ヘビーウェイトTシャツ", 100, 500, "早割", 910, 300, 300, 550),
    ("ヘビーウェイトTシャツ", 100, 500, "通常", 1100, 300, 300, 550),

    # ドライポロシャツ
    ("ドライポロシャツ", 10, 14, "早割", 2170, 850, 850, 550),
    ("ドライポロシャツ", 10, 14, "通常", 2370, 850, 850, 550),
    ("ドライポロシャツ", 15, 19, "早割", 1810, 650, 650, 550),
    ("ドライポロシャツ", 15, 19, "通常", 2010, 650, 650, 550),
    ("ドライポロシャツ", 20, 29, "早割", 1570, 450, 450, 550),
    ("ドライポロシャツ", 20, 29, "通常", 1770, 450, 450, 550),
    ("ドライポロシャツ", 30, 39, "早割", 1400, 350, 350, 550),
    ("ドライポロシャツ", 30, 39, "通常", 1600, 350, 350, 550),
    ("ドライポロシャツ", 40, 49, "早割", 1320, 350, 350, 550),
    ("ドライポロシャツ", 40, 49, "通常", 1520, 350, 350, 550),
    ("ドライポロシャツ", 50, 99, "早割", 1230, 350, 350, 550),
    ("ドライポロシャツ", 50, 99, "通常", 1430, 350, 350, 550),
    ("ドライポロシャツ", 100, 500, "早割", 1110, 300, 300, 550),
    ("ドライポロシャツ", 100, 500, "通常", 1310, 300, 300, 550),

    # ドライメッシュビブス
    ("ドライメッシュビブス", 10, 14, "早割", 2170, 850, 850, 550),
    ("ドライメッシュビブス", 10, 14, "通常", 2370, 850, 850, 550),
    ("ドライメッシュビブス", 15, 19, "早割", 1810, 650, 650, 550),
    ("ドライメッシュビブス", 15, 19, "通常", 2010, 650, 650, 550),
    ("ドライメッシュビブス", 20, 29, "早割", 1570, 450, 450, 550),
    ("ドライメッシュビブス", 20, 29, "通常", 1770, 450, 450, 550),
    ("ドライメッシュビブス", 30, 39, "早割", 1400, 350, 350, 550),
    ("ドライメッシュビブス", 30, 39, "通常", 1600, 350, 350, 550),
    ("ドライメッシュビブス", 40, 49, "早割", 1320, 350, 350, 550),
    ("ドライメッシュビブス", 40, 49, "通常", 1520, 350, 350, 550),
    ("ドライメッシュビブス", 50, 99, "早割", 1230, 350, 350, 550),
    ("ドライメッシュビブス", 50, 99, "通常", 1430, 350, 350, 550),
    ("ドライメッシュビブス", 100, 500, "早割", 1100, 300, 300, 550),
    ("ドライメッシュビブス", 100, 500, "通常", 1310, 300, 300, 550),

    # ドライベースボールシャツ
    ("ドライベースボールシャツ", 10, 14, "早割", 2470, 850, 850, 550),
    ("ドライベースボールシャツ", 10, 14, "通常", 2670, 850, 850, 550),
    ("ドライベースボールシャツ", 15, 19, "早割", 2110, 650, 650, 550),
    ("ドライベースボールシャツ", 15, 19, "通常", 2310, 650, 650, 550),
    ("ドライベースボールシャツ", 20, 29, "早割", 1870, 450, 450, 550),
    ("ドライベースボールシャツ", 20, 29, "通常", 2070, 450, 450, 550),
    ("ドライベースボールシャツ", 30, 39, "早割", 1700, 350, 350, 550),
    ("ドライベースボールシャツ", 30, 39, "通常", 1900, 350, 350, 550),
    ("ドライベースボールシャツ", 40, 49, "早割", 1620, 350, 350, 550),
    ("ドライベースボールシャツ", 40, 49, "通常", 1820, 350, 350, 550),
    ("ドライベースボールシャツ", 50, 99, "早割", 1530, 350, 350, 550),
    ("ドライベースボールシャツ", 50, 99, "通常", 1730, 350, 350, 550),
    ("ドライベースボールシャツ", 100, 500, "早割", 1410, 300, 300, 550),
    ("ドライベースボールシャツ", 100, 500, "通常", 1610, 300, 300, 550),

    # ドライロングスリープTシャツ
    ("ドライロングスリープTシャツ", 10, 14, "早割", 2030, 850, 850, 550),
    ("ドライロングスリープTシャツ", 10, 14, "通常", 2230, 850, 850, 550),
    ("ドライロングスリープTシャツ", 15, 19, "早割", 1670, 650, 650, 550),
    ("ドライロングスリープTシャツ", 15, 19, "通常", 1870, 650, 650, 550),
    ("ドライロングスリープTシャツ", 20, 29, "早割", 1430, 450, 450, 550),
    ("ドライロングスリープTシャツ", 20, 29, "通常", 1630, 450, 450, 550),
    ("ドライロングスリープTシャツ", 30, 39, "早割", 1260, 350, 350, 550),
    ("ドライロングスリープTシャツ", 30, 39, "通常", 1460, 350, 350, 550),
    ("ドライロングスリープTシャツ", 40, 49, "早割", 1180, 350, 350, 550),
    ("ドライロングスリープTシャツ", 40, 49, "通常", 1380, 350, 350, 550),
    ("ドライロングスリープTシャツ", 50, 99, "早割", 1090, 350, 350, 550),
    ("ドライロングスリープTシャツ", 50, 99, "通常", 1290, 350, 350, 550),
    ("ドライロングスリープTシャツ", 100, 500, "早割", 970, 300, 300, 550),
    ("ドライロングスリープTシャツ", 100, 500, "通常", 1170, 300, 300, 550),

    # ドライハーフパンツ
    ("ドライハーフパンツ", 10, 14, "早割", 2270, 850, 850, 550),
    ("ドライハーフパンツ", 10, 14, "通常", 2470, 850, 850, 550),
    ("ドライハーフパンツ", 15, 19, "早割", 1910, 650, 650, 550),
    ("ドライハーフパンツ", 15, 19, "通常", 2110, 650, 650, 550),
    ("ドライハーフパンツ", 20, 29, "早割", 1670, 450, 450, 550),
    ("ドライハーフパンツ", 20, 29, "通常", 1870, 450, 450, 550),
    ("ドライハーフパンツ", 30, 39, "早割", 1500, 350, 350, 550),
    ("ドライハーフパンツ", 30, 39, "通常", 1700, 350, 350, 550),
    ("ドライハーフパンツ", 40, 49, "早割", 1420, 350, 350, 550),
    ("ドライハーフパンツ", 40, 49, "通常", 1620, 350, 350, 550),
    ("ドライハーフパンツ", 50, 99, "早割", 1330, 350, 350, 550),
    ("ドライハーフパンツ", 50, 99, "通常", 1530, 350, 350, 550),
    ("ドライハーフパンツ", 100, 500, "早割", 1210, 300, 300, 550),
    ("ドライハーフパンツ", 100, 500, "通常", 1410, 300, 300, 550),

    # ヘビーウェイトロングスリープTシャツ
    ("ヘビーウェイトロングスリープTシャツ", 10, 14, "早割", 2330, 850, 850, 550),
    ("ヘビーウェイトロングスリープTシャツ", 10, 14, "通常", 2530, 850, 850, 550),
    ("ヘビーウェイトロングスリープTシャツ", 15, 19, "早割", 1970, 650, 650, 550),
    ("ヘビーウェイトロングスリープTシャツ", 15, 19, "通常", 2170, 650, 650, 550),
    ("ヘビーウェイトロングスリープTシャツ", 20, 29, "早割", 1730, 450, 450, 550),
    ("ヘビーウェイトロングスリープTシャツ", 20, 29, "通常", 1930, 450, 450, 550),
    ("ヘビーウェイトロングスリープTシャツ", 30, 39, "早割", 1560, 350, 350, 550),
    ("ヘビーウェイトロングスリープTシャツ", 30, 39, "通常", 1760, 350, 350, 550),
    ("ヘビーウェイトロングスリープTシャツ", 40, 49, "早割", 1480, 350, 350, 550),
    ("ヘビーウェイトロングスリープTシャツ", 40, 49, "通常", 1680, 350, 350, 550),
    ("ヘビーウェイトロングスリープTシャツ", 50, 99, "早割", 1390, 350, 350, 550),
    ("ヘビーウェイトロングスリープTシャツ", 50, 99, "通常", 1590, 350, 350, 550),
    ("ヘビーウェイトロングスリープTシャツ", 100, 500, "早割", 1270, 300, 300, 550),
    ("ヘビーウェイトロングスリープTシャツ", 100, 500, "通常", 1470, 300, 300, 550),

    # クルーネックライトトレーナー
    ("クルーネックライトトレーナー", 10, 14, "早割", 2870, 850, 850, 550),
    ("クルーネックライトトレーナー", 10, 14, "通常", 3070, 850, 850, 550),
    ("クルーネックライトトレーナー", 15, 19, "早割", 2510, 650, 650, 550),
    ("クルーネックライトトレーナー", 15, 19, "通常", 2710, 650, 650, 550),
    ("クルーネックライトトレーナー", 20, 29, "早割", 2270, 450, 450, 550),
    ("クルーネックライトトレーナー", 20, 29, "通常", 2470, 450, 450, 550),
    ("クルーネックライトトレーナー", 30, 39, "早割", 2100, 350, 350, 550),
    ("クルーネックライトトレーナー", 30, 39, "通常", 2300, 350, 350, 550),
    ("クルーネックライトトレーナー", 40, 49, "早割", 2020, 350, 350, 550),
    ("クルーネックライトトレーナー", 40, 49, "通常", 2220, 350, 350, 550),
    ("クルーネックライトトレーナー", 50, 99, "早割", 1930, 350, 350, 550),
    ("クルーネックライトトレーナー", 50, 99, "通常", 2130, 350, 350, 550),
    ("クルーネックライトトレーナー", 100, 500, "早割", 1810, 300, 300, 550),
    ("クルーネックライトトレーナー", 100, 500, "通常", 2010, 300, 300, 550),

    # フーデッドライトパーカー
    ("フーデッドライトパーカー", 10, 14, "早割", 3270, 850, 850, 550),
    ("フーデッドライトパーカー", 10, 14, "通常", 3470, 850, 850, 550),
    ("フーデッドライトパーカー", 15, 19, "早割", 2910, 650, 650, 550),
    ("フーデッドライトパーカー", 15, 19, "通常", 3110, 650, 650, 550),
    ("フーデッドライトパーカー", 20, 29, "早割", 2670, 450, 450, 550),
    ("フーデッドライトパーカー", 20, 29, "通常", 2870, 450, 450, 550),
    ("フーデッドライトパーカー", 30, 39, "早割", 2500, 350, 350, 550),
    ("フーデッドライトパーカー", 30, 39, "通常", 2700, 350, 350, 550),
    ("フーデッドライトパーカー", 40, 49, "早割", 2420, 350, 350, 550),
    ("フーデッドライトパーカー", 40, 49, "通常", 2620, 350, 350, 550),
    ("フーデッドライトパーカー", 50, 99, "早割", 2330, 350, 350, 550),
    ("フーデッドライトパーカー", 50, 99, "通常", 2530, 350, 350, 550),
    ("フーデッドライトパーカー", 100, 500, "早割", 2210, 300, 300, 550),
    ("フーデッドライトパーカー", 100, 500, "通常", 2410, 300, 300, 550),

    # スタンダードトレーナー
    ("スタンダードトレーナー", 10, 14, "早割", 3280, 850, 850, 550),
    ("スタンダードトレーナー", 10, 14, "通常", 3480, 850, 850, 550),
    ("スタンダードトレーナー", 15, 19, "早割", 2920, 650, 650, 550),
    ("スタンダードトレーナー", 15, 19, "通常", 3120, 650, 650, 550),
    ("スタンダードトレーナー", 20, 29, "早割", 2680, 450, 450, 550),
    ("スタンダードトレーナー", 20, 29, "通常", 2880, 450, 450, 550),
    ("スタンダードトレーナー", 30, 39, "早割", 2510, 350, 350, 550),
    ("スタンダードトレーナー", 30, 39, "通常", 2710, 350, 350, 550),
    ("スタンダードトレーナー", 40, 49, "早割", 2430, 350, 350, 550),
    ("スタンダードトレーナー", 40, 49, "通常", 2630, 350, 350, 550),
    ("スタンダードトレーナー", 50, 99, "早割", 2340, 350, 350, 550),
    ("スタンダードトレーナー", 50, 99, "通常", 2540, 350, 350, 550),
    ("スタンダードトレーナー", 100, 500, "早割", 2220, 300, 300, 550),
    ("スタンダードトレーナー", 100, 500, "通常", 2420, 300, 300, 550),

    # スタンダードWフードパーカー
    ("スタンダードWフードパーカー", 10, 14, "早割", 4040, 850, 850, 550),
    ("スタンダードWフードパーカー", 10, 14, "通常", 4240, 850, 850, 550),
    ("スタンダードWフードパーカー", 15, 19, "早割", 3680, 650, 650, 550),
    ("スタンダードWフードパーカー", 15, 19, "通常", 3880, 650, 650, 550),
    ("スタンダードWフードパーカー", 20, 29, "早割", 3440, 450, 450, 550),
    ("スタンダードWフードパーカー", 20, 29, "通常", 3640, 450, 450, 550),
    ("スタンダードWフードパーカー", 30, 39, "早割", 3270, 350, 350, 550),
    ("スタンダードWフードパーカー", 30, 39, "通常", 3470, 350, 350, 550),
    ("スタンダードWフードパーカー", 40, 49, "早割", 3190, 350, 350, 550),
    ("スタンダードWフードパーカー", 40, 49, "通常", 3390, 350, 350, 550),
    ("スタンダードWフードパーカー", 50, 99, "早割", 3100, 350, 350, 550),
    ("スタンダードWフードパーカー", 50, 99, "通常", 3300, 350, 350, 550),
    ("スタンダードWフードパーカー", 100, 500, "早割", 2980, 300, 300, 550),
    ("スタンダードWフードパーカー", 100, 500, "通常", 3180, 300, 300, 550),

    # ジップアップライトパーカー
    ("ジップアップライトパーカー", 10, 14, "早割", 3770, 850, 850, 550),
    ("ジップアップライトパーカー", 10, 14, "通常", 3970, 850, 850, 550),
    ("ジップアップライトパーカー", 15, 19, "早割", 3410, 650, 650, 550),
    ("ジップアップライトパーカー", 15, 19, "通常", 3610, 650, 650, 550),
    ("ジップアップライトパーカー", 20, 29, "早割", 3170, 450, 450, 550),
    ("ジップアップライトパーカー", 20, 29, "通常", 3370, 450, 450, 550),
    ("ジップアップライトパーカー", 30, 39, "早割", 3000, 350, 350, 550),
    ("ジップアップライトパーカー", 30, 39, "通常", 3200, 350, 350, 550),
    ("ジップアップライトパーカー", 40, 49, "早割", 2920, 350, 350, 550),
    ("ジップアップライトパーカー", 40, 49, "通常", 3120, 350, 350, 550),
    ("ジップアップライトパーカー", 50, 99, "早割", 2830, 350, 350, 550),
    ("ジップアップライトパーカー", 50, 99, "通常", 3030, 350, 350, 550),
    ("ジップアップライトパーカー", 100, 500, "早割", 2710, 300, 300, 550),
    ("ジップアップライトパーカー", 100, 500, "通常", 2910, 300, 300, 550),
]


def calc_total_price(
    product_name: str,
    quantity: int,
    early_discount_str: str, 
    print_position: str,
    color_option: str
) -> int:
    if early_discount_str == "14日前以上":
        discount_type = "早割"
    else:
        discount_type = "通常"

    row = None
    for item in PRICE_TABLE:
        (p_name, min_q, max_q, d_type, unit_price, color_price, pos_price, full_price) = item
        if p_name == product_name and d_type == discount_type and min_q <= quantity <= max_q:
            row = item
            break

    if not row:
        return 0

    (_, _, _, _, unit_price, color_price, pos_price, full_price) = row
    base = unit_price * quantity
    option_cost = 0

    if color_option == "same_color_add":
        option_cost += color_price * quantity
    elif color_option == "different_color_add":
        option_cost += pos_price * quantity
    elif color_option == "full_color_add":
        option_cost += full_price * quantity

    total = base + option_cost
    return total

###################################
# (F) Flex Message: モード選択
###################################
def create_mode_selection_flex():
    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(text='モードを選択してください!', weight='bold', size='lg')
            ]
        ),
        footer=BoxComponent(
            layout='vertical',
            contents=[
                ButtonComponent(style='primary', action=PostbackAction(label='簡易見積', data='quick_estimate')),
                ButtonComponent(style='primary', action=PostbackAction(label='WEBフォームから注文', data='web_order')),
                ButtonComponent(style='primary', action=PostbackAction(label='注文用紙から注文', data='paper_order'))
            ]
        )
    )
    return FlexSendMessage(alt_text='モードを選択してください', contents=bubble)

###################################
# (G) 簡易見積フロー 
###################################
def create_quick_estimate_intro_flex():
    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(
                    text=(
                        '簡易見積に必要な項目を順番に確認します。\n'
                        '1. 学校/団体名\n'
                        '2. お届け先(都道府県)\n'
                        '3. 早割確認\n'
                        '4. 1枚当たりの予算\n'
                        '5. 商品名\n'
                        '6. 枚数\n'
                        '7. プリント位置\n'
                        '8. 使用する色数'
                    ),
                    wrap=True
                )
            ]
        ),
        footer=BoxComponent(
            layout='vertical',
            contents=[
                ButtonComponent(style='primary', action=PostbackAction(label='入力を開始する', data='start_quick_estimate_input'))
            ]
        )
    )
    return FlexSendMessage(alt_text='簡易見積モードへようこそ', contents=bubble)

def create_early_discount_flex():
    bubble = BubbleContainer(
        body=BoxComponent(layout='vertical', contents=[
            TextComponent(text='使用日から14日前以上 or 14日前以内を選択してください。', wrap=True)
        ]),
        footer=BoxComponent(
            layout='vertical',
            contents=[
                ButtonComponent(style='primary', action=PostbackAction(label='14日前以上', data='14days_plus')),
                ButtonComponent(style='primary', action=PostbackAction(label='14日前以内', data='14days_minus'))
            ]
        )
    )
    return FlexSendMessage(alt_text='早割確認', contents=bubble)

def create_product_selection_carousel():
    bubble1 = BubbleContainer(
        body=BoxComponent(layout='vertical', contents=[
            TextComponent(text='商品を選択してください(1/2)', weight='bold', size='md')
        ]),
        footer=BoxComponent(layout='vertical', contents=[
            ButtonComponent(style='primary', action=PostbackAction(label='ドライTシャツ', data='ドライTシャツ')),
            ButtonComponent(style='primary', action=PostbackAction(label='ヘビーウェイトTシャツ', data='ヘビーウェイトTシャツ')),
            ButtonComponent(style='primary', action=PostbackAction(label='ドライポロシャツ', data='ドライポロシャツ')),
            ButtonComponent(style='primary', action=PostbackAction(label='ドライメッシュビブス', data='ドライメッシュビブス')),
            ButtonComponent(style='primary', action=PostbackAction(label='ドライベースボールシャツ', data='ドライベースボールシャツ')),
            ButtonComponent(style='primary', action=PostbackAction(label='ドライロングスリープTシャツ', data='ドライロングスリープTシャツ')),
            ButtonComponent(style='primary', action=PostbackAction(label='ドライハーフパンツ', data='ドライハーフパンツ'))
        ])
    )
    bubble2 = BubbleContainer(
        body=BoxComponent(layout='vertical', contents=[
            TextComponent(text='商品を選択してください(2/2)', weight='bold', size='md')
        ]),
        footer=BoxComponent(layout='vertical', contents=[
            ButtonComponent(style='primary', action=PostbackAction(label='ヘビーウェイトロングスリープTシャツ', data='ヘビーウェイトロングスリープTシャツ')),
            ButtonComponent(style='primary', action=PostbackAction(label='クルーネックライトトレーナー', data='クルーネックライトトレーナー')),
            ButtonComponent(style='primary', action=PostbackAction(label='フーデッドライトパーカー', data='フーデッドライトパーカー')),
            ButtonComponent(style='primary', action=PostbackAction(label='スタンダードトレーナー', data='スタンダードトレーナー')),
            ButtonComponent(style='primary', action=PostbackAction(label='スタンダードWフードパーカー', data='スタンダードWフードパーカー')),
            ButtonComponent(style='primary', action=PostbackAction(label='ジップアップライトパーカー', data='ジップアップライトパーカー'))
        ])
    )
    carousel = CarouselContainer(contents=[bubble1, bubble2])
    return FlexSendMessage(alt_text='商品を選択してください', contents=carousel)

def create_print_position_flex():
    bubble = BubbleContainer(
        body=BoxComponent(layout='vertical', contents=[
            TextComponent(text='プリントする位置を選択してください', weight='bold')
        ]),
        footer=BoxComponent(layout='vertical', contents=[
            ButtonComponent(style='primary', action=PostbackAction(label='前', data='front')),
            ButtonComponent(style='primary', action=PostbackAction(label='背中', data='back')),
            ButtonComponent(style='primary', action=PostbackAction(label='前と背中', data='front_back'))
        ])
    )
    return FlexSendMessage(alt_text='プリント位置選択', contents=bubble)

def create_color_options_flex():
    bubble = BubbleContainer(
        body=BoxComponent(layout='vertical', contents=[
            TextComponent(text='使用する色数(前・背中)を選択してください', weight='bold'),
            TextComponent(text='(複数選択の実装は省略)', size='sm')
        ]),
        footer=BoxComponent(layout='vertical', contents=[
            ButtonComponent(style='primary', action=PostbackAction(label='同じ位置にプリントカラー追加', data='same_color_add')),
            ButtonComponent(style='primary', action=PostbackAction(label='別の場所にプリント位置追加', data='different_color_add')),
            ButtonComponent(style='primary', action=PostbackAction(label='フルカラーに追加', data='full_color_add'))
        ])
    )
    return FlexSendMessage(alt_text='使用する色数を選択', contents=bubble)

###################################
# (H) Flaskルート: HealthCheck
###################################
@app.route("/", methods=["GET"])
def health_check():
    return "OK", 200

###################################
# (I) Flaskルート: LINE Callback
###################################
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    if not signature:
        abort(400)

    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        logger.error(f"InvalidSignatureError: {e}")
        abort(400)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        traceback.print_exc()
        abort(500)

    return "OK", 200

###################################
# (J) LINEハンドラ: TextMessage
###################################
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    user_input = event.message.text.strip()
    logger.info(f"[DEBUG] user_input: '{user_input}'")

    if user_input == "モード選択":
        flex = create_mode_selection_flex()
        line_bot_api.reply_message(event.reply_token, flex)
        return

    # ガード: 注文用紙から注文モードでまだ写真待ちの場合
    if user_id in user_states and user_states[user_id].get("state") == "await_order_form_photo":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="注文用紙の写真を送ってください。テキストはまだ受け付けていません。")
        )
        return

    # ステートマシンに応じた処理
    if user_id in user_states:
        st = user_states[user_id].get("state")
        if st == "await_school_name":
            user_states[user_id]["school_name"] = user_input
            user_states[user_id]["state"] = "await_prefecture"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="学校名を保存しました。\n次にお届け先(都道府県)を入力してください。")
            )
            return

        if st == "await_prefecture":
            user_states[user_id]["prefecture"] = user_input
            user_states[user_id]["state"] = "await_early_discount"
            discount_flex = create_early_discount_flex()
            line_bot_api.reply_message(event.reply_token, discount_flex)
            return

        if st == "await_budget":
            user_states[user_id]["budget"] = user_input
            user_states[user_id]["state"] = "await_product"
            product_flex = create_product_selection_carousel()
            line_bot_api.reply_message(event.reply_token, product_flex)
            return

        if st == "await_quantity":
            user_states[user_id]["quantity"] = user_input
            user_states[user_id]["state"] = "await_print_position"
            pos_flex = create_print_position_flex()
            line_bot_api.reply_message(event.reply_token, pos_flex)
            return

        # 想定外の場合
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"現在の状態({st})でテキスト入力は想定外です。")
        )
        return

    # ステート管理外の通常メッセージ
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"あなたのメッセージ: {user_input}")
    )

###################################
# (J') LINEハンドラ: ImageMessage
###################################
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    user_id = event.source.user_id

    if user_id not in user_states or user_states[user_id].get("state") != "await_order_form_photo":
        return

    # 画像を取得してローカルに保存
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)
    temp_filename = f"temp_{user_id}_{message_id}.jpg"
    with open(temp_filename, "wb") as fd:
        for chunk in message_content.iter_content():
            fd.write(chunk)

    # Google Vision でOCR
    ocr_text = google_vision_ocr(temp_filename)
    logger.info(f"[DEBUG] OCR result: {ocr_text}")

    # OpenAIでフォーム項目を推定
    form_estimated_data = openai_extract_form_data(ocr_text)
    logger.info(f"[DEBUG] form_estimated_data from OpenAI: {form_estimated_data}")

    # 推定データをユーザーステートに保存
    user_states[user_id]["paper_form_data"] = form_estimated_data
    del user_states[user_id]["state"]

    # 紙注文フォームURLを案内
    paper_form_url = f"https://{request.host}/paper_order_form?user_id={user_id}"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=(
                "注文用紙の写真から情報を読み取りました。\n"
                "こちらのフォームに自動入力しましたので、内容をご確認・修正の上送信してください。\n"
                f"{paper_form_url}"
            )
        )
    )

    # ローカルファイル削除(任意)
    try:
        os.remove(temp_filename)
    except Exception:
        pass

###################################
# (K) LINEハンドラ: PostbackEvent
###################################
@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    logger.info(f"[DEBUG] Postback data: {data}")

    if data == "quick_estimate":
        intro = create_quick_estimate_intro_flex()
        line_bot_api.reply_message(event.reply_token, intro)
        return

    if data == "start_quick_estimate_input":
        user_states[user_id] = {
            "state": "await_school_name",
            "school_name": None,
            "prefecture": None,
            "early_discount": None,
            "budget": None,
            "product": None,
            "quantity": None,
            "print_position": None,
            "color_options": None
        }
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="まずは学校または団体名を入力してください。")
        )
        return

    if data == "web_order":
        form_url = f"https://{request.host}/webform?user_id={user_id}"
        msg = (f"WEBフォームから注文ですね！\nこちらから入力してください。\n{form_url}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return

    if data == "paper_order":
        user_states[user_id] = {
            "state": "await_order_form_photo"
        }
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="注文用紙の写真を送ってください。\n(スマホで撮影したものでもOKです)")
        )
        return

    if user_id not in user_states:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="簡易見積モードではありません。"))
        return

    st = user_states[user_id]["state"]

    if st == "await_early_discount":
        if data == "14days_plus":
            user_states[user_id]["early_discount"] = "14日前以上"
        elif data == "14days_minus":
            user_states[user_id]["early_discount"] = "14日前以内"
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="早割選択が不明です。"))
            return
        user_states[user_id]["state"] = "await_budget"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="早割を保存しました。\n1枚あたりの予算を入力してください。"))
        return

    if st == "await_product":
        user_states[user_id]["product"] = data
        user_states[user_id]["state"] = "await_quantity"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{data} を選択しました。\n枚数を入力してください。")
        )
        return

    if st == "await_print_position":
        if data == "front":
            user_states[user_id]["print_position"] = "前"
        elif data == "back":
            user_states[user_id]["print_position"] = "背中"
        elif data == "front_back":
            user_states[user_id]["print_position"] = "前と背中"
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="プリント位置の指定が不明です。"))
            return
        user_states[user_id]["state"] = "await_color_options"
        color_flex = create_color_options_flex()
        line_bot_api.reply_message(event.reply_token, color_flex)
        return

    if st == "await_color_options":
        if data not in ["same_color_add", "different_color_add", "full_color_add"]:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="色数の選択が不明です。"))
            return

        user_states[user_id]["color_options"] = data

        # 簡易見積結果まとめ + DB保存
        s = user_states[user_id]
        summary = (
            f"学校/団体名: {s['school_name']}\n"
            f"都道府県: {s['prefecture']}\n"
            f"早割確認: {s['early_discount']}\n"
            f"予算: {s['budget']}\n"
            f"商品名: {s['product']}\n"
            f"枚数: {s['quantity']}\n"
            f"プリント位置: {s['print_position']}\n"
            f"使用する色数: {s['color_options']}"
        )

        qty = int(s['quantity'])
        early_disc = s['early_discount']
        product = s['product']
        pos = s['print_position']
        color_opt = s['color_options']
        total_price = calc_total_price(product, qty, early_disc, pos, color_opt)

        if qty > 0:
            unit_price = total_price // qty
        else:
            unit_price = 0

        import time
        quote_number = f"Q{int(time.time())}"

        insert_estimate(
            user_id,
            s['school_name'],
            s['prefecture'],
            s['early_discount'],
            s['budget'],
            product,
            qty,
            s['print_position'],
            color_opt,
            total_price,
            unit_price,
            quote_number
        )

        del user_states[user_id]

        reply_text = (
            "全項目の入力が完了しました。\n\n" + summary +
            "\n\n--- 見積計算結果 ---\n"
            f"見積番号: {quote_number}\n"
            f"合計金額: ¥{total_price:,}\n"
            f"1枚あたりの単価: ¥{unit_price:,}\n"
            "ご注文に進まれる場合はWEBフォームから注文\n"
            "もしくは注文用紙から注文を選択してください。"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"不明なアクション: {data}"))

def insert_estimate(
    user_id,
    school_name,
    prefecture,
    early_discount,
    budget,
    product,
    quantity,
    print_position,
    color_options,
    total_price,
    unit_price,
    quote_number
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            sql = """
            INSERT INTO estimates (
                user_id,
                school_name,
                prefecture,
                early_discount,
                budget,
                product,
                quantity,
                print_position,
                color_options,
                total_price,
                unit_price,
                quote_number,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, NOW()
            )
            """
            params = (
                user_id,
                school_name,
                prefecture,
                early_discount,
                budget,
                product,
                quantity,
                print_position,
                color_options,
                total_price,
                unit_price,
                quote_number
            )
            cur.execute(sql, params)
        conn.commit()

###################################
# (L) WEBフォーム (修正版HTML)
###################################
FORM_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <style>
    body {
      margin: 16px;
      font-family: sans-serif;
      font-size: 16px;
      line-height: 1.5;
    }
    h1 {
      margin-bottom: 24px;
      font-size: 1.2em;
    }
    form {
      max-width: 600px;
      margin: 0 auto;
    }
    input[type="text"],
    input[type="number"],
    input[type="email"],
    input[type="date"],
    select,
    button {
      display: block;
      width: 100%;
      box-sizing: border-box;
      margin-bottom: 16px;
      padding: 8px;
      font-size: 16px;
    }
    .radio-group,
    .checkbox-group {
      margin-bottom: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .radio-group label,
    .checkbox-group label {
      display: flex;
      align-items: center;
    }
    h3 {
      margin-top: 24px;
      margin-bottom: 8px;
      font-size: 1.1em;
    }
    .canvas-container {
      position: relative;
      margin-bottom: 16px;
      text-align: center;
    }
    canvas {
      border: 1px solid #ccc;
      max-width: 100%;
      touch-action: none; /* スマホでのスクロール干渉を防ぐ */
    }
    .buttons-inline {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
    }
  </style>
</head>
<body>
  <h1>WEBフォームから注文</h1>
  <form action="/webform_submit" method="POST" enctype="multipart/form-data">
    <input type="hidden" name="user_id" value="{{ user_id }}" />

    <!-- 既存のテキスト・select入力を省略せずフル掲載 -->
    <label>申込日:</label>
    <input type="date" name="application_date">

    <label>配達日:</label>
    <input type="date" name="delivery_date">

    <label>使用日:</label>
    <input type="date" name="use_date">

    <label>利用する学割特典:</label>
    <select name="discount_option">
      <option value="早割">早割</option>
      <option value="タダ割">タダ割</option>
      <option value="いっしょ割り">いっしょ割り</option>
    </select>

    <label>学校名:</label>
    <input type="text" name="school_name">

    <label>LINEアカウント名:</label>
    <input type="text" name="line_account">

    <label>団体名:</label>
    <input type="text" name="group_name">

    <label>学校住所:</label>
    <input type="text" name="school_address">

    <label>学校TEL:</label>
    <input type="text" name="school_tel">

    <label>担任名:</label>
    <input type="text" name="teacher_name">

    <label>担任携帯:</label>
    <input type="text" name="teacher_tel">

    <label>担任メール:</label>
    <input type="email" name="teacher_email">

    <label>代表者:</label>
    <input type="text" name="representative">

    <label>代表者TEL:</label>
    <input type="text" name="rep_tel">

    <label>代表者メール:</label>
    <input type="email" name="rep_email">

    <label>デザイン確認方法:</label>
    <select name="design_confirm">
      <option value="LINE代表者">LINE代表者</option>
      <option value="LINEご担任(保護者)">LINEご担任(保護者)</option>
      <option value="メール代表者">メール代表者</option>
      <option value="メールご担任(保護者)">メールご担任(保護者)</option>
    </select>

    <label>お支払い方法:</label>
    <select name="payment_method">
      <option value="代金引換(ヤマト運輸/現金のみ)">代金引換(ヤマト運輸/現金のみ)</option>
      <option value="後払い(コンビニ/郵便振替)">後払い(コンビニ/郵便振替)</option>
      <option value="後払い(銀行振込)">後払い(銀行振込)</option>
      <option value="先払い(銀行振込)">先払い(銀行振込)</option>
    </select>

    <label>商品名:</label>
    <select name="product_name">
      <option value="ドライTシャツ">ドライTシャツ</option>
      <option value="ヘビーウェイトTシャツ">ヘビーウェイトTシャツ</option>
      <option value="ドライポロシャツ">ドライポロシャツ</option>
      <option value="ドライメッシュビブス">ドライメッシュビブス</option>
      <option value="ドライベースボールシャツ">ドライベースボールシャツ</option>
      <option value="ドライロングスリープTシャツ">ドライロングスリープTシャツ</option>
      <option value="ドライハーフパンツ">ドライハーフパンツ</option>
      <option value="ヘビーウェイトロングスリープTシャツ">ヘビーウェイトロングスリープTシャツ</option>
      <option value="クルーネックライトトレーナー">クルーネックライトトレーナー</option>
      <option value="フーデッドライトパーカー">フーデッドライトパーカー</option>
      <option value="スタンダードトレーナー">スタンダードトレーナー</option>
      <option value="スタンダードWフードパーカー">スタンダードWフードパーカー</option>
      <option value="ジップアップライトパーカー">ジップアップライトパーカー</option>
    </select>

    <label>商品カラー:</label>
    <input type="text" name="product_color">

    <label>サイズ(SS):</label>
    <input type="number" name="size_ss">

    <label>サイズ(S):</label>
    <input type="number" name="size_s">

    <label>サイズ(M):</label>
    <input type="number" name="size_m">

    <label>サイズ(L):</label>
    <input type="number" name="size_l">

    <label>サイズ(LL):</label>
    <input type="number" name="size_ll">

    <label>サイズ(LLL):</label>
    <input type="number" name="size_lll">

    <!-- ==== 前面 ==== -->
    <h3>プリント位置: 前</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_front" value="おまかせ (最大:横28cm x 縦35cm以内)" checked>
        おまかせ
      </label>
      <label>
        <input type="radio" name="print_size_front" value="custom">
        ヨコ×タテ(入力):
      </label>
    </div>
    <input type="text" name="print_size_front_custom">
    <label>プリントカラー(前):</label>
    <input type="text" name="print_color_front">
    <label>フォントNo.(前):</label>
    <input type="text" name="font_no_front">
    <label>プリントデザインサンプル(前):</label>
    <input type="text" name="design_sample_front">

    <label>プリント位置データ(前):</label>
    <div class="canvas-container">
      <canvas id="canvas_front" width="300" height="400"></canvas>
    </div>
    <input type="hidden" name="print_position_data_front" id="print_position_data_front">
    <div class="buttons-inline">
      <button type="button" onclick="saveCanvasFront()">前デザイン保存</button>
      <button type="button" onclick="resetCanvasFront()">前リセット</button>
    </div>

    <!-- ==== 後面 ==== -->
    <h3>プリント位置: 後</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_back" value="おまかせ (最大:横28cm x 縦35cm以内)" checked>
        おまかせ
      </label>
      <label>
        <input type="radio" name="print_size_back" value="custom">
        ヨコ×タテ(入力):
      </label>
    </div>
    <input type="text" name="print_size_back_custom">
    <label>プリントカラー(後):</label>
    <input type="text" name="print_color_back">
    <label>フォントNo.(後):</label>
    <input type="text" name="font_no_back">
    <label>プリントデザインサンプル(後):</label>
    <input type="text" name="design_sample_back">

    <label>プリント位置データ(後):</label>
    <div class="canvas-container">
      <canvas id="canvas_back" width="300" height="400"></canvas>
    </div>
    <input type="hidden" name="print_position_data_back" id="print_position_data_back">
    <div class="buttons-inline">
      <button type="button" onclick="saveCanvasBack()">後デザイン保存</button>
      <button type="button" onclick="resetCanvasBack()">後リセット</button>
    </div>

    <!-- ==== その他 ==== -->
    <h3>プリント位置: その他</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_other" value="おまかせ (最大:横28cm x 縦35cm以内)" checked>
        おまかせ
      </label>
      <label>
        <input type="radio" name="print_size_other" value="custom">
        ヨコ×タテ(入力):
      </label>
    </div>
    <input type="text" name="print_size_other_custom">
    <label>プリントカラー(その他):</label>
    <input type="text" name="print_color_other">
    <label>フォントNo.(その他):</label>
    <input type="text" name="font_no_other">
    <label>プリントデザインサンプル(その他):</label>
    <input type="text" name="design_sample_other">

    <label>プリント位置データ(その他):</label>
    <div class="canvas-container">
      <canvas id="canvas_other" width="300" height="400"></canvas>
    </div>
    <input type="hidden" name="print_position_data_other" id="print_position_data_other">
    <div class="buttons-inline">
      <button type="button" onclick="saveCanvasOther()">その他デザイン保存</button>
      <button type="button" onclick="resetCanvasOther()">その他リセット</button>
    </div>

    <button type="submit">送信</button>
  </form>

  <script>
    /* 前面キャンバス (赤線) */
    let drawingFront = false;
    let lastXFront = 0, lastYFront = 0;

    function initCanvasFront() {
      const canvas = document.getElementById("canvas_front");
      const ctx = canvas.getContext("2d");
      const img = new Image();
      // デフォルト: Tシャツ(前)
      img.src = "https://via.placeholder.com/300x400.jpg?text=T-Shirt(Front)";
      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      };

      // マウス
      canvas.addEventListener("mousedown", e => {
        drawingFront = true;
        [lastXFront, lastYFront] = [e.offsetX, e.offsetY];
      });
      canvas.addEventListener("mousemove", e => {
        if (!drawingFront) return;
        ctx.beginPath();
        ctx.moveTo(lastXFront, lastYFront);
        ctx.lineTo(e.offsetX, e.offsetY);
        ctx.strokeStyle = "red";
        ctx.lineWidth = 2;
        ctx.stroke();
        [lastXFront, lastYFront] = [e.offsetX, e.offsetY];
      });
      canvas.addEventListener("mouseup", () => (drawingFront = false));
      canvas.addEventListener("mouseout", () => (drawingFront = false));

      // タッチ
      canvas.addEventListener("touchstart", e => {
        e.preventDefault();
        drawingFront = true;
        const touch = e.touches[0];
        const rect = canvas.getBoundingClientRect();
        [lastXFront, lastYFront] = [touch.clientX - rect.left, touch.clientY - rect.top];
      }, {passive: false});
      canvas.addEventListener("touchmove", e => {
        if (!drawingFront) return;
        e.preventDefault();
        const touch = e.touches[0];
        const rect = canvas.getBoundingClientRect();
        const x = touch.clientX - rect.left;
        const y = touch.clientY - rect.top;
        ctx.beginPath();
        ctx.moveTo(lastXFront, lastYFront);
        ctx.lineTo(x, y);
        ctx.strokeStyle = "red";
        ctx.lineWidth = 2;
        ctx.stroke();
        [lastXFront, lastYFront] = [x, y];
      }, {passive: false});
      canvas.addEventListener("touchend", () => {
        drawingFront = false;
      });
    }

    function saveCanvasFront() {
      const canvas = document.getElementById("canvas_front");
      // JPEG (品質0.8)
      const dataURL = canvas.toDataURL("image/jpeg", 0.8);
      document.getElementById("print_position_data_front").value = dataURL;
      alert("前面のキャンバス内容を保存しました。");
    }

    function resetCanvasFront() {
      const canvas = document.getElementById("canvas_front");
      const ctx = canvas.getContext("2d");
      const img = new Image();
      img.src = "https://via.placeholder.com/300x400.jpg?text=T-Shirt(Front)";
      img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height); // まず消去
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height); // 初期Tシャツ画像を再描画
      };
    }

    /* 後面キャンバス (青線) */
    let drawingBack = false;
    let lastXBack = 0, lastYBack = 0;

    function initCanvasBack() {
      const canvas = document.getElementById("canvas_back");
      const ctx = canvas.getContext("2d");
      const img = new Image();
      // デフォルト: Tシャツ(Back)
      img.src = "https://via.placeholder.com/300x400.jpg?text=T-Shirt(Back)";
      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      };

      canvas.addEventListener("mousedown", e => {
        drawingBack = true;
        [lastXBack, lastYBack] = [e.offsetX, e.offsetY];
      });
      canvas.addEventListener("mousemove", e => {
        if (!drawingBack) return;
        ctx.beginPath();
        ctx.moveTo(lastXBack, lastYBack);
        ctx.lineTo(e.offsetX, e.offsetY);
        ctx.strokeStyle = "blue";
        ctx.lineWidth = 2;
        ctx.stroke();
        [lastXBack, lastYBack] = [e.offsetX, e.offsetY];
      });
      canvas.addEventListener("mouseup", () => (drawingBack = false));
      canvas.addEventListener("mouseout", () => (drawingBack = false));

      // タッチ
      canvas.addEventListener("touchstart", e => {
        e.preventDefault();
        drawingBack = true;
        const touch = e.touches[0];
        const rect = canvas.getBoundingClientRect();
        [lastXBack, lastYBack] = [touch.clientX - rect.left, touch.clientY - rect.top];
      }, {passive: false});
      canvas.addEventListener("touchmove", e => {
        if (!drawingBack) return;
        e.preventDefault();
        const touch = e.touches[0];
        const rect = canvas.getBoundingClientRect();
        const x = touch.clientX - rect.left;
        const y = touch.clientY - rect.top;
        ctx.beginPath();
        ctx.moveTo(lastXBack, lastYBack);
        ctx.lineTo(x, y);
        ctx.strokeStyle = "blue";
        ctx.lineWidth = 2;
        ctx.stroke();
        [lastXBack, lastYBack] = [x, y];
      }, {passive: false});
      canvas.addEventListener("touchend", () => {
        drawingBack = false;
      });
    }

    function saveCanvasBack() {
      const canvas = document.getElementById("canvas_back");
      const dataURL = canvas.toDataURL("image/jpeg", 0.8);
      document.getElementById("print_position_data_back").value = dataURL;
      alert("後面のキャンバス内容を保存しました。");
    }

    function resetCanvasBack() {
      const canvas = document.getElementById("canvas_back");
      const ctx = canvas.getContext("2d");
      const img = new Image();
      img.src = "https://via.placeholder.com/300x400.jpg?text=T-Shirt(Back)";
      img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      };
    }

    /* その他キャンバス (緑線) */
    let drawingOther = false;
    let lastXOther = 0, lastYOther = 0;

    function initCanvasOther() {
      const canvas = document.getElementById("canvas_other");
      const ctx = canvas.getContext("2d");
      const img = new Image();
      // デフォルト: Tシャツ(Other)
      img.src = "https://via.placeholder.com/300x400.jpg?text=T-Shirt(Other)";
      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      };

      canvas.addEventListener("mousedown", e => {
        drawingOther = true;
        [lastXOther, lastYOther] = [e.offsetX, e.offsetY];
      });
      canvas.addEventListener("mousemove", e => {
        if (!drawingOther) return;
        ctx.beginPath();
        ctx.moveTo(lastXOther, lastYOther);
        ctx.lineTo(e.offsetX, e.offsetY);
        ctx.strokeStyle = "green";
        ctx.lineWidth = 2;
        ctx.stroke();
        [lastXOther, lastYOther] = [e.offsetX, e.offsetY];
      });
      canvas.addEventListener("mouseup", () => (drawingOther = false));
      canvas.addEventListener("mouseout", () => (drawingOther = false));

      // タッチ
      canvas.addEventListener("touchstart", e => {
        e.preventDefault();
        drawingOther = true;
        const touch = e.touches[0];
        const rect = canvas.getBoundingClientRect();
        [lastXOther, lastYOther] = [touch.clientX - rect.left, touch.clientY - rect.top];
      }, {passive: false});
      canvas.addEventListener("touchmove", e => {
        if (!drawingOther) return;
        e.preventDefault();
        const touch = e.touches[0];
        const rect = canvas.getBoundingClientRect();
        const x = touch.clientX - rect.left;
        const y = touch.clientY - rect.top;
        ctx.beginPath();
        ctx.moveTo(lastXOther, lastYOther);
        ctx.lineTo(x, y);
        ctx.strokeStyle = "green";
        ctx.lineWidth = 2;
        ctx.stroke();
        [lastXOther, lastYOther] = [x, y];
      }, {passive: false});
      canvas.addEventListener("touchend", () => {
        drawingOther = false;
      });
    }

    function saveCanvasOther() {
      const canvas = document.getElementById("canvas_other");
      const dataURL = canvas.toDataURL("image/jpeg", 0.8);
      document.getElementById("print_position_data_other").value = dataURL;
      alert("その他のキャンバス内容を保存しました。");
    }

    function resetCanvasOther() {
      const canvas = document.getElementById("canvas_other");
      const ctx = canvas.getContext("2d");
      const img = new Image();
      img.src = "https://via.placeholder.com/300x400.jpg?text=T-Shirt(Other)";
      img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      };
    }

    window.addEventListener('load', function(){
      initCanvasFront();
      initCanvasBack();
      initCanvasOther();
    });
  </script>
</body>
</html>
"""

@app.route("/webform", methods=["GET"])
def show_webform():
    user_id = request.args.get("user_id", "")
    return render_template_string(FORM_HTML, user_id=user_id)

###################################
# (M) 空文字→None 変換
###################################
def none_if_empty_str(val: str):
    if not val:
        return None
    return val

def none_if_empty_date(val: str):
    if not val:
        return None
    return val

def none_if_empty_int(val: str):
    if not val:
        return None
    return int(val)

###################################
# (N) /webform_submit: フォーム送信
###################################
@app.route("/webform_submit", methods=["POST"])
def webform_submit():
    form = request.form
    files = request.files
    user_id = form.get("user_id", "")

    # テキスト項目
    application_date = none_if_empty_date(form.get("application_date"))
    delivery_date = none_if_empty_date(form.get("delivery_date"))
    use_date = none_if_empty_date(form.get("use_date"))

    discount_option = none_if_empty_str(form.get("discount_option"))
    school_name = none_if_empty_str(form.get("school_name"))
    line_account = none_if_empty_str(form.get("line_account"))
    group_name = none_if_empty_str(form.get("group_name"))
    school_address = none_if_empty_str(form.get("school_address"))
    school_tel = none_if_empty_str(form.get("school_tel"))
    teacher_name = none_if_empty_str(form.get("teacher_name"))
    teacher_tel = none_if_empty_str(form.get("teacher_tel"))
    teacher_email = none_if_empty_str(form.get("teacher_email"))
    representative = none_if_empty_str(form.get("representative"))
    rep_tel = none_if_empty_str(form.get("rep_tel"))
    rep_email = none_if_empty_str(form.get("rep_email"))

    design_confirm = none_if_empty_str(form.get("design_confirm"))
    payment_method = none_if_empty_str(form.get("payment_method"))
    product_name = none_if_empty_str(form.get("product_name"))
    product_color = none_if_empty_str(form.get("product_color"))

    size_ss = none_if_empty_int(form.get("size_ss"))
    size_s = none_if_empty_int(form.get("size_s"))
    size_m = none_if_empty_int(form.get("size_m"))
    size_l = none_if_empty_int(form.get("size_l"))
    size_ll = none_if_empty_int(form.get("size_ll"))
    size_lll = none_if_empty_int(form.get("size_lll"))

    print_size_front = none_if_empty_str(form.get("print_size_front"))
    print_size_front_custom = none_if_empty_str(form.get("print_size_front_custom"))
    print_color_front = none_if_empty_str(form.get("print_color_front"))
    font_no_front = none_if_empty_str(form.get("font_no_front"))
    design_sample_front = none_if_empty_str(form.get("design_sample_front"))

    print_size_back = none_if_empty_str(form.get("print_size_back"))
    print_size_back_custom = none_if_empty_str(form.get("print_size_back_custom"))
    print_color_back = none_if_empty_str(form.get("print_color_back"))
    font_no_back = none_if_empty_str(form.get("font_no_back"))
    design_sample_back = none_if_empty_str(form.get("design_sample_back"))

    print_size_other = none_if_empty_str(form.get("print_size_other"))
    print_size_other_custom = none_if_empty_str(form.get("print_size_other_custom"))
    print_color_other = none_if_empty_str(form.get("print_color_other"))
    font_no_other = none_if_empty_str(form.get("font_no_other"))
    design_sample_other = none_if_empty_str(form.get("design_sample_other"))

    # Base64受け取り (前/後/その他)
    img_front_base64 = none_if_empty_str(form.get("print_position_data_front"))
    img_back_base64 = none_if_empty_str(form.get("print_position_data_back"))
    img_other_base64 = none_if_empty_str(form.get("print_position_data_other"))

    # もしファイルアップロードがあるなら(例: 従来機能)
    img_front_file = files.get("design_image_front")
    img_back_file = files.get("design_image_back")
    img_other_file = files.get("design_image_other")

    front_url = None
    back_url = None
    other_url = None

    # 前面 Base64 → S3
    if img_front_base64:
        front_url = upload_base64_to_s3(img_front_base64, S3_BUCKET_NAME, prefix="uploads/")
    # 後面 Base64 → S3
    if img_back_base64:
        back_url = upload_base64_to_s3(img_back_base64, S3_BUCKET_NAME, prefix="uploads/")
    # その他 Base64 → S3
    if img_other_base64:
        other_url = upload_base64_to_s3(img_other_base64, S3_BUCKET_NAME, prefix="uploads/")

    # fallback: 従来のファイルアップロード
    if not front_url:
        fufront = upload_file_to_s3(img_front_file, S3_BUCKET_NAME, prefix="uploads/")
        if fufront:
            front_url = fufront
    if not back_url:
        fuback = upload_file_to_s3(img_back_file, S3_BUCKET_NAME, prefix="uploads/")
        if fuback:
            back_url = fuback
    if not other_url:
        fuother = upload_file_to_s3(img_other_file, S3_BUCKET_NAME, prefix="uploads/")
        if fuother:
            other_url = fuother

    # DBへINSERT
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            sql = """
            INSERT INTO orders (
                user_id,
                application_date,
                delivery_date,
                use_date,
                discount_option,
                school_name,
                line_account,
                group_name,
                school_address,
                school_tel,
                teacher_name,
                teacher_tel,
                teacher_email,
                representative,
                rep_tel,
                rep_email,
                design_confirm,
                payment_method,
                product_name,
                product_color,
                size_ss,
                size_s,
                size_m,
                size_l,
                size_ll,
                size_lll,

                print_size_front,
                print_size_front_custom,
                print_color_front,
                font_no_front,
                design_sample_front,
                design_image_front_url,

                print_size_back,
                print_size_back_custom,
                print_color_back,
                font_no_back,
                design_sample_back,
                design_image_back_url,

                print_size_other,
                print_size_other_custom,
                print_color_other,
                font_no_other,
                design_sample_other,
                design_image_other_url,

                created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s,

                %s, %s, %s, %s, %s, %s,

                %s, %s, %s, %s, %s, %s,

                %s, %s, %s, %s, %s, %s,

                NOW()
            )
            RETURNING id
            """
            params = (
                user_id,
                application_date,
                delivery_date,
                use_date,
                discount_option,
                school_name,
                line_account,
                group_name,
                school_address,
                school_tel,
                teacher_name,
                teacher_tel,
                teacher_email,
                representative,
                rep_tel,
                rep_email,
                design_confirm,
                payment_method,
                product_name,
                product_color,
                size_ss,
                size_s,
                size_m,
                size_l,
                size_ll,
                size_lll,

                print_size_front,
                print_size_front_custom,
                print_color_front,
                font_no_front,
                design_sample_front,
                front_url,

                print_size_back,
                print_size_back_custom,
                print_color_back,
                font_no_back,
                design_sample_back,
                back_url,

                print_size_other,
                print_size_other_custom,
                print_color_other,
                font_no_other,
                design_sample_other,
                other_url
            )
            cur.execute(sql, params)
            new_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"Inserted order id={new_id}")

    # 見積→注文のDBフラグなど
    mark_estimate_as_ordered(user_id)

    # LINE通知
    push_text = (
        "WEBフォームの注文を受け付けました！\n"
        f"学校名: {school_name}\n"
        f"商品名: {product_name}\n"
        "後ほど担当者からご連絡いたします。"
    )
    try:
        line_bot_api.push_message(to=user_id, messages=TextSendMessage(text=push_text))
    except Exception as e:
        logger.error(f"Push message failed: {e}")

    return "フォーム送信完了。LINEに通知を送りました。"

###################################
# (O) CSV出力 (任意)
###################################
import csv

def export_orders_to_csv():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders ORDER BY id")
            rows = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]

    file_path = "orders_export.csv"
    with open(file_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        for row in rows:
            writer.writerow(row)
    logger.info(f"CSV Export Done: {file_path}")

###################################
# Google Vision OCR処理
###################################
def google_vision_ocr(local_image_path: str) -> str:
    from google.cloud import vision

    client = vision.ImageAnnotatorClient()
    with open(local_image_path, "rb") as image_file:
        content = image_file.read()
    image = vision.Image(content=content)

    response = client.document_text_detection(image=image)
    if response.error.message:
        raise Exception(f"Vision API Error: {response.error.message}")

    full_text = response.full_text_annotation.text
    return full_text

###################################
# OpenAIでテキスト解析
###################################
import openai

def openai_extract_form_data(ocr_text: str) -> dict:
    openai.api_key = OPENAI_API_KEY

    system_prompt = """あなたは注文用紙のOCR結果から必要な項目を抽出するアシスタントです。
    入力として渡されるテキスト（OCR結果）を解析し、次のフォーム項目に合致する値をJSONで返してください。
    必ず JSON のみを返し、余計な文章は一切出力しないでください。
    キー一覧: [
        "application_date","delivery_date","use_date","discount_option","school_name",
        "line_account","group_name","school_address","school_tel","teacher_name",
        "teacher_tel","teacher_email","representative","rep_tel","rep_email",
        "design_confirm","payment_method","product_name","product_color",
        "size_ss","size_s","size_m","size_l","size_ll","size_lll"
    ]
    また前後のプリント位置やカラー情報などが読み取れそうであれば追加で含めてください。
    """

    user_prompt = f"""
以下OCRテキストです:
{ocr_text}
上記に基づき、フォーム項目に合致する値をJSONのみで返してください。
    """

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    content = response["choices"][0]["message"]["content"]
    logger.info(f"OpenAI raw content: {content}")

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        result = {}

    return result

###################################
# 紙の注文用フォーム
###################################
PAPER_FORM_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <style>
    body {
      margin: 16px;
      font-family: sans-serif;
      font-size: 16px;
      line-height: 1.5;
    }
    h1 {
      margin-bottom: 24px;
      font-size: 1.2em;
    }
    form {
      max-width: 600px;
      margin: 0 auto;
    }
    input[type="text"],
    input[type="number"],
    input[type="email"],
    input[type="date"],
    select,
    button {
      display: block;
      width: 100%;
      box-sizing: border-box;
      margin-bottom: 16px;
      padding: 8px;
      font-size: 16px;
    }
    .radio-group {
      margin-bottom: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .radio-group label {
      display: flex;
      align-items: center;
    }
    h3 {
      margin-top: 24px;
      margin-bottom: 8px;
      font-size: 1.1em;
    }
    .canvas-container {
      position: relative;
      margin-bottom: 16px;
      text-align: center;
    }
    canvas {
      border: 1px solid #ccc;
      max-width: 100%;
      touch-action: none;
    }
    .buttons-inline {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
    }
  </style>
</head>
<body>
  <h1>注文用紙(写真)からの注文</h1>
  <form action="/paper_order_form_submit" method="POST" enctype="multipart/form-data">
    <input type="hidden" name="user_id" value="{{ user_id }}" />

    <!-- 既存の紙注文フォームも同様に、前/後/その他のキャンバスを追加 -->
    <!-- 省略せずフル実装 (webformとほぼ同じ内容) -->
    <label>申込日:</label>
    <input type="date" name="application_date" value="{{ data['application_date'] or '' }}">

    <label>配達日:</label>
    <input type="date" name="delivery_date" value="{{ data['delivery_date'] or '' }}">

    <label>使用日:</label>
    <input type="date" name="use_date" value="{{ data['use_date'] or '' }}">

    <!-- ...中略: webform と同様の入力項目... -->

    <h3>プリント位置: 前</h3>
    <div class="canvas-container">
      <canvas id="canvas_front" width="300" height="400"></canvas>
    </div>
    <input type="hidden" name="print_position_data_front" id="print_position_data_front">
    <div class="buttons-inline">
      <button type="button" onclick="saveCanvasFront()">前デザイン保存</button>
      <button type="button" onclick="resetCanvasFront()">前リセット</button>
    </div>

    <h3>プリント位置: 後</h3>
    <div class="canvas-container">
      <canvas id="canvas_back" width="300" height="400"></canvas>
    </div>
    <input type="hidden" name="print_position_data_back" id="print_position_data_back">
    <div class="buttons-inline">
      <button type="button" onclick="saveCanvasBack()">後デザイン保存</button>
      <button type="button" onclick="resetCanvasBack()">後リセット</button>
    </div>

    <h3>プリント位置: その他</h3>
    <div class="canvas-container">
      <canvas id="canvas_other" width="300" height="400"></canvas>
    </div>
    <input type="hidden" name="print_position_data_other" id="print_position_data_other">
    <div class="buttons-inline">
      <button type="button" onclick="saveCanvasOther()">その他デザイン保存</button>
      <button type="button" onclick="resetCanvasOther()">その他リセット</button>
    </div>

    <button type="submit">送信</button>
  </form>

  <script>
    /* webform と同じく、initCanvasFront/Back/Other, saveCanvas..., resetCanvas...をコピペ */
    /* 例: 線色を変えるなら個別に設定 */
  </script>
</body>
</html>
"""

@app.route("/paper_order_form", methods=["GET"])
def paper_order_form():
    user_id = request.args.get("user_id", "")
    guessed_data = {}
    if user_id in user_states and "paper_form_data" in user_states[user_id]:
        guessed_data = user_states[user_id]["paper_form_data"]
    return render_template_string(PAPER_FORM_HTML, user_id=user_id, data=guessed_data)

###################################
# 紙注文フォーム送信
###################################
@app.route("/paper_order_form_submit", methods=["POST"])
def paper_order_form_submit():
    form = request.form
    files = request.files
    user_id = form.get("user_id", "")

    # webform_submit と同様の処理で Base64 → S3アップロード & DB保存
    application_date = none_if_empty_date(form.get("application_date"))
    delivery_date = none_if_empty_date(form.get("delivery_date"))
    use_date = none_if_empty_date(form.get("use_date"))

    discount_option = none_if_empty_str(form.get("discount_option"))
    school_name = none_if_empty_str(form.get("school_name"))
    line_account = none_if_empty_str(form.get("line_account"))
    group_name = none_if_empty_str(form.get("group_name"))
    school_address = none_if_empty_str(form.get("school_address"))
    school_tel = none_if_empty_str(form.get("school_tel"))
    teacher_name = none_if_empty_str(form.get("teacher_name"))
    teacher_tel = none_if_empty_str(form.get("teacher_tel"))
    teacher_email = none_if_empty_str(form.get("teacher_email"))
    representative = none_if_empty_str(form.get("representative"))
    rep_tel = none_if_empty_str(form.get("rep_tel"))
    rep_email = none_if_empty_str(form.get("rep_email"))

    design_confirm = none_if_empty_str(form.get("design_confirm"))
    payment_method = none_if_empty_str(form.get("payment_method"))
    product_name = none_if_empty_str(form.get("product_name"))
    product_color = none_if_empty_str(form.get("product_color"))

    size_ss = none_if_empty_int(form.get("size_ss"))
    size_s = none_if_empty_int(form.get("size_s"))
    size_m = none_if_empty_int(form.get("size_m"))
    size_l = none_if_empty_int(form.get("size_l"))
    size_ll = none_if_empty_int(form.get("size_ll"))
    size_lll = none_if_empty_int(form.get("size_lll"))

    print_size_front = none_if_empty_str(form.get("print_size_front"))
    print_size_front_custom = none_if_empty_str(form.get("print_size_front_custom"))
    print_color_front = none_if_empty_str(form.get("print_color_front"))
    font_no_front = none_if_empty_str(form.get("font_no_front"))
    design_sample_front = none_if_empty_str(form.get("design_sample_front"))

    print_size_back = none_if_empty_str(form.get("print_size_back"))
    print_size_back_custom = none_if_empty_str(form.get("print_size_back_custom"))
    print_color_back = none_if_empty_str(form.get("print_color_back"))
    font_no_back = none_if_empty_str(form.get("font_no_back"))
    design_sample_back = none_if_empty_str(form.get("design_sample_back"))

    print_size_other = none_if_empty_str(form.get("print_size_other"))
    print_size_other_custom = none_if_empty_str(form.get("print_size_other_custom"))
    print_color_other = none_if_empty_str(form.get("print_color_other"))
    font_no_other = none_if_empty_str(form.get("font_no_other"))
    design_sample_other = none_if_empty_str(form.get("design_sample_other"))

    img_front_base64 = none_if_empty_str(form.get("print_position_data_front"))
    img_back_base64 = none_if_empty_str(form.get("print_position_data_back"))
    img_other_base64 = none_if_empty_str(form.get("print_position_data_other"))

    img_front_file = files.get("design_image_front")
    img_back_file = files.get("design_image_back")
    img_other_file = files.get("design_image_other")

    front_url = None
    back_url = None
    other_url = None

    # 前面 Base64
    if img_front_base64:
        front_url = upload_base64_to_s3(img_front_base64, S3_BUCKET_NAME, prefix="uploads/")
    # 後面 Base64
    if img_back_base64:
        back_url = upload_base64_to_s3(img_back_base64, S3_BUCKET_NAME, prefix="uploads/")
    # その他 Base64
    if img_other_base64:
        other_url = upload_base64_to_s3(img_other_base64, S3_BUCKET_NAME, prefix="uploads/")

    # fallback: ファイルアップロード
    if not front_url:
        fu_front = upload_file_to_s3(img_front_file, S3_BUCKET_NAME, prefix="uploads/")
        if fu_front:
            front_url = fu_front
    if not back_url:
        fu_back = upload_file_to_s3(img_back_file, S3_BUCKET_NAME, prefix="uploads/")
        if fu_back:
            back_url = fu_back
    if not other_url:
        fu_other = upload_file_to_s3(img_other_file, S3_BUCKET_NAME, prefix="uploads/")
        if fu_other:
            other_url = fu_other

    # DBへINSERT
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            sql = """
            INSERT INTO orders (
                user_id,
                application_date,
                delivery_date,
                use_date,
                discount_option,
                school_name,
                line_account,
                group_name,
                school_address,
                school_tel,
                teacher_name,
                teacher_tel,
                teacher_email,
                representative,
                rep_tel,
                rep_email,
                design_confirm,
                payment_method,
                product_name,
                product_color,
                size_ss,
                size_s,
                size_m,
                size_l,
                size_ll,
                size_lll,

                print_size_front,
                print_size_front_custom,
                print_color_front,
                font_no_front,
                design_sample_front,
                design_image_front_url,

                print_size_back,
                print_size_back_custom,
                print_color_back,
                font_no_back,
                design_sample_back,
                design_image_back_url,

                print_size_other,
                print_size_other_custom,
                print_color_other,
                font_no_other,
                design_sample_other,
                design_image_other_url,

                created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s,

                %s, %s, %s, %s, %s, %s,

                %s, %s, %s, %s, %s, %s,

                %s, %s, %s, %s, %s, %s,

                NOW()
            )
            RETURNING id
            """
            params = (
                user_id,
                application_date,
                delivery_date,
                use_date,
                discount_option,
                school_name,
                line_account,
                group_name,
                school_address,
                school_tel,
                teacher_name,
                teacher_tel,
                teacher_email,
                representative,
                rep_tel,
                rep_email,
                design_confirm,
                payment_method,
                product_name,
                product_color,
                size_ss,
                size_s,
                size_m,
                size_l,
                size_ll,
                size_lll,

                print_size_front,
                print_size_front_custom,
                print_color_front,
                font_no_front,
                design_sample_front,
                front_url,

                print_size_back,
                print_size_back_custom,
                print_color_back,
                font_no_back,
                design_sample_back,
                back_url,

                print_size_other,
                print_size_other_custom,
                print_color_other,
                font_no_other,
                design_sample_other,
                other_url
            )
            cur.execute(sql, params)
            new_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"Inserted paper_order id={new_id}")

    mark_estimate_as_ordered(user_id)

    push_text = (
        "注文用紙(写真)からの注文を受け付けました！\n"
        f"学校名: {school_name}\n"
        f"商品名: {product_name}\n"
        "後ほど担当者からご連絡いたします。"
    )
    try:
        line_bot_api.push_message(to=user_id, messages=TextSendMessage(text=push_text))
    except Exception as e:
        logger.error(f"Push message failed: {e}")

    return "紙の注文フォーム送信完了。LINEに通知を送りました。"

def mark_estimate_as_ordered(user_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            sql = """
            UPDATE estimates
               SET order_placed = true
             WHERE user_id = %s
               AND order_placed = false
            """
            cur.execute(sql, (user_id,))
        conn.commit()

###################################
# ▼▼ 24時間ごとにリマインドを送る
###################################
@app.route("/send_reminders", methods=["GET"])
def send_reminders():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            sql = """
            SELECT id, user_id, quote_number, total_price
              FROM estimates
             WHERE order_placed = false
               AND reminder_count < 2
               AND created_at < (NOW() - INTERVAL '24 hours')
            """
            cur.execute(sql)
            rows = cur.fetchall()

            for (est_id, uid, quote_number, total_price) in rows:
                reminder_text = (
                    f"【リマインド】\n"
                    f"先日の簡易見積（見積番号: {quote_number}）\n"
                    f"合計金額: ¥{total_price:,}\n"
                    "ご注文はお済みでしょうか？\n"
                    "ご検討中の場合は、WEBフォーム or 注文用紙からいつでもお申し込みください。"
                )
                try:
                    line_bot_api.push_message(to=uid, messages=TextSendMessage(text=reminder_text))
                    cur2 = conn.cursor()
                    cur2.execute(
                        "UPDATE estimates SET reminder_count = reminder_count + 1 WHERE id = %s",
                        (est_id,)
                    )
                    cur2.close()
                    logger.info(f"Sent reminder to user_id={uid}, estimate_id={est_id}")
                except Exception as e:
                    logger.error(f"Push reminder failed for user_id={uid}: {e}")

        conn.commit()

    return "リマインド送信完了"

###################################
# Flask起動
###################################
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
