﻿import os
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

###################################
# (E) 価格表と計算ロジック (既存)
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
    early_discount_str: str,  # "14日前以上" => "早割", それ以外 => "通常"
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
# (G) 簡易見積フロー (既存機能)
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

    # ▼▼ 追加: 「注文用紙から注文」で写真待ちの状態でテキストを受け取った場合のガード ▼▼
    if user_id in user_states and user_states[user_id].get("state") == "await_order_form_photo":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="注文用紙の写真を送ってください。テキストはまだ受け付けていません。")
        )
        return
    # ▲▲ 追加 ▲▲

    if user_id in user_states:
        st = user_states[user_id].get("state")
        # 以下、既存のステートマシン処理
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

        # 想定外
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"現在の状態({st})でテキスト入力は想定外です。")
        )
        return

    # どのステートでもない通常メッセージ
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"あなたのメッセージ: {user_input}")
    )

###################################
# (J') LINEハンドラ: ImageMessage
#     (注文用紙からの注文で写真をアップロードさせる機能)
###################################
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    user_id = event.source.user_id

    # 状態が "await_order_form_photo" 以外の場合はスルー
    if user_id not in user_states or user_states[user_id].get("state") != "await_order_form_photo":
        return

    # 画像取得
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)
    
    # 一時的にローカル保存する
    temp_filename = f"temp_{user_id}_{message_id}.jpg"
    with open(temp_filename, "wb") as fd:
        for chunk in message_content.iter_content():
            fd.write(chunk)

    # ローカルに保存した画像を使って Google Vision API OCR 処理
    ocr_text = google_vision_ocr(temp_filename)
    logger.info(f"[DEBUG] OCR result: {ocr_text}")

    # OpenAI API を呼び出して、webフォーム各項目に対応しそうな値を推定
    form_estimated_data = openai_extract_form_data(ocr_text)
    logger.info(f"[DEBUG] form_estimated_data from OpenAI: {form_estimated_data}")

    # 推定結果をユーザーごとの状態に保持しておき、フォーム表示の際に使う
    user_states[user_id]["paper_form_data"] = form_estimated_data
    # ステート終了
    del user_states[user_id]["state"]

    # ユーザーにフォームURLを案内し、修正・送信を促す
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

        del user_states[user_id]
        reply_text = (
            "全項目の入力が完了しました。\n\n" + summary +
            "\n\n--- 見積計算結果 ---\n"
            f"合計金額: ¥{total_price:,}\n"
            "（概算です。詳細は別途ご相談ください）"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"不明なアクション: {data}"))

###################################
# (L) WEBフォーム (修正後HTML)
###################################
FORM_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>WEBフォームから注文</title>
</head>
<body>
  <h1>WEBフォームから注文</h1>
  <!-- 画像アップロードに対応するため、enctypeをmultipart/form-data に設定 -->
  <form action="/webform_submit" method="POST" enctype="multipart/form-data">
    <input type="hidden" name="user_id" value="{{ user_id }}" />

    <p>申込日: <input type="date" name="application_date"></p>
    <p>配達日: <input type="date" name="delivery_date"></p>
    <p>使用日: <input type="date" name="use_date"></p>

    <p>利用する学割特典:
      <select name="discount_option">
        <option value="早割">早割</option>
        <option value="タダ割">タダ割</option>
        <option value="いっしょ割り">いっしょ割り</option>
      </select>
    </p>

    <p>学校名: <input type="text" name="school_name"></p>
    <p>LINEアカウント名: <input type="text" name="line_account"></p>
    <p>団体名: <input type="text" name="group_name"></p>
    <p>学校住所: <input type="text" name="school_address"></p>
    <p>学校TEL: <input type="text" name="school_tel"></p>
    <p>担任名: <input type="text" name="teacher_name"></p>
    <p>担任携帯: <input type="text" name="teacher_tel"></p>
    <p>担任メール: <input type="email" name="teacher_email"></p>
    <p>代表者: <input type="text" name="representative"></p>
    <p>代表者TEL: <input type="text" name="rep_tel"></p>
    <p>代表者メール: <input type="email" name="rep_email"></p>

    <p>デザイン確認方法:
      <select name="design_confirm">
        <option value="LINE代表者">LINE代表者</option>
        <option value="LINEご担任(保護者)">LINEご担任(保護者)</option>
        <option value="メール代表者">メール代表者</option>
        <option value="メールご担任(保護者)">メールご担任(保護者)</option>
      </select>
    </p>

    <p>お支払い方法:
      <select name="payment_method">
        <option value="代金引換(ヤマト運輸/現金のみ)">代金引換(ヤマト運輸/現金のみ)</option>
        <option value="後払い(コンビニ/郵便振替)">後払い(コンビニ/郵便振替)</option>
        <option value="後払い(銀行振込)">後払い(銀行振込)</option>
        <option value="先払い(銀行振込)">先払い(銀行振込)</option>
      </select>
    </p>

    <p>商品名:
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
    </p>
    <p>商品カラー: <input type="text" name="product_color"></p>
    <p>サイズ(SS): <input type="number" name="size_ss"></p>
    <p>サイズ(S): <input type="number" name="size_s"></p>
    <p>サイズ(M): <input type="number" name="size_m"></p>
    <p>サイズ(L): <input type="number" name="size_l"></p>
    <p>サイズ(LL): <input type="number" name="size_ll"></p>
    <p>サイズ(LLL): <input type="number" name="size_lll"></p>

    <h3>プリント位置: 前</h3>
    <p>プリントサイズ(前):
      <input type="radio" name="print_size_front" value="おまかせ (最大:横28cm x 縦35cm以内)" checked> おまかせ
      <input type="radio" name="print_size_front" value="custom"> ヨコcm x タテcmくらい(入力する):
      <input type="text" name="print_size_front_custom" placeholder="例: 20cm x 15cm">
    </p>
    <p>プリントカラー(前): <input type="text" name="print_color_front" placeholder="全てのカラーをご記入ください。計xx色"></p>
    <p>フォントNo.(前): <input type="text" name="font_no_front" placeholder="例: X-XX"></p>
    <p>プリントデザインサンプル(前): <input type="text" name="design_sample_front" placeholder="例: D-XXX"></p>
    <p>プリントデザインイメージデータ(前): <input type="file" name="design_image_front"></p>

    <h3>プリント位置: 後</h3>
    <p>プリントサイズ(後):
      <input type="radio" name="print_size_back" value="おまかせ (最大:横28cm x 縦35cm以内)" checked> おまかせ
      <input type="radio" name="print_size_back" value="custom"> ヨコcm x タテcmくらい(入力する):
      <input type="text" name="print_size_back_custom" placeholder="例: 20cm x 15cm">
    </p>
    <p>プリントカラー(後): <input type="text" name="print_color_back" placeholder="全てのカラーをご記入ください。計xx色"></p>
    <p>フォントNo.(後): <input type="text" name="font_no_back" placeholder="例: X-XX"></p>
    <p>プリントデザインサンプル(後): <input type="text" name="design_sample_back" placeholder="例: D-XXX"></p>
    <p>プリントデザインイメージデータ(後): <input type="file" name="design_image_back"></p>

    <h3>プリント位置: その他</h3>
    <p>プリントサイズ(その他):
      <input type="radio" name="print_size_other" value="おまかせ (最大:横28cm x 縦35cm以内)" checked> おまかせ
      <input type="radio" name="print_size_other" value="custom"> ヨコcm x タテcmくらい(入力する):
      <input type="text" name="print_size_other_custom" placeholder="例: 20cm x 15cm">
    </p>
    <p>プリントカラー(その他): <input type="text" name="print_color_other" placeholder="全てのカラーをご記入ください。計xx色"></p>
    <p>フォントNo.(その他): <input type="text" name="font_no_other" placeholder="例: X-XX"></p>
    <p>プリントデザインサンプル(その他): <input type="text" name="design_sample_other" placeholder="例: D-XXX"></p>
    <p>プリントデザインイメージデータ(その他): <input type="file" name="design_image_other"></p>

    <p><button type="submit">送信</button></p>
  </form>
</body>
</html>
"""

@app.route("/webform", methods=["GET"])
def show_webform():
    user_id = request.args.get("user_id", "")
    return render_template_string(FORM_HTML, user_id=user_id)

###################################
# (M) 空文字を None にする関数
###################################
def none_if_empty_str(val: str):
    """文字列入力が空なら None, そうでなければ文字列を返す"""
    if not val:
        return None
    return val

def none_if_empty_date(val: str):
    """日付カラム用: 空なら None、そうでなければそのまま文字列として渡す"""
    if not val:
        return None
    return val

def none_if_empty_int(val: str):
    """数値カラム用: 空なら None, それ以外はintに変換"""
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

    # ---------- テキスト項目を取得 (空文字はNone化) ----------
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

    # ▼▼ 新規追加項目(前) ▼▼
    print_size_front = none_if_empty_str(form.get("print_size_front"))
    print_size_front_custom = none_if_empty_str(form.get("print_size_front_custom"))
    print_color_front = none_if_empty_str(form.get("print_color_front"))
    font_no_front = none_if_empty_str(form.get("font_no_front"))
    design_sample_front = none_if_empty_str(form.get("design_sample_front"))

    # ▼▼ 新規追加項目(後) ▼▼
    print_size_back = none_if_empty_str(form.get("print_size_back"))
    print_size_back_custom = none_if_empty_str(form.get("print_size_back_custom"))
    print_color_back = none_if_empty_str(form.get("print_color_back"))
    font_no_back = none_if_empty_str(form.get("font_no_back"))
    design_sample_back = none_if_empty_str(form.get("design_sample_back"))

    # ▼▼ 新規追加項目(その他) ▼▼
    print_size_other = none_if_empty_str(form.get("print_size_other"))
    print_size_other_custom = none_if_empty_str(form.get("print_size_other_custom"))
    print_color_other = none_if_empty_str(form.get("print_color_other"))
    font_no_other = none_if_empty_str(form.get("font_no_other"))
    design_sample_other = none_if_empty_str(form.get("design_sample_other"))

    # ---------- 画像ファイル ----------
    img_front = files.get("design_image_front")
    img_back = files.get("design_image_back")
    img_other = files.get("design_image_other")

    # S3にアップロード → URL取得
    front_url = upload_file_to_s3(img_front, S3_BUCKET_NAME, prefix="uploads/")
    back_url = upload_file_to_s3(img_back, S3_BUCKET_NAME, prefix="uploads/")
    other_url = upload_file_to_s3(img_other, S3_BUCKET_NAME, prefix="uploads/")

    # DBに保存
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

    # フォーム送信完了 → Push通知
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
# (O) 例: CSV出力関数 (任意, 既存)
###################################
import csv

def export_orders_to_csv():
    """DBの orders テーブルをCSV形式で出力する例(ローカルファイル書き込み想定)"""
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
# ▼▼ 追加: Google Vision OCR処理
###################################
def google_vision_ocr(local_image_path: str) -> str:
    """
    Google Cloud Vision APIを用いて画像のOCRを行い、
    抽出されたテキスト全体を文字列で返すサンプル。
    ※ 認証キーなどは環境変数 GOOGLE_APPLICATION_CREDENTIALS を利用。
    """
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
# ▼▼ 追加: OpenAIでテキスト解析
###################################
import openai

def openai_extract_form_data(ocr_text: str) -> dict:
    """
    OCRテキストから注文フォーム項目を推定し、JSONを返す例。
    ここは既存のままです。
    """
    openai.api_key = OPENAI_API_KEY

    system_prompt = """あなたは注文用紙のOCR結果から必要な項目を抽出するアシスタントです。
    入力として渡されるテキスト（OCR結果）を解析し、次のフォーム項目に合致する値を抽出してJSONで返してください。
    必ず JSON のみを返し、余計な文章は一切出力しないでください。
    キー一覧: [
        "application_date","delivery_date","use_date","discount_option","school_name",
        "line_account","group_name","school_address","school_tel","teacher_name",
        "teacher_tel","teacher_email","representative","rep_tel","rep_email",
        "design_confirm","payment_method","product_name","product_color",
        "size_ss","size_s","size_m","size_l","size_ll","size_lll"
    ]
    追加で (前/後/その他) のプリントサイズ、カラー、フォントNo.,デザインサンプル等があれば推定してください。
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

    # JSONとしてパースを試みる
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        result = {}

    # 必要そうなキーが無い場合は空文字にするなど
    return result

###################################
# ▼▼ 修正後: 注文用紙フロー用フォーム
###################################
PAPER_FORM_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>注文用紙(写真)からの注文</title>
</head>
<body>
  <h1>注文用紙(写真)からの注文</h1>
  <form action="/paper_order_form_submit" method="POST" enctype="multipart/form-data">
    <input type="hidden" name="user_id" value="{{ user_id }}" />

    <p>申込日: <input type="date" name="application_date" value="{{ data['application_date'] or '' }}"></p>
    <p>配達日: <input type="date" name="delivery_date" value="{{ data['delivery_date'] or '' }}"></p>
    <p>使用日: <input type="date" name="use_date" value="{{ data['use_date'] or '' }}"></p>

    <p>利用する学割特典:
      <select name="discount_option">
        <option value="早割" {% if data['discount_option'] == '早割' %}selected{% endif %}>早割</option>
        <option value="タダ割" {% if data['discount_option'] == 'タダ割' %}selected{% endif %}>タダ割</option>
        <option value="いっしょ割り" {% if data['discount_option'] == 'いっしょ割り' %}selected{% endif %}>いっしょ割り</option>
      </select>
    </p>

    <p>学校名: <input type="text" name="school_name" value="{{ data['school_name'] or '' }}"></p>
    <p>LINEアカウント名: <input type="text" name="line_account" value="{{ data['line_account'] or '' }}"></p>
    <p>団体名: <input type="text" name="group_name" value="{{ data['group_name'] or '' }}"></p>
    <p>学校住所: <input type="text" name="school_address" value="{{ data['school_address'] or '' }}"></p>
    <p>学校TEL: <input type="text" name="school_tel" value="{{ data['school_tel'] or '' }}"></p>
    <p>担任名: <input type="text" name="teacher_name" value="{{ data['teacher_name'] or '' }}"></p>
    <p>担任携帯: <input type="text" name="teacher_tel" value="{{ data['teacher_tel'] or '' }}"></p>
    <p>担任メール: <input type="email" name="teacher_email" value="{{ data['teacher_email'] or '' }}"></p>
    <p>代表者: <input type="text" name="representative" value="{{ data['representative'] or '' }}"></p>
    <p>代表者TEL: <input type="text" name="rep_tel" value="{{ data['rep_tel'] or '' }}"></p>
    <p>代表者メール: <input type="email" name="rep_email" value="{{ data['rep_email'] or '' }}"></p>

    <p>デザイン確認方法:
      <select name="design_confirm">
        <option value="LINE代表者" {% if data['design_confirm'] == 'LINE代表者' %}selected{% endif %}>LINE代表者</option>
        <option value="LINEご担任(保護者)" {% if data['design_confirm'] == 'LINEご担任(保護者)' %}selected{% endif %}>LINEご担任(保護者)</option>
        <option value="メール代表者" {% if data['design_confirm'] == 'メール代表者' %}selected{% endif %}>メール代表者</option>
        <option value="メールご担任(保護者)" {% if data['design_confirm'] == 'メールご担任(保護者)' %}selected{% endif %}>メールご担任(保護者)</option>
      </select>
    </p>

    <p>お支払い方法:
      <select name="payment_method">
        <option value="代金引換(ヤマト運輸/現金のみ)" {% if data['payment_method'] == '代金引換(ヤマト運輸/現金のみ)' %}selected{% endif %}>代金引換(ヤマト運輸/現金のみ)</option>
        <option value="後払い(コンビニ/郵便振替)" {% if data['payment_method'] == '後払い(コンビニ/郵便振替)' %}selected{% endif %}>後払い(コンビニ/郵便振替)</option>
        <option value="後払い(銀行振込)" {% if data['payment_method'] == '後払い(銀行振込)' %}selected{% endif %}>後払い(銀行振込)</option>
        <option value="先払い(銀行振込)" {% if data['payment_method'] == '先払い(銀行振込)' %}selected{% endif %}>先払い(銀行振込)</option>
      </select>
    </p>

    <p>商品名:
      <select name="product_name">
        <option value="ドライTシャツ" {% if data['product_name'] == 'ドライTシャツ' %}selected{% endif %}>ドライTシャツ</option>
        <option value="ヘビーウェイトTシャツ" {% if data['product_name'] == 'ヘビーウェイトTシャツ' %}selected{% endif %}>ヘビーウェイトTシャツ</option>
        <option value="ドライポロシャツ" {% if data['product_name'] == 'ドライポロシャツ' %}selected{% endif %}>ドライポロシャツ</option>
        <option value="ドライメッシュビブス" {% if data['product_name'] == 'ドライメッシュビブス' %}selected{% endif %}>ドライメッシュビブス</option>
        <option value="ドライベースボールシャツ" {% if data['product_name'] == 'ドライベースボールシャツ' %}selected{% endif %}>ドライベースボールシャツ</option>
        <option value="ドライロングスリープTシャツ" {% if data['product_name'] == 'ドライロングスリープTシャツ' %}selected{% endif %}>ドライロングスリープTシャツ</option>
        <option value="ドライハーフパンツ" {% if data['product_name'] == 'ドライハーフパンツ' %}selected{% endif %}>ドライハーフパンツ</option>
        <option value="ヘビーウェイトロングスリープTシャツ" {% if data['product_name'] == 'ヘビーウェイトロングスリープTシャツ' %}selected{% endif %}>ヘビーウェイトロングスリープTシャツ</option>
        <option value="クルーネックライトトレーナー" {% if data['product_name'] == 'クルーネックライトトレーナー' %}selected{% endif %}>クルーネックライトトレーナー</option>
        <option value="フーデッドライトパーカー" {% if data['product_name'] == 'フーデッドライトパーカー' %}selected{% endif %}>フーデッドライトパーカー</option>
        <option value="スタンダードトレーナー" {% if data['product_name'] == 'スタンダードトレーナー' %}selected{% endif %}>スタンダードトレーナー</option>
        <option value="スタンダードWフードパーカー" {% if data['product_name'] == 'スタンダードWフードパーカー' %}selected{% endif %}>スタンダードWフードパーカー</option>
        <option value="ジップアップライトパーカー" {% if data['product_name'] == 'ジップアップライトパーカー' %}selected{% endif %}>ジップアップライトパーカー</option>
      </select>
    </p>

    <p>商品カラー: <input type="text" name="product_color" value="{{ data['product_color'] or '' }}"></p>
    <p>サイズ(SS): <input type="number" name="size_ss" value="{{ data['size_ss'] or '' }}"></p>
    <p>サイズ(S): <input type="number" name="size_s" value="{{ data['size_s'] or '' }}"></p>
    <p>サイズ(M): <input type="number" name="size_m" value="{{ data['size_m'] or '' }}"></p>
    <p>サイズ(L): <input type="number" name="size_l" value="{{ data['size_l'] or '' }}"></p>
    <p>サイズ(LL): <input type="number" name="size_ll" value="{{ data['size_ll'] or '' }}"></p>
    <p>サイズ(LLL): <input type="number" name="size_lll" value="{{ data['size_lll'] or '' }}"></p>

    <h3>プリント位置: 前</h3>
    <p>プリントサイズ(前):
      <input type="radio" name="print_size_front" value="おまかせ (最大:横28cm x 縦35cm以内)"
        {% if data['print_size_front'] == 'おまかせ (最大:横28cm x 縦35cm以内)' %}checked{% endif %}> おまかせ
      <input type="radio" name="print_size_front" value="custom"
        {% if data['print_size_front'] == 'custom' %}checked{% endif %}> ヨコcm x タテcmくらい(入力する):
      <input type="text" name="print_size_front_custom" placeholder="例: 20cm x 15cm"
        value="{{ data['print_size_front_custom'] or '' }}">
    </p>
    <p>プリントカラー(前):
      <input type="text" name="print_color_front" placeholder="全てのカラーをご記入ください。計xx色"
        value="{{ data['print_color_front'] or '' }}">
    </p>
    <p>フォントNo.(前):
      <input type="text" name="font_no_front" placeholder="例: X-XX"
        value="{{ data['font_no_front'] or '' }}">
    </p>
    <p>プリントデザインサンプル(前):
      <input type="text" name="design_sample_front" placeholder="例: D-XXX"
        value="{{ data['design_sample_front'] or '' }}">
    </p>
    <p>プリントデザインイメージデータ(前): <input type="file" name="design_image_front"></p>

    <h3>プリント位置: 後</h3>
    <p>プリントサイズ(後):
      <input type="radio" name="print_size_back" value="おまかせ (最大:横28cm x 縦35cm以内)"
        {% if data['print_size_back'] == 'おまかせ (最大:横28cm x 縦35cm以内)' %}checked{% endif %}> おまかせ
      <input type="radio" name="print_size_back" value="custom"
        {% if data['print_size_back'] == 'custom' %}checked{% endif %}> ヨコcm x タテcmくらい(入力する):
      <input type="text" name="print_size_back_custom" placeholder="例: 20cm x 15cm"
        value="{{ data['print_size_back_custom'] or '' }}">
    </p>
    <p>プリントカラー(後):
      <input type="text" name="print_color_back" placeholder="全てのカラーをご記入ください。計xx色"
        value="{{ data['print_color_back'] or '' }}">
    </p>
    <p>フォントNo.(後):
      <input type="text" name="font_no_back" placeholder="例: X-XX"
        value="{{ data['font_no_back'] or '' }}">
    </p>
    <p>プリントデザインサンプル(後):
      <input type="text" name="design_sample_back" placeholder="例: D-XXX"
        value="{{ data['design_sample_back'] or '' }}">
    </p>
    <p>プリントデザインイメージデータ(後): <input type="file" name="design_image_back"></p>

    <h3>プリント位置: その他</h3>
    <p>プリントサイズ(その他):
      <input type="radio" name="print_size_other" value="おまかせ (最大:横28cm x 縦35cm以内)"
        {% if data['print_size_other'] == 'おまかせ (最大:横28cm x 縦35cm以内)' %}checked{% endif %}> おまかせ
      <input type="radio" name="print_size_other" value="custom"
        {% if data['print_size_other'] == 'custom' %}checked{% endif %}> ヨコcm x タテcmくらい(入力する):
      <input type="text" name="print_size_other_custom" placeholder="例: 20cm x 15cm"
        value="{{ data['print_size_other_custom'] or '' }}">
    </p>
    <p>プリントカラー(その他):
      <input type="text" name="print_color_other" placeholder="全てのカラーをご記入ください。計xx色"
        value="{{ data['print_color_other'] or '' }}">
    </p>
    <p>フォントNo.(その他):
      <input type="text" name="font_no_other" placeholder="例: X-XX"
        value="{{ data['font_no_other'] or '' }}">
    </p>
    <p>プリントデザインサンプル(その他):
      <input type="text" name="design_sample_other" placeholder="例: D-XXX"
        value="{{ data['design_sample_other'] or '' }}">
    </p>
    <p>プリントデザインイメージデータ(その他): <input type="file" name="design_image_other"></p>

    <p><button type="submit">送信</button></p>
  </form>
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
# ▼▼ 紙の注文用フォーム送信
###################################
@app.route("/paper_order_form_submit", methods=["POST"])
def paper_order_form_submit():
    form = request.form
    files = request.files
    user_id = form.get("user_id", "")

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

    # ▼▼ 新規追加項目(前) ▼▼
    print_size_front = none_if_empty_str(form.get("print_size_front"))
    print_size_front_custom = none_if_empty_str(form.get("print_size_front_custom"))
    print_color_front = none_if_empty_str(form.get("print_color_front"))
    font_no_front = none_if_empty_str(form.get("font_no_front"))
    design_sample_front = none_if_empty_str(form.get("design_sample_front"))

    # ▼▼ 新規追加項目(後) ▼▼
    print_size_back = none_if_empty_str(form.get("print_size_back"))
    print_size_back_custom = none_if_empty_str(form.get("print_size_back_custom"))
    print_color_back = none_if_empty_str(form.get("print_color_back"))
    font_no_back = none_if_empty_str(form.get("font_no_back"))
    design_sample_back = none_if_empty_str(form.get("design_sample_back"))

    # ▼▼ 新規追加項目(その他) ▼▼
    print_size_other = none_if_empty_str(form.get("print_size_other"))
    print_size_other_custom = none_if_empty_str(form.get("print_size_other_custom"))
    print_color_other = none_if_empty_str(form.get("print_color_other"))
    font_no_other = none_if_empty_str(form.get("font_no_other"))
    design_sample_other = none_if_empty_str(form.get("design_sample_other"))

    img_front = files.get("design_image_front")
    img_back = files.get("design_image_back")
    img_other = files.get("design_image_other")

    front_url = upload_file_to_s3(img_front, S3_BUCKET_NAME, prefix="uploads/")
    back_url = upload_file_to_s3(img_back, S3_BUCKET_NAME, prefix="uploads/")
    other_url = upload_file_to_s3(img_other, S3_BUCKET_NAME, prefix="uploads/")

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

###################################
# Flask起動 (既存)
###################################
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
