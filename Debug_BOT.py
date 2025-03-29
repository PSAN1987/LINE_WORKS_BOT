import os
import json
import time
import uuid
import boto3

import gspread
from flask import Flask, request, abort, render_template_string
from oauth2client.service_account import ServiceAccountCredentials

# line-bot-sdk v2 系
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
)
from werkzeug.utils import secure_filename

app = Flask(__name__)

# -----------------------
# 環境変数取得
# -----------------------
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
SERVICE_ACCOUNT_FILE = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")
SPREADSHEET_KEY = os.environ.get("SPREADSHEET_KEY", "")

# S3アップロード用
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# -----------------------
# Google Sheets 接続
# -----------------------
def get_gspread_client():
    """
    環境変数 SERVICE_ACCOUNT_FILE (JSONパス or JSON文字列) から認証情報を取り出し、
    gspread クライアントを返す
    """
    if not SERVICE_ACCOUNT_FILE:
        raise ValueError("環境変数 GCP_SERVICE_ACCOUNT_JSON が設定されていません。")

    service_account_dict = json.loads(SERVICE_ACCOUNT_FILE)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_dict, scope)
    return gspread.authorize(credentials)

def get_or_create_worksheet(sheet, title):
    """
    スプレッドシート内で該当titleのワークシートを取得。
    なければ新規作成し、ヘッダを書き込み、全列を左揃えに設定する(可能な場合)。
    """
    try:
        ws = sheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        # 新規作成
        ws = sheet.add_worksheet(title=title, rows=2000, cols=100)

        # ヘッダ行を設定
        if title == "CatalogRequests":
            ws.update('A1:H1', [[
                "氏名", "郵便番号", "住所", "電話番号",
                "メールアドレス", "Insta/TikTok名",
                "在籍予定の学校名と学年", "その他(質問・要望)"
            ]])

        elif title == "簡易見積":
            ws.update('A1:L1', [[
                "日時", "見積番号", "ユーザーID",
                "使用日(割引区分)", "予算", "商品名", "枚数",
                "プリント位置", "色数", "背ネーム",
                "合計金額", "単価"
            ]])

        elif title == "Orders":
            ws = sheet.add_worksheet(title=title, rows=2000, cols=100)

            # 52 列あるので A1:Z1 ではなく A1:AZ1 が必要
            ws.update('A1:AZ1', [[
                "申込日", "配達日", "使用日", "学割特典", "学校名", "LINEアカウント名",
                "団体名", "学校住所", "学校TEL", "担任名", "担任携帯", "担任メール",
                "代表者名", "代表者TEL", "代表者メール", "デザイン確認方法", "お支払い方法",
                "商品名", "商品カラー",
                "サイズ(SS)", "サイズ(S)", "サイズ(M)", "サイズ(L)", "サイズ(LL)", "サイズ(LLL)",
                "前プリントサイズ", "前プリントサイズ指定",
                "前プリントカラー", "前フォントNo", "前デザインサンプル", "前位置データURL",
                "前位置選択",
                "後プリントサイズ", "後プリントサイズ指定",
                "後プリントカラー", "後フォントNo", "後デザインサンプル", "後位置データURL",
                "後位置選択",
                "その他プリントサイズ", "その他プリントサイズ指定",
                "その他プリントカラー", "その他フォントNo", "その他デザインサンプル", "その他位置データURL",
                "背ネーム番号プリント", "追加デザイン位置", "追加デザイン画像URL",
                "合計金額", "単価", "注文番号", "ユーザーID"
            ]])
    return ws

# -----------------------
# S3アップロード機能
# -----------------------
def upload_file_to_s3(file_storage, s3_bucket, prefix="uploads/"):
    """
    file_storage: FlaskのFileStorage (request.files['...'])
    s3_bucket: 保存先のS3バケット
    prefix: アップロードパス
    戻り値: アップロード後のS3ファイルURL (無い場合は空文字)
    """
    if not file_storage or file_storage.filename == "":
        return ""

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

# -----------------------
# カタログ申し込みフォーム
# -----------------------
def write_to_spreadsheet_for_catalog(form_data: dict):
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_KEY)
    worksheet = get_or_create_worksheet(sh, "CatalogRequests")

    new_row = [
        form_data.get("name", ""),
        form_data.get("postal_code", ""),
        form_data.get("address", ""),
        form_data.get("phone", ""),
        form_data.get("email", ""),
        form_data.get("sns_account", ""),
        form_data.get("school_grade", ""),
        form_data.get("other", ""),
    ]
    worksheet.append_row(new_row, value_input_option="USER_ENTERED")


# -----------------------
# PRICE_TABLE と 簡易見積
# -----------------------
PRICE_TABLE = [
    {"item": "ドライTシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 1830, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 2030, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 1470, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 1670, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 1230, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 1430, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 1060, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 1260, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 980, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 1180, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 890, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 1090, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 770, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライTシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 970, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "ヘビーウェイトTシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 1970, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 2170, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 1610, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 1810, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 1370, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 1570, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 1200, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 1400, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 1120, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 1320, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 1030, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 1230, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 910, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトTシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 1100, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "ドライポロシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 2170, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 2370, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 1810, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 2010, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 1570, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 1770, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 1400, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 1600, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 1320, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 1520, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 1230, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 1430, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 1110, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライポロシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 1310, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "ドライメッシュビブス", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 2170, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 2370, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 1810, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 2010, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 1570, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 1770, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 1400, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 1600, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 1320, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 1520, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 1230, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 1430, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 1100, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライメッシュビブス", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 1310, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "ドライベースボールシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 2470, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 2670, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 2110, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 2310, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 1870, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 2070, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 1700, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 1900, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 1620, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 1820, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 1530, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 1730, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 1410, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライベースボールシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 1610, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "ドライロングスリープTシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 2030, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 2230, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 1670, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 1870, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 1430, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 1630, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 1260, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 1460, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 1180, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 1380, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 1090, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 1290, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 970, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライロングスリープTシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 1170, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "ドライハーフパンツ", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 2270, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 2470, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 1910, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 2110, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 1670, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 1870, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 1500, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 1700, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 1420, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 1620, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 1330, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 1530, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 1210, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ドライハーフパンツ", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 1410, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 2330, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 2530, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 1970, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 2170, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 1730, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 1930, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 1560, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 1760, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 1480, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 1680, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 1390, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 1590, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 1270, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ヘビーウェイトロングスリープTシャツ", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 1470, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "クルーネックライトトレーナー", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 2870, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 3070, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 2510, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 2710, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 2270, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 2470, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 2100, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 2300, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 2020, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 2220, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 1930, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 2130, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 1810, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "クルーネックライトトレーナー", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 2010, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "フーデッドライトパーカー", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 3270, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 3470, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 2910, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 3110, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 2670, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 2870, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 2500, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 2700, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 2420, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 2620, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 2330, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 2530, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 2210, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "フーデッドライトパーカー", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 2410, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "スタンダードトレーナー", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 3280, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 3480, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 2920, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 3120, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 2680, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 2880, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 2510, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 2710, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 2430, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 2630, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 2340, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 2540, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 2220, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードトレーナー", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 2420, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "スタンダードWフードパーカー", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 4040, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 4240, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 3680, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 3880, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 3440, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 3640, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 3270, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 3470, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 3190, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 3390, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 3100, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 3300, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 2980, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "スタンダードWフードパーカー", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 3180, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},

    {"item": "ジップアップライトパーカー", "min_qty": 10, "max_qty": 14, "discount_type": "早割", "unit_price": 3770, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 10, "max_qty": 14, "discount_type": "通常", "unit_price": 3970, "pos_add": 850, "color_add": 850, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 15, "max_qty": 19, "discount_type": "早割", "unit_price": 3410, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 15, "max_qty": 19, "discount_type": "通常", "unit_price": 3610, "pos_add": 650, "color_add": 650, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 20, "max_qty": 29, "discount_type": "早割", "unit_price": 3170, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 20, "max_qty": 29, "discount_type": "通常", "unit_price": 3370, "pos_add": 450, "color_add": 450, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 30, "max_qty": 39, "discount_type": "早割", "unit_price": 3000, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 30, "max_qty": 39, "discount_type": "通常", "unit_price": 3200, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 40, "max_qty": 49, "discount_type": "早割", "unit_price": 2920, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 40, "max_qty": 49, "discount_type": "通常", "unit_price": 3120, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 50, "max_qty": 99, "discount_type": "早割", "unit_price": 2830, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 50, "max_qty": 99, "discount_type": "通常", "unit_price": 3030, "pos_add": 350, "color_add": 350, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 100, "max_qty": 500, "discount_type": "早割", "unit_price": 2710, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
    {"item": "ジップアップライトパーカー", "min_qty": 100, "max_qty": 500, "discount_type": "通常", "unit_price": 2910, "pos_add": 300, "color_add": 300, "fullcolor_add": 550, "set_name_num": 900, "big_name": 550, "big_num": 550},
]

COLOR_COST_MAP = {
    "前 or 背中 1色": (0, 0),
    "前 or 背中 2色": (1, 0),
    "前 or 背中 フルカラー": (0, 1),
    "前と背中 前1色 背中1色": (0, 0),
    "前と背中 前2色 背中1色": (1, 0),
    "前と背中 前1色 背中2色": (1, 0),
    "前と背中 前2色 背中2色": (2, 0),
    "前と背中 フルカラー": (0, 2),
}

user_estimate_sessions = {}  # 見積フロー管理簡易セッション


def write_estimate_to_spreadsheet(user_id, estimate_data, total_price, unit_price):
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_KEY)
    worksheet = get_or_create_worksheet(sh, "簡易見積")

    quote_number = str(int(time.time()))

    new_row = [
        time.strftime("%Y/%m/%d %H:%M:%S"),
        quote_number,
        user_id,
        f"{estimate_data['usage_date']}({estimate_data['discount_type']})",
        estimate_data['budget'],
        estimate_data['item'],
        estimate_data['quantity'],
        estimate_data['print_position'],
        estimate_data['color_count'],
        estimate_data['back_name'],
        f"¥{total_price:,}",
        f"¥{unit_price:,}"
    ]
    worksheet.append_row(new_row, value_input_option="USER_ENTERED")
    return quote_number


def find_price_row(item_name, discount_type, quantity):
    for row in PRICE_TABLE:
        if (row["item"] == item_name
            and row["discount_type"] == discount_type
            and row["min_qty"] <= quantity <= row["max_qty"]):
            return row
    return None


def calculate_estimate(estimate_data):
    item_name = estimate_data['item']
    discount_type = estimate_data['discount_type']
    quantity = int(estimate_data['quantity'])
    print_position = estimate_data['print_position']
    color_choice = estimate_data['color_count']
    back_name = estimate_data['back_name']

    row = find_price_row(item_name, discount_type, quantity)
    if row is None:
        return 0, 0

    base_price = row["unit_price"]
    if print_position in ["前のみ","背中のみ"]:
        pos_add = 0
    else:
        pos_add = row["pos_add"]

    color_add_count, fullcolor_add_count = COLOR_COST_MAP[color_choice]
    color_fee = color_add_count * row["color_add"] + fullcolor_add_count * row["fullcolor_add"]

    if back_name == "ネーム&背番号セット":
        back_name_fee = row["set_name_num"]
    elif back_name == "ネーム(大)":
        back_name_fee = row["big_name"]
    elif back_name == "番号(大)":
        back_name_fee = row["big_num"]
    else:
        back_name_fee = 0

    unit_price = base_price + pos_add + color_fee + back_name_fee
    total_price = unit_price * quantity
    return total_price, unit_price


# -----------------------
# Flexメッセージ (見積フロー)
# -----------------------
from linebot.models import FlexSendMessage

def flex_usage_date():
    bubble = {
        "type": "bubble",
        "hero": {
            "type": "box","layout": "vertical","contents": [
                {
                    "type": "text","text": "❶使用日","weight": "bold","size": "lg","align": "center"
                },
                {
                    "type": "text",
                    "text": "大会やイベントで使用する日程を教えてください。(注文日が14日前以上なら早割)",
                    "size": "sm","wrap": True
                }
            ]
        },
        "footer": {
            "type": "box","layout": "vertical","spacing": "sm","contents": [
                {
                    "type": "button","style": "primary","height": "sm",
                    "action": {"type": "message","label": "14日前以上","text": "14日前以上"}
                },
                {
                    "type": "button","style": "primary","height": "sm",
                    "action": {"type": "message","label": "14日前以内","text": "14日前以内"}
                }
            ],
            "flex": 0
        }
    }
    return FlexSendMessage(alt_text="使用日を選択してください", contents=bubble)

def flex_budget():
    budgets = ["1,000円", "2,000円", "3,000円", "4,000円", "5,000円"]
    buttons = []
    for b in budgets:
        buttons.append({
            "type": "button","style": "primary","height": "sm",
            "action": {"type": "message","label": b,"text": b}
        })
    bubble = {
        "type":"bubble",
        "hero":{
            "type":"box","layout":"vertical","contents":[
                {"type":"text","text":"❷1枚当たりの予算","weight":"bold","size":"lg","align":"center"},
                {"type":"text","text":"ご希望の1枚あたり予算を選択してください。","size":"sm","wrap":True}
            ]
        },
        "footer":{
            "type":"box","layout":"vertical","spacing":"sm","contents":buttons,"flex":0
        }
    }
    return FlexSendMessage(alt_text="予算を選択してください", contents=bubble)

def flex_item_select():
    items = [
        "ドライTシャツ","ヘビーウェイトTシャツ","ドライポロシャツ","ドライメッシュビブス",
        "ドライベースボールシャツ","ドライロングスリープTシャツ","ドライハーフパンツ",
        "ヘビーウェイトロングスリープTシャツ","クルーネックライトトレーナー",
        "フーデッドライトパーカー","スタンダードトレーナー","スタンダードWフードパーカー",
        "ジップアップライトパーカー"
    ]
    item_bubbles = []
    chunk_size = 5
    for i in range(0, len(items), chunk_size):
        chunk_part = items[i:i+chunk_size]
        btns = []
        for it in chunk_part:
            btns.append({
                "type":"button","style":"primary","height":"sm",
                "action":{"type":"message","label":it,"text":it}
            })
        bubble = {
            "type":"bubble",
            "hero":{
                "type":"box","layout":"vertical","contents":[
                    {"type":"text","text":"❸商品名","weight":"bold","size":"lg","align":"center"},
                    {"type":"text","text":"ご希望の商品を選択してください。","size":"sm","wrap":True}
                ]
            },
            "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":btns}
        }
        item_bubbles.append(bubble)
    carousel = {"type":"carousel","contents":item_bubbles}
    return FlexSendMessage(alt_text="商品名を選択してください", contents=carousel)

def flex_quantity():
    quantities = ["10","20","30","40","50","100"]
    btns = []
    for q in quantities:
        btns.append({
            "type":"button","style":"primary","height":"sm",
            "action":{"type":"message","label":q,"text":q}
        })
    bubble = {
        "type":"bubble",
        "hero":{
            "type":"box","layout":"vertical","contents":[
                {"type":"text","text":"❹枚数","weight":"bold","size":"lg","align":"center"},
                {"type":"text","text":"必要枚数を選択してください。","size":"sm","wrap":True}
            ]
        },
        "footer":{
            "type":"box","layout":"vertical","spacing":"sm","contents":btns
        }
    }
    return FlexSendMessage(alt_text="必要枚数を選択してください", contents=bubble)

def flex_print_position():
    positions = ["前のみ","背中のみ","前と背中"]
    btns = []
    for p in positions:
        btns.append({
            "type":"button","style":"primary","height":"sm",
            "action":{"type":"message","label":p,"text":p}
        })
    bubble = {
        "type":"bubble",
        "hero":{
            "type":"box","layout":"vertical","contents":[
                {"type":"text","text":"❺プリント位置","weight":"bold","size":"lg","align":"center"},
                {"type":"text","text":"プリントを入れる箇所を選択してください。","size":"sm","wrap":True}
            ]
        },
        "footer":{
            "type":"box","layout":"vertical","spacing":"sm","contents":btns
        }
    }
    return FlexSendMessage(alt_text="プリント位置を選択してください", contents=bubble)

def flex_color_count():
    color_list = [
        "前 or 背中 1色","前 or 背中 2色","前 or 背中 フルカラー",
        "前と背中 前1色 背中1色","前と背中 前2色 背中1色",
        "前と背中 前1色 背中2色","前と背中 前2色 背中2色","前と背中 フルカラー"
    ]
    chunk_size = 4
    color_bubbles = []
    for i in range(0, len(color_list), chunk_size):
        chunk_part = color_list[i:i+chunk_size]
        btns = []
        for c in chunk_part:
            btns.append({
                "type":"button","style":"primary","height":"sm",
                "action":{"type":"message","label":c[:12],"text":c}
            })
        bubble = {
            "type":"bubble",
            "hero":{
                "type":"box","layout":"vertical","contents":[
                    {"type":"text","text":"❻色数","weight":"bold","size":"lg","align":"center"},
                    {"type":"text","text":"プリントの色数を選択してください。","size":"sm","wrap":True}
                ]
            },
            "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":btns}
        }
        color_bubbles.append(bubble)
    carousel = {"type":"carousel","contents":color_bubbles}
    return FlexSendMessage(alt_text="色数を選択してください", contents=carousel)

def flex_back_name():
    names = ["ネーム&背番号セット","ネーム(大)","番号(大)","背ネーム・番号を使わない"]
    btns = []
    for nm in names:
        btns.append({
            "type":"button","style":"primary","height":"sm",
            "action":{"type":"message","label":nm,"text":nm}
        })
    bubble = {
        "type":"bubble",
        "hero":{
            "type":"box","layout":"vertical","contents":[
                {"type":"text","text":"❼背ネーム・番号","weight":"bold","size":"lg","align":"center"},
                {"type":"text","text":"背ネームや番号を入れる場合は選択してください。","size":"sm","wrap":True},
                {"type":"text","text":"不要な場合は「背ネーム・番号を使わない」を選択してください。","size":"sm","wrap":True}
            ]
        },
        "footer":{
            "type":"box","layout":"vertical","spacing":"sm","contents":btns
        }
    }
    return FlexSendMessage(alt_text="背ネーム・番号を選択してください", contents=bubble)


# -----------------------
# LINEコールバック
# -----------------------
@app.route("/line/callback", methods=["POST"])
def line_callback():
    signature = request.headers.get("X-Line-Signature","")
    if not signature:
        abort(400)

    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        abort(400, f"Invalid signature: {e}")
    return "OK", 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # すでに見積りフロー中かどうか
    if user_id in user_estimate_sessions and user_estimate_sessions[user_id]["step"]>0:
        process_estimate_flow(event, text)
        return

    # 見積りフロー開始
    if text == "お見積り":
        start_estimate_flow(event)
        return

    # カタログ案内キーワード
    if ("カタログ" in text) or ("catalog" in text.lower()):
        reply_text = (
            "🎁 【クラTナビ最新カタログ無料プレゼント】 🎁 \n"
            "クラスTシャツの最新デザインやトレンド情報が詰まったカタログを、期間限定で無料でお届けします✨\n\n"
            "📚 1. 応募方法\n"
            "以下の どちらかのアカウントをフォロー してください👇\n"
            "📸 Instagram：https://www.instagram.com/graffitees_045/\n"
            "🎥 TikTok： https://www.tiktok.com/@graffitees_045\n\n"
            "👉 フォロー後、下記フォームからお申し込みください。\n"
            "⚠️ 注意： サブアカウントや重複申し込みはご遠慮ください。\n\n"
            "📦 2. カタログ発送時期\n"
            "📅 2025年4月中旬～郵送で発送予定です。\n\n"
            "🙌 3. 配布数について\n"
            "先着 300名様分 を予定しています。\n"
            "※応募が殺到した場合は、配布数の増加や抽選になる可能性があります。\n\n"
            "📝 4. お申し込みはこちら\n"
            "📩 カタログ申し込みフォーム：https://line-works-bot-1.onrender.com/catalog_form"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # WEBフォーム注文
    if text == "WEBフォーム注文":
        form_url = f"https://{request.host}/webform?user_id={user_id}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"WEBフォームから注文ですね！\nこちらへどうぞ:\n{form_url}")
        )
        return

    # その他
    return

def start_estimate_flow(event: MessageEvent):
    user_id = event.source.user_id
    user_estimate_sessions[user_id] = {"step":1, "answers":{}}
    line_bot_api.reply_message(event.reply_token, flex_usage_date())

def process_estimate_flow(event: MessageEvent, text: str):
    user_id = event.source.user_id
    session_data = user_estimate_sessions[user_id]
    step = session_data["step"]

    if step == 1:
        if text in ["14日前以上","14日前以内"]:
            session_data["answers"]["usage_date"] = text
            session_data["answers"]["discount_type"] = "早割" if text=="14日前以上" else "通常"
            session_data["step"] = 2
            line_bot_api.reply_message(event.reply_token, flex_budget())
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text="「14日前以上」または「14日前以内」を選択ください。"))

    elif step == 2:
        budgets = ["1,000円","2,000円","3,000円","4,000円","5,000円"]
        if text in budgets:
            session_data["answers"]["budget"] = text
            session_data["step"] = 3
            line_bot_api.reply_message(event.reply_token, flex_item_select())
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text="1枚あたりの予算を選択してください。"))

    elif step == 3:
        items = [
            "ドライTシャツ","ヘビーウェイトTシャツ","ドライポロシャツ","ドライメッシュビブス",
            "ドライベースボールシャツ","ドライロングスリープTシャツ","ドライハーフパンツ",
            "ヘビーウェイトロングスリープTシャツ","クルーネックライトトレーナー",
            "フーデッドライトパーカー","スタンダードトレーナー","スタンダードWフードパーカー",
            "ジップアップライトパーカー"
        ]
        if text in items:
            session_data["answers"]["item"] = text
            session_data["step"] = 4
            line_bot_api.reply_message(event.reply_token, flex_quantity())
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text="商品名をボタンから選択してください。"))

    elif step == 4:
        valid_qty = ["10","20","30","40","50","100"]
        if text in valid_qty:
            session_data["answers"]["quantity"] = text
            session_data["step"] = 5
            line_bot_api.reply_message(event.reply_token, flex_print_position())
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text="枚数をボタンから選択してください。"))

    elif step == 5:
        valid_pos = ["前のみ","背中のみ","前と背中"]
        if text in valid_pos:
            session_data["answers"]["print_position"] = text
            session_data["step"] = 6
            line_bot_api.reply_message(event.reply_token, flex_color_count())
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text="プリント位置を選択してください。"))

    elif step == 6:
        color_list = list(COLOR_COST_MAP.keys())
        if text in color_list:
            session_data["answers"]["color_count"] = text
            session_data["step"] = 7
            line_bot_api.reply_message(event.reply_token, flex_back_name())
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text="色数を選択してください。"))

    elif step == 7:
        valid_back = ["ネーム&背番号セット","ネーム(大)","番号(大)","背ネーム・番号を使わない"]
        if text in valid_back:
            session_data["answers"]["back_name"] = text
            session_data["step"] = 8

            # 見積計算
            edata = session_data["answers"]
            quantity = int(edata["quantity"])
            total_price, unit_price = calculate_estimate(edata)
            quote_number = write_estimate_to_spreadsheet(user_id, edata, total_price, unit_price)

            reply_msg = (
                f"お見積りが完了しました。\n\n"
                f"見積番号: {quote_number}\n"
                f"使用日: {edata['usage_date']}（{edata['discount_type']}）\n"
                f"予算: {edata['budget']}\n"
                f"商品: {edata['item']}\n"
                f"枚数: {quantity}枚\n"
                f"プリント位置: {edata['print_position']}\n"
                f"色数: {edata['color_count']}\n"
                f"背ネーム・番号: {edata['back_name']}\n\n"
                f"【合計金額】¥{total_price:,}\n"
                f"【1枚あたり】¥{unit_price:,}\n"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

            del user_estimate_sessions[user_id]
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text="背ネーム・番号の選択肢からお選びください。"))
    else:
        # エラー時
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text="エラーが発生しました。最初からやり直してください。"))
        if user_id in user_estimate_sessions:
            del user_estimate_sessions[user_id]

# -----------------------
# カタログ申し込みフォーム (GET/POST)
# -----------------------
@app.route("/catalog_form", methods=["GET"])
def show_catalog_form():
    # モバイル対応のために <meta name="viewport"> を追加
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>カタログ申し込みフォーム</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: sans-serif;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            padding: 1em;
        }
        label {
            display: block;
            margin-bottom: 0.5em;
        }
        input[type=text], input[type=email], textarea {
            width: 100%;
            padding: 0.5em;
            margin-top: 0.3em;
            box-sizing: border-box;
        }
        input[type=submit] {
            padding: 0.7em 1em;
            font-size: 1em;
            margin-top: 1em;
        }
    </style>
    <script>
    async function fetchAddress() {
        let pcRaw = document.getElementById('postal_code').value.trim();
        pcRaw = pcRaw.replace('-', '');
        if (pcRaw.length < 7) {
            return;
        }
        try {
            const response = await fetch('https://api.zipaddress.net/?zipcode='+pcRaw);
            const data = await response.json();
            if(data.code===200){
                document.getElementById('address').value=data.data.fullAddress;
            }
        }catch(e){
            console.log("住所検索失敗:", e);
        }
    }
    </script>
</head>
<body>
    <div class="container">
      <h1>カタログ申し込みフォーム</h1>
      <p>以下の項目をご記入の上、送信してください。</p>
      <form action="/submit_form" method="post">
          <label>氏名（必須）:
              <input type="text" name="name" required>
          </label>

          <label>郵便番号（必須）:<br>
              <small>※ハイフン無し7桁で入力すると自動で住所補完します</small><br>
              <input type="text" name="postal_code" id="postal_code" onkeyup="fetchAddress()" required>
          </label>

          <label>住所（必須）:
              <input type="text" name="address" id="address" required>
          </label>

          <label>電話番号（必須）:
              <input type="text" name="phone" required>
          </label>

          <label>メールアドレス（必須）:
              <input type="email" name="email" required>
          </label>

          <label>Insta・TikTok名（必須）:
              <input type="text" name="sns_account" required>
          </label>

          <label>2025年度に在籍予定の学校名と学年（未記入可）:
              <input type="text" name="school_grade">
          </label>

          <label>その他（質問やご要望など）:
              <textarea name="other" rows="4"></textarea>
          </label>

          <input type="submit" value="送信">
      </form>
    </div>
</body>
</html>
"""
    return render_template_string(html_content)

@app.route("/submit_form", methods=["POST"])
def submit_catalog_form():
    form_data = {
        "name": request.form.get("name","").strip(),
        "postal_code": request.form.get("postal_code","").strip(),
        "address": request.form.get("address","").strip(),
        "phone": request.form.get("phone","").strip(),
        "email": request.form.get("email","").strip(),
        "sns_account": request.form.get("sns_account","").strip(),
        "school_grade": request.form.get("school_grade","").strip(),
        "other": request.form.get("other","").strip(),
    }
    try:
        write_to_spreadsheet_for_catalog(form_data)
    except Exception as e:
        return f"エラーが発生しました: {e}", 500

    return "フォーム送信ありがとうございました！ カタログ送付をお待ちください。", 200

# -----------------------
# WEBフォームから注文 (GET/POST) (省略なし, S3対応)
# -----------------------
FORM_HTML = r"""
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
    p.instruction {
      font-size: 14px;
      color: #555;
    }
    .tshirt-container {
      width: 300px;
      margin-bottom: 16px;
      position: relative;
    }
    svg {
      width: 100%;
      height: auto;
      display: block;
    }
    .tshirt-shape {
      fill: #f5f5f5;
      stroke: #aaa;
      stroke-width: 2;
    }
    .click-area {
      fill: white;
      stroke: black;
      cursor: pointer;
      transition: 0.2s;
    }
    .click-area:hover {
      fill: orange;
    }
    .click-area.selected {
      fill: orange;
    }
    .area-label {
      pointer-events: none;
      font-size: 12px;
      text-anchor: middle;
      alignment-baseline: middle;
      user-select: none;
    }
  </style>
</head>
<body>
  <h1>WEBフォームから注文</h1>
  <form action="/webform_submit" method="POST" enctype="multipart/form-data">
    <input type="hidden" name="user_id" value="{{ user_id }}" />

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


    <!-- ▼▼ 前面プリント ▼▼ -->
    <h3>プリント位置: 前</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_front" value="おまかせ (最大:横28cm x 縦35cm以内)" checked>
        おまかせ (最大:横28cm x 縦35cm以内)
      </label>
      <label>
        <input type="radio" name="print_size_front" value="custom">
        ヨコcm x タテcmくらい(入力する):
      </label>
    </div>
    <input type="text" name="print_size_front_custom" placeholder="例: 20cm x 15cm">

    <!-- ▼▼ プリントカラー(前) を複数選択式に変更 ▼▼ -->
    <label>プリントカラー(前):</label>
    <select name="print_color_front[]" multiple style="height: 180px;">
      <optgroup label="●レギュラーインク">
        <option value="ホワイト">ホワイト</option>
        <option value="ライトグレー">ライトグレー</option>
        <option value="ダークグレー">ダークグレー</option>
        <option value="ブラック">ブラック</option>
        <option value="サックス">サックス</option>
        <option value="ブルー">ブルー</option>
        <option value="ネイビー">ネイビー</option>
        <option value="ライトピンク">ライトピンク</option>
        <option value="ローズピンク">ローズピンク</option>
        <option value="ホットピンク">ホットピンク</option>
        <option value="レッド">レッド</option>
        <option value="ワインレッド">ワインレッド</option>
        <option value="ミントグリーン">ミントグリーン</option>
        <option value="エメラルドグリーン">エメラルドグリーン</option>
        <option value="パステルイエロー">パステルイエロー</option>
        <option value="イエロー">イエロー</option>
        <option value="ゴールドイエロー">ゴールドイエロー</option>
        <option value="オレンジ">オレンジ</option>
        <option value="イエローグリーン">イエローグリーン</option>
        <option value="グリーン">グリーン</option>
        <option value="ダークグリーン">ダークグリーン</option>
        <option value="ライトパープル">ライトパープル</option>
        <option value="パープル">パープル</option>
        <option value="クリーム">クリーム</option>
        <option value="ライトブラウン">ライトブラウン</option>
        <option value="ダークブラウン">ダークブラウン</option>
        <option value="シルバー">シルバー</option>
        <option value="ゴールド">ゴールド</option>
      </optgroup>
      <optgroup label="●オプションインク">
        <option value="グリッターシルバー">グリッターシルバー</option>
        <option value="グリッターゴールド">グリッターゴールド</option>
        <option value="グリッターブラック">グリッターブラック</option>
        <option value="グリッターイエロー">グリッターイエロー</option>
        <option value="グリッターピンク">グリッターピンク</option>
        <option value="グリッターレッド">グリッターレッド</option>
        <option value="グリッターグリーン">グリッターグリーン</option>
        <option value="グリッターブルー">グリッターブルー</option>
        <option value="グリッターパープル">グリッターパープル</option>
        <option value="蛍光オレンジ">蛍光オレンジ</option>
        <option value="蛍光ピンク">蛍光ピンク</option>
        <option value="蛍光グリーン">蛍光グリーン</option>
      </optgroup>
    </select>

    <!-- ▼▼ フォントNo.(前) ▼▼ -->
    <label>フォントNo.(前):</label>
    <select name="font_no_front">
      <option value="">選択してください</option>
      <option value="E-01">E-01</option>
      <option value="E-02">E-02</option>
      <option value="E-03">E-03</option>
      <option value="E-05">E-05</option>
      <option value="E-06">E-06</option>
      <option value="E-09">E-09</option>
      <option value="E-10">E-10</option>
      <option value="E-13">E-13</option>
      <option value="E-14">E-14</option>
      <option value="E-15">E-15</option>
      <option value="E-16">E-16</option>
      <option value="E-17">E-17</option>
      <option value="E-18">E-18</option>
      <option value="E-19">E-19</option>
      <option value="E-20">E-20</option>
      <option value="E-21">E-21</option>
      <option value="E-22">E-22</option>
      <option value="E-23">E-23</option>
      <option value="E-24">E-24</option>
      <option value="E-25">E-25</option>
      <option value="E-26">E-26</option>
      <option value="E-27">E-27</option>
      <option value="E-28">E-28</option>
      <option value="E-29">E-29</option>
      <option value="E-30">E-30</option>
      <option value="E-31">E-31</option>
      <option value="E-32">E-32</option>
      <option value="E-33">E-33</option>
      <option value="E-34">E-34</option>
      <option value="E-35">E-35</option>
      <option value="E-37">E-37</option>
      <option value="E-38">E-38</option>
      <option value="E-40">E-40</option>
      <option value="E-41">E-41</option>
      <option value="E-42">E-42</option>
      <option value="E-43">E-43</option>
      <option value="E-44">E-44</option>
      <option value="E-45">E-45</option>
      <option value="E-46">E-46</option>
      <option value="E-47">E-47</option>
      <option value="E-50">E-50</option>
      <option value="E-51">E-51</option>
      <option value="E-52">E-52</option>
      <option value="E-53">E-53</option>
      <option value="E-54">E-54</option>
      <option value="E-55">E-55</option>
      <option value="E-56">E-56</option>
      <option value="E-57">E-57</option>
    </select>

    <!-- ▼▼ プリントサンプル(前) ▼▼ -->
    <label>プリントサンプル(前):</label>
    <select name="design_sample_front">
      <option value="">選択してください</option>
      <option value="D-008">D-008</option>
      <option value="D-009">D-009</option>
      <option value="D-012">D-012</option>
      <option value="D-013">D-013</option>
      <option value="D-014">D-014</option>
      <option value="D-015">D-015</option>
      <option value="D-027">D-027</option>
      <option value="D-028">D-028</option>
      <option value="D-029">D-029</option>
      <option value="D-030">D-030</option>
      <option value="D-039">D-039</option>
      <option value="D-040">D-040</option>
      <option value="D-041">D-041</option>
      <option value="D-042">D-042</option>
      <option value="D-051">D-051</option>
      <option value="D-068">D-068</option>
      <option value="D-080">D-080</option>
      <option value="D-106">D-106</option>
      <option value="D-111">D-111</option>
      <option value="D-125">D-125</option>
      <option value="D-128">D-128</option>
      <option value="D-129">D-129</option>
      <option value="D-138">D-138</option>
      <option value="D-140">D-140</option>
      <option value="D-150">D-150</option>
      <option value="D-157">D-157</option>
      <option value="D-167">D-167</option>
      <option value="D-168">D-168</option>
      <option value="D-177">D-177</option>
      <option value="D-195">D-195</option>
      <option value="D-201">D-201</option>
      <option value="D-212">D-212</option>
      <option value="D-213">D-213</option>
      <option value="D-218">D-218</option>
      <option value="D-220">D-220</option>
      <option value="D-222">D-222</option>
      <option value="D-223">D-223</option>
      <option value="D-229">D-229</option>
      <option value="D-230">D-230</option>
      <option value="D-231">D-231</option>
      <option value="D-233">D-233</option>
      <option value="D-234">D-234</option>
      <option value="D-235">D-235</option>
      <option value="D-236">D-236</option>
      <option value="D-238">D-238</option>
      <option value="D-240">D-240</option>
      <option value="D-241">D-241</option>
      <option value="D-242">D-242</option>
      <option value="D-244">D-244</option>
      <option value="D-246">D-246</option>
      <option value="D-247">D-247</option>
      <option value="D-248">D-248</option>
      <option value="D-260">D-260</option>
      <option value="D-266">D-266</option>
      <option value="D-273">D-273</option>
      <option value="D-274">D-274</option>
      <option value="D-275">D-275</option>
      <option value="D-280">D-280</option>
      <option value="D-281">D-281</option>
      <option value="D-286">D-286</option>
      <option value="D-287">D-287</option>
      <option value="D-288">D-288</option>
      <option value="D-291">D-291</option>
      <option value="D-292">D-292</option>
      <option value="D-298">D-298</option>
      <option value="D-299">D-299</option>
      <option value="D-300">D-300</option>
      <option value="D-301">D-301</option>
      <option value="D-307">D-307</option>
      <option value="D-309">D-309</option>
      <option value="D-315">D-315</option>
      <option value="D-317">D-317</option>
      <option value="D-318">D-318</option>
      <option value="D-322">D-322</option>
      <option value="D-332">D-332</option>
      <option value="D-334">D-334</option>
      <option value="D-335">D-335</option>
      <option value="D-337">D-337</option>
      <option value="D-340">D-340</option>
      <option value="D-341">D-341</option>
      <option value="D-344">D-344</option>
      <option value="D-346">D-346</option>
      <option value="D-347">D-347</option>
      <option value="D-348">D-348</option>
      <option value="D-349">D-349</option>
      <option value="D-352">D-352</option>
      <option value="D-353">D-353</option>
      <option value="D-354">D-354</option>
      <option value="D-355">D-355</option>
      <option value="D-358">D-358</option>
      <option value="D-363">D-363</option>
      <option value="D-364">D-364</option>
      <option value="D-365">D-365</option>
      <option value="D-366">D-366</option>
      <option value="D-367">D-367</option>
      <option value="D-368">D-368</option>
      <option value="D-370">D-370</option>
      <option value="D-372">D-372</option>
      <option value="D-373">D-373</option>
      <option value="D-374">D-374</option>
      <option value="D-375">D-375</option>
      <option value="D-376">D-376</option>
      <option value="D-377">D-377</option>
      <option value="D-378">D-378</option>
      <option value="D-379">D-379</option>
      <option value="D-380">D-380</option>
      <option value="D-381">D-381</option>
      <option value="D-382">D-382</option>
      <option value="D-383">D-383</option>
      <option value="D-384">D-384</option>
      <option value="D-385">D-385</option>
      <option value="D-386">D-386</option>
      <option value="D-388">D-388</option>
      <option value="D-390">D-390</option>
      <option value="D-391">D-391</option>
      <option value="D-392">D-392</option>
      <option value="D-393">D-393</option>
      <option value="D-394">D-394</option>
      <option value="D-396">D-396</option>
      <option value="D-397">D-397</option>
      <option value="D-398">D-398</option>
      <option value="D-399">D-399</option>
      <option value="D-400">D-400</option>
      <option value="D-401">D-401</option>
      <option value="D-402">D-402</option>
      <option value="D-403">D-403</option>
      <option value="D-404">D-404</option>
      <option value="D-405">D-405</option>
    </select>

    <label>プリント位置データ(前) (画像アップロード):</label>
    <input type="file" name="position_data_front">

    <input type="text" name="front_positions_selected" id="front_positions_selected"
           placeholder="前面 1~9" readonly>

    <div class="tshirt-container">
      <svg viewBox="0 0 300 300">
        <path class="tshirt-shape" d="
          M 90,20
          L 210,20
          Q 220,30 210,40
          L 210,65
          L 270,65
          L 270,100
          L 210,100
          L 210,240
          L 90,240
          L 90,100
          L 30,100
          L 30,65
          L 90,65
          L 90,40
          Q 80,30 90,20
          Z
        "></path>
        <circle cx="60" cy="50" r="10" class="click-area" data-num="1"></circle>
        <text x="60" y="50" class="area-label">1</text>
        <circle cx="240" cy="50" r="10" class="click-area" data-num="2"></circle>
        <text x="240" y="50" class="area-label">2</text>
        <circle cx="120" cy="80" r="10" class="click-area" data-num="3"></circle>
        <text x="120" y="80" class="area-label">3</text>
        <circle cx="150" cy="80" r="10" class="click-area" data-num="4"></circle>
        <text x="150" y="80" class="area-label">4</text>
        <circle cx="180" cy="80" r="10" class="click-area" data-num="5"></circle>
        <text x="180" y="80" class="area-label">5</text>
        <circle cx="150" cy="120" r="10" class="click-area" data-num="6"></circle>
        <text x="150" y="120" class="area-label">6</text>
        <circle cx="100" cy="200" r="10" class="click-area" data-num="7"></circle>
        <text x="100" y="200" class="area-label">7</text>
        <circle cx="150" cy="200" r="10" class="click-area" data-num="8"></circle>
        <text x="150" y="200" class="area-label">8</text>
        <circle cx="200" cy="200" r="10" class="click-area" data-num="9"></circle>
        <text x="200" y="200" class="area-label">9</text>
      </svg>
    </div>

    <!-- ▼▼ 背面プリント ▼▼ -->
    <h3>プリント位置: 後</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_back" value="おまかせ (最大:横28cm x 縦35cm以内)" checked>
        おまかせ (最大:横28cm x 縦35cm以内)
      </label>
      <label>
        <input type="radio" name="print_size_back" value="custom">
        ヨコcm x タテcmくらい(入力する):
      </label>
    </div>
    <input type="text" name="print_size_back_custom" placeholder="例: 20cm x 15cm">

    <!-- ▼▼ プリントカラー(後) を複数選択式に変更 ▼▼ -->
    <label>プリントカラー(後):</label>
    <select name="print_color_back[]" multiple style="height: 180px;">
      <optgroup label="●レギュラーインク">
        <option value="ホワイト">ホワイト</option>
        <option value="ライトグレー">ライトグレー</option>
        <option value="ダークグレー">ダークグレー</option>
        <option value="ブラック">ブラック</option>
        <option value="サックス">サックス</option>
        <option value="ブルー">ブルー</option>
        <option value="ネイビー">ネイビー</option>
        <option value="ライトピンク">ライトピンク</option>
        <option value="ローズピンク">ローズピンク</option>
        <option value="ホットピンク">ホットピンク</option>
        <option value="レッド">レッド</option>
        <option value="ワインレッド">ワインレッド</option>
        <option value="ミントグリーン">ミントグリーン</option>
        <option value="エメラルドグリーン">エメラルドグリーン</option>
        <option value="パステルイエロー">パステルイエロー</option>
        <option value="イエロー">イエロー</option>
        <option value="ゴールドイエロー">ゴールドイエロー</option>
        <option value="オレンジ">オレンジ</option>
        <option value="イエローグリーン">イエローグリーン</option>
        <option value="グリーン">グリーン</option>
        <option value="ダークグリーン">ダークグリーン</option>
        <option value="ライトパープル">ライトパープル</option>
        <option value="パープル">パープル</option>
        <option value="クリーム">クリーム</option>
        <option value="ライトブラウン">ライトブラウン</option>
        <option value="ダークブラウン">ダークブラウン</option>
        <option value="シルバー">シルバー</option>
        <option value="ゴールド">ゴールド</option>
      </optgroup>
      <optgroup label="●オプションインク">
        <option value="グリッターシルバー">グリッターシルバー</option>
        <option value="グリッターゴールド">グリッターゴールド</option>
        <option value="グリッターブラック">グリッターブラック</option>
        <option value="グリッターイエロー">グリッターイエロー</option>
        <option value="グリッターピンク">グリッターピンク</option>
        <option value="グリッターレッド">グリッターレッド</option>
        <option value="グリッターグリーン">グリッターグリーン</option>
        <option value="グリッターブルー">グリッターブルー</option>
        <option value="グリッターパープル">グリッターパープル</option>
        <option value="蛍光オレンジ">蛍光オレンジ</option>
        <option value="蛍光ピンク">蛍光ピンク</option>
        <option value="蛍光グリーン">蛍光グリーン</option>
      </optgroup>
    </select>

    <!-- ▼▼ フォントNo.(後) ▼▼ -->
    <label>フォントNo.(後):</label>
    <select name="font_no_back">
      <option value="">選択してください</option>
      <option value="E-01">E-01</option>
      <option value="E-02">E-02</option>
      <option value="E-03">E-03</option>
      <option value="E-05">E-05</option>
      <option value="E-06">E-06</option>
      <option value="E-09">E-09</option>
      <option value="E-10">E-10</option>
      <option value="E-13">E-13</option>
      <option value="E-14">E-14</option>
      <option value="E-15">E-15</option>
      <option value="E-16">E-16</option>
      <option value="E-17">E-17</option>
      <option value="E-18">E-18</option>
      <option value="E-19">E-19</option>
      <option value="E-20">E-20</option>
      <option value="E-21">E-21</option>
      <option value="E-22">E-22</option>
      <option value="E-23">E-23</option>
      <option value="E-24">E-24</option>
      <option value="E-25">E-25</option>
      <option value="E-26">E-26</option>
      <option value="E-27">E-27</option>
      <option value="E-28">E-28</option>
      <option value="E-29">E-29</option>
      <option value="E-30">E-30</option>
      <option value="E-31">E-31</option>
      <option value="E-32">E-32</option>
      <option value="E-33">E-33</option>
      <option value="E-34">E-34</option>
      <option value="E-35">E-35</option>
      <option value="E-37">E-37</option>
      <option value="E-38">E-38</option>
      <option value="E-40">E-40</option>
      <option value="E-41">E-41</option>
      <option value="E-42">E-42</option>
      <option value="E-43">E-43</option>
      <option value="E-44">E-44</option>
      <option value="E-45">E-45</option>
      <option value="E-46">E-46</option>
      <option value="E-47">E-47</option>
      <option value="E-50">E-50</option>
      <option value="E-51">E-51</option>
      <option value="E-52">E-52</option>
      <option value="E-53">E-53</option>
      <option value="E-54">E-54</option>
      <option value="E-55">E-55</option>
      <option value="E-56">E-56</option>
      <option value="E-57">E-57</option>
    </select>

    <!-- ▼▼ プリントサンプル(後) ▼▼ -->
    <label>プリントサンプル(後):</label>
    <select name="design_sample_back">
      <option value="">選択してください</option>
      <option value="D-008">D-008</option>
      <option value="D-009">D-009</option>
      <option value="D-012">D-012</option>
      <option value="D-013">D-013</option>
      <option value="D-014">D-014</option>
      <option value="D-015">D-015</option>
      <option value="D-027">D-027</option>
      <option value="D-028">D-028</option>
      <option value="D-029">D-029</option>
      <option value="D-030">D-030</option>
      <option value="D-039">D-039</option>
      <option value="D-040">D-040</option>
      <option value="D-041">D-041</option>
      <option value="D-042">D-042</option>
      <option value="D-051">D-051</option>
      <option value="D-068">D-068</option>
      <option value="D-080">D-080</option>
      <option value="D-106">D-106</option>
      <option value="D-111">D-111</option>
      <option value="D-125">D-125</option>
      <option value="D-128">D-128</option>
      <option value="D-129">D-129</option>
      <option value="D-138">D-138</option>
      <option value="D-140">D-140</option>
      <option value="D-150">D-150</option>
      <option value="D-157">D-157</option>
      <option value="D-167">D-167</option>
      <option value="D-168">D-168</option>
      <option value="D-177">D-177</option>
      <option value="D-195">D-195</option>
      <option value="D-201">D-201</option>
      <option value="D-212">D-212</option>
      <option value="D-213">D-213</option>
      <option value="D-218">D-218</option>
      <option value="D-220">D-220</option>
      <option value="D-222">D-222</option>
      <option value="D-223">D-223</option>
      <option value="D-229">D-229</option>
      <option value="D-230">D-230</option>
      <option value="D-231">D-231</option>
      <option value="D-233">D-233</option>
      <option value="D-234">D-234</option>
      <option value="D-235">D-235</option>
      <option value="D-236">D-236</option>
      <option value="D-238">D-238</option>
      <option value="D-240">D-240</option>
      <option value="D-241">D-241</option>
      <option value="D-242">D-242</option>
      <option value="D-244">D-244</option>
      <option value="D-246">D-246</option>
      <option value="D-247">D-247</option>
      <option value="D-248">D-248</option>
      <option value="D-260">D-260</option>
      <option value="D-266">D-266</option>
      <option value="D-273">D-273</option>
      <option value="D-274">D-274</option>
      <option value="D-275">D-275</option>
      <option value="D-280">D-280</option>
      <option value="D-281">D-281</option>
      <option value="D-286">D-286</option>
      <option value="D-287">D-287</option>
      <option value="D-288">D-288</option>
      <option value="D-291">D-291</option>
      <option value="D-292">D-292</option>
      <option value="D-298">D-298</option>
      <option value="D-299">D-299</option>
      <option value="D-300">D-300</option>
      <option value="D-301">D-301</option>
      <option value="D-307">D-307</option>
      <option value="D-309">D-309</option>
      <option value="D-315">D-315</option>
      <option value="D-317">D-317</option>
      <option value="D-318">D-318</option>
      <option value="D-322">D-322</option>
      <option value="D-332">D-332</option>
      <option value="D-334">D-334</option>
      <option value="D-335">D-335</option>
      <option value="D-337">D-337</option>
      <option value="D-340">D-340</option>
      <option value="D-341">D-341</option>
      <option value="D-344">D-344</option>
      <option value="D-346">D-346</option>
      <option value="D-347">D-347</option>
      <option value="D-348">D-348</option>
      <option value="D-349">D-349</option>
      <option value="D-352">D-352</option>
      <option value="D-353">D-353</option>
      <option value="D-354">D-354</option>
      <option value="D-355">D-355</option>
      <option value="D-358">D-358</option>
      <option value="D-363">D-363</option>
      <option value="D-364">D-364</option>
      <option value="D-365">D-365</option>
      <option value="D-366">D-366</option>
      <option value="D-367">D-367</option>
      <option value="D-368">D-368</option>
      <option value="D-370">D-370</option>
      <option value="D-372">D-372</option>
      <option value="D-373">D-373</option>
      <option value="D-374">D-374</option>
      <option value="D-375">D-375</option>
      <option value="D-376">D-376</option>
      <option value="D-377">D-377</option>
      <option value="D-378">D-378</option>
      <option value="D-379">D-379</option>
      <option value="D-380">D-380</option>
      <option value="D-381">D-381</option>
      <option value="D-382">D-382</option>
      <option value="D-383">D-383</option>
      <option value="D-384">D-384</option>
      <option value="D-385">D-385</option>
      <option value="D-386">D-386</option>
      <option value="D-388">D-388</option>
      <option value="D-390">D-390</option>
      <option value="D-391">D-391</option>
      <option value="D-392">D-392</option>
      <option value="D-393">D-393</option>
      <option value="D-394">D-394</option>
      <option value="D-396">D-396</option>
      <option value="D-397">D-397</option>
      <option value="D-398">D-398</option>
      <option value="D-399">D-399</option>
      <option value="D-400">D-400</option>
      <option value="D-401">D-401</option>
      <option value="D-402">D-402</option>
      <option value="D-403">D-403</option>
      <option value="D-404">D-404</option>
      <option value="D-405">D-405</option>
    </select>

    <label>プリント位置データ(後) (画像アップロード):</label>
    <input type="file" name="position_data_back">
    <input type="text" name="back_positions_selected" id="back_positions_selected"
           placeholder="背面 10~14" readonly>

    <div class="tshirt-container">
      <svg viewBox="0 0 300 300">
        <path class="tshirt-shape" d="
          M 90,20
          L 210,20
          Q 220,30 210,40
          L 210,65
          L 270,65
          L 270,100
          L 210,100
          L 210,240
          L 90,240
          L 90,100
          L 30,100
          L 30,65
          L 90,65
          L 90,40
          Q 80,30 90,20
          Z
        "></path>

        <circle cx="150" cy="50" r="10" class="click-area" data-num="10"></circle>
        <text x="150" y="50" class="area-label">10</text>
        <circle cx="150" cy="100" r="10" class="click-area" data-num="11"></circle>
        <text x="150" y="100" class="area-label">11</text>
        <circle cx="100" cy="200" r="10" class="click-area" data-num="12"></circle>
        <text x="100" y="200" class="area-label">12</text>
        <circle cx="150" cy="200" r="10" class="click-area" data-num="13"></circle>
        <text x="150" y="200" class="area-label">13</text>
        <circle cx="200" cy="200" r="10" class="click-area" data-num="14"></circle>
        <text x="200" y="200" class="area-label">14</text>
      </svg>
    </div>

    <!-- ▼▼ その他プリント ▼▼ -->
    <h3>プリント位置: その他</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_other" value="おまかせ (最大:横28cm x 縦35cm以内)" checked>
        おまかせ (最大:横28cm x 縦35cm以内)
      </label>
      <label>
        <input type="radio" name="print_size_other" value="custom">
        ヨコcm x タテcmくらい(入力する):
      </label>
    </div>
    <input type="text" name="print_size_other_custom" placeholder="例: 20cm x 15cm">

    <!-- ▼▼ プリントカラー(その他) を複数選択式に変更 ▼▼ -->
    <label>プリントカラー(その他):</label>
    <select name="print_color_other[]" multiple style="height: 180px;">
      <optgroup label="●レギュラーインク">
        <option value="ホワイト">ホワイト</option>
        <option value="ライトグレー">ライトグレー</option>
        <option value="ダークグレー">ダークグレー</option>
        <option value="ブラック">ブラック</option>
        <option value="サックス">サックス</option>
        <option value="ブルー">ブルー</option>
        <option value="ネイビー">ネイビー</option>
        <option value="ライトピンク">ライトピンク</option>
        <option value="ローズピンク">ローズピンク</option>
        <option value="ホットピンク">ホットピンク</option>
        <option value="レッド">レッド</option>
        <option value="ワインレッド">ワインレッド</option>
        <option value="ミントグリーン">ミントグリーン</option>
        <option value="エメラルドグリーン">エメラルドグリーン</option>
        <option value="パステルイエロー">パステルイエロー</option>
        <option value="イエロー">イエロー</option>
        <option value="ゴールドイエロー">ゴールドイエロー</option>
        <option value="オレンジ">オレンジ</option>
        <option value="イエローグリーン">イエローグリーン</option>
        <option value="グリーン">グリーン</option>
        <option value="ダークグリーン">ダークグリーン</option>
        <option value="ライトパープル">ライトパープル</option>
        <option value="パープル">パープル</option>
        <option value="クリーム">クリーム</option>
        <option value="ライトブラウン">ライトブラウン</option>
        <option value="ダークブラウン">ダークブラウン</option>
        <option value="シルバー">シルバー</option>
        <option value="ゴールド">ゴールド</option>
      </optgroup>
      <optgroup label="●オプションインク">
        <option value="グリッターシルバー">グリッターシルバー</option>
        <option value="グリッターゴールド">グリッターゴールド</option>
        <option value="グリッターブラック">グリッターブラック</option>
        <option value="グリッターイエロー">グリッターイエロー</option>
        <option value="グリッターピンク">グリッターピンク</option>
        <option value="グリッターレッド">グリッターレッド</option>
        <option value="グリッターグリーン">グリッターグリーン</option>
        <option value="グリッターブルー">グリッターブルー</option>
        <option value="グリッターパープル">グリッターパープル</option>
        <option value="蛍光オレンジ">蛍光オレンジ</option>
        <option value="蛍光ピンク">蛍光ピンク</option>
        <option value="蛍光グリーン">蛍光グリーン</option>
      </optgroup>
    </select>

    <!-- ▼▼ フォントNo.(その他) ▼▼ -->
    <label>フォントNo.(その他):</label>
    <select name="font_no_other">
      <option value="">選択してください</option>
      <option value="E-01">E-01</option>
      <option value="E-02">E-02</option>
      <option value="E-03">E-03</option>
      <option value="E-05">E-05</option>
      <option value="E-06">E-06</option>
      <option value="E-09">E-09</option>
      <option value="E-10">E-10</option>
      <option value="E-13">E-13</option>
      <option value="E-14">E-14</option>
      <option value="E-15">E-15</option>
      <option value="E-16">E-16</option>
      <option value="E-17">E-17</option>
      <option value="E-18">E-18</option>
      <option value="E-19">E-19</option>
      <option value="E-20">E-20</option>
      <option value="E-21">E-21</option>
      <option value="E-22">E-22</option>
      <option value="E-23">E-23</option>
      <option value="E-24">E-24</option>
      <option value="E-25">E-25</option>
      <option value="E-26">E-26</option>
      <option value="E-27">E-27</option>
      <option value="E-28">E-28</option>
      <option value="E-29">E-29</option>
      <option value="E-30">E-30</option>
      <option value="E-31">E-31</option>
      <option value="E-32">E-32</option>
      <option value="E-33">E-33</option>
      <option value="E-34">E-34</option>
      <option value="E-35">E-35</option>
      <option value="E-37">E-37</option>
      <option value="E-38">E-38</option>
      <option value="E-40">E-40</option>
      <option value="E-41">E-41</option>
      <option value="E-42">E-42</option>
      <option value="E-43">E-43</option>
      <option value="E-44">E-44</option>
      <option value="E-45">E-45</option>
      <option value="E-46">E-46</option>
      <option value="E-47">E-47</option>
      <option value="E-50">E-50</option>
      <option value="E-51">E-51</option>
      <option value="E-52">E-52</option>
      <option value="E-53">E-53</option>
      <option value="E-54">E-54</option>
      <option value="E-55">E-55</option>
      <option value="E-56">E-56</option>
      <option value="E-57">E-57</option>
    </select>

    <!-- ▼▼ プリントサンプル(その他) ▼▼ -->
    <label>プリントサンプル(その他):</label>
    <select name="design_sample_other">
      <option value="">選択してください</option>
      <option value="D-008">D-008</option>
      <option value="D-009">D-009</option>
      <option value="D-012">D-012</option>
      <option value="D-013">D-013</option>
      <option value="D-014">D-014</option>
      <option value="D-015">D-015</option>
      <option value="D-027">D-027</option>
      <option value="D-028">D-028</option>
      <option value="D-029">D-029</option>
      <option value="D-030">D-030</option>
      <option value="D-039">D-039</option>
      <option value="D-040">D-040</option>
      <option value="D-041">D-041</option>
      <option value="D-042">D-042</option>
      <option value="D-051">D-051</option>
      <option value="D-068">D-068</option>
      <option value="D-080">D-080</option>
      <option value="D-106">D-106</option>
      <option value="D-111">D-111</option>
      <option value="D-125">D-125</option>
      <option value="D-128">D-128</option>
      <option value="D-129">D-129</option>
      <option value="D-138">D-138</option>
      <option value="D-140">D-140</option>
      <option value="D-150">D-150</option>
      <option value="D-157">D-157</option>
      <option value="D-167">D-167</option>
      <option value="D-168">D-168</option>
      <option value="D-177">D-177</option>
      <option value="D-195">D-195</option>
      <option value="D-201">D-201</option>
      <option value="D-212">D-212</option>
      <option value="D-213">D-213</option>
      <option value="D-218">D-218</option>
      <option value="D-220">D-220</option>
      <option value="D-222">D-222</option>
      <option value="D-223">D-223</option>
      <option value="D-229">D-229</option>
      <option value="D-230">D-230</option>
      <option value="D-231">D-231</option>
      <option value="D-233">D-233</option>
      <option value="D-234">D-234</option>
      <option value="D-235">D-235</option>
      <option value="D-236">D-236</option>
      <option value="D-238">D-238</option>
      <option value="D-240">D-240</option>
      <option value="D-241">D-241</option>
      <option value="D-242">D-242</option>
      <option value="D-244">D-244</option>
      <option value="D-246">D-246</option>
      <option value="D-247">D-247</option>
      <option value="D-248">D-248</option>
      <option value="D-260">D-260</option>
      <option value="D-266">D-266</option>
      <option value="D-273">D-273</option>
      <option value="D-274">D-274</option>
      <option value="D-275">D-275</option>
      <option value="D-280">D-280</option>
      <option value="D-281">D-281</option>
      <option value="D-286">D-286</option>
      <option value="D-287">D-287</option>
      <option value="D-288">D-288</option>
      <option value="D-291">D-291</option>
      <option value="D-292">D-292</option>
      <option value="D-298">D-298</option>
      <option value="D-299">D-299</option>
      <option value="D-300">D-300</option>
      <option value="D-301">D-301</option>
      <option value="D-307">D-307</option>
      <option value="D-309">D-309</option>
      <option value="D-315">D-315</option>
      <option value="D-317">D-317</option>
      <option value="D-318">D-318</option>
      <option value="D-322">D-322</option>
      <option value="D-332">D-332</option>
      <option value="D-334">D-334</option>
      <option value="D-335">D-335</option>
      <option value="D-337">D-337</option>
      <option value="D-340">D-340</option>
      <option value="D-341">D-341</option>
      <option value="D-344">D-344</option>
      <option value="D-346">D-346</option>
      <option value="D-347">D-347</option>
      <option value="D-348">D-348</option>
      <option value="D-349">D-349</option>
      <option value="D-352">D-352</option>
      <option value="D-353">D-353</option>
      <option value="D-354">D-354</option>
      <option value="D-355">D-355</option>
      <option value="D-358">D-358</option>
      <option value="D-363">D-363</option>
      <option value="D-364">D-364</option>
      <option value="D-365">D-365</option>
      <option value="D-366">D-366</option>
      <option value="D-367">D-367</option>
      <option value="D-368">D-368</option>
      <option value="D-370">D-370</option>
      <option value="D-372">D-372</option>
      <option value="D-373">D-373</option>
      <option value="D-374">D-374</option>
      <option value="D-375">D-375</option>
      <option value="D-376">D-376</option>
      <option value="D-377">D-377</option>
      <option value="D-378">D-378</option>
      <option value="D-379">D-379</option>
      <option value="D-380">D-380</option>
      <option value="D-381">D-381</option>
      <option value="D-382">D-382</option>
      <option value="D-383">D-383</option>
      <option value="D-384">D-384</option>
      <option value="D-385">D-385</option>
      <option value="D-386">D-386</option>
      <option value="D-388">D-388</option>
      <option value="D-390">D-390</option>
      <option value="D-391">D-391</option>
      <option value="D-392">D-392</option>
      <option value="D-393">D-393</option>
      <option value="D-394">D-394</option>
      <option value="D-396">D-396</option>
      <option value="D-397">D-397</option>
      <option value="D-398">D-398</option>
      <option value="D-399">D-399</option>
      <option value="D-400">D-400</option>
      <option value="D-401">D-401</option>
      <option value="D-402">D-402</option>
      <option value="D-403">D-403</option>
      <option value="D-404">D-404</option>
      <option value="D-405">D-405</option>
    </select>

    <label>プリント位置データ(その他):</label>
    <input type="file" name="position_data_other">

    <h3>背ネーム・背番号プリント</h3>
    <p class="instruction">※複数選択可能</p>
    <div class="checkbox-group">
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム&背番号セット"> ネーム&背番号セット</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム(大)"> ネーム(大)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム(小)"> ネーム(小)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="番号(大)"> 番号(大)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="番号(小)"> 番号(小)</label>
    </div>

    <h3>追加のデザインイメージデータ</h3>
    <p class="instruction">プリント位置(前, 左胸, 右胸, 背中, 左袖, 右袖)を選択し、アップロードできます。</p>
    <label>プリント位置:</label>
    <select name="additional_design_position">
      <option value="">選択してください</option>
      <option value="前">前</option>
      <option value="左胸">左胸</option>
      <option value="右胸">右胸</option>
      <option value="背中">背中</option>
      <option value="左袖">左袖</option>
      <option value="右袖">右袖</option>
    </select>
    <label>デザインイメージデータ:</label>
    <input type="file" name="additional_design_image">

    <button type="submit">送信</button>

    <script>
      // 前面(①〜⑨)
      const frontSvg = document.querySelectorAll('.tshirt-container')[0];
      const frontAreas = frontSvg.querySelectorAll('.click-area');
      const frontInput = document.getElementById('front_positions_selected');
      frontAreas.forEach(area => {
        area.addEventListener('click', () => {
          frontAreas.forEach(a => a.classList.remove('selected'));
          area.classList.add('selected');
          const num = area.getAttribute('data-num');
          frontInput.value = num;
        });
      });

      // 背面(⑩〜⑭)
      const backSvg = document.querySelectorAll('.tshirt-container')[1];
      const backAreas = backSvg.querySelectorAll('.click-area');
      const backInput = document.getElementById('back_positions_selected');
      backAreas.forEach(area => {
        area.addEventListener('click', () => {
          backAreas.forEach(a => a.classList.remove('selected'));
          area.classList.add('selected');
          const num = area.getAttribute('data-num');
          backInput.value = num;
        });
      });
    </script>

  </form>
</body>
</html>
"""

@app.route("/webform", methods=["GET"])
def show_webform():
    user_id = request.args.get("user_id","")
    return render_template_string(FORM_HTML, user_id=user_id)

@app.route("/webform_submit", methods=["POST"])
def webform_submit():
    # (1) フォーム内容取得
    user_id = request.form.get("user_id","")

    application_date = request.form.get("application_date","")
    delivery_date = request.form.get("delivery_date","")
    use_date = request.form.get("use_date","")
    discount_option = request.form.get("discount_option","")
    school_name = request.form.get("school_name","")
    line_account= request.form.get("line_account","")
    group_name = request.form.get("group_name","")
    school_address= request.form.get("school_address","")
    school_tel = request.form.get("school_tel","")
    teacher_name= request.form.get("teacher_name","")
    teacher_tel = request.form.get("teacher_tel","")
    teacher_email= request.form.get("teacher_email","")
    representative= request.form.get("representative","")
    rep_tel = request.form.get("rep_tel","")
    rep_email = request.form.get("rep_email","")
    design_confirm= request.form.get("design_confirm","")
    payment_method= request.form.get("payment_method","")
    product_name = request.form.get("product_name","")
    product_color= request.form.get("product_color","")

    size_ss = request.form.get("size_ss","0")
    size_s  = request.form.get("size_s","0")
    size_m  = request.form.get("size_m","0")
    size_l  = request.form.get("size_l","0")
    size_ll = request.form.get("size_ll","0")
    size_lll= request.form.get("size_lll","0")

    print_size_front= request.form.get("print_size_front","")
    print_size_front_custom= request.form.get("print_size_front_custom","")
    print_color_front= request.form.get("print_color_front","")
    font_no_front= request.form.get("font_no_front","")
    design_sample_front= request.form.get("design_sample_front","")
    position_data_front= request.files.get("position_data_front")
    front_positions_selected= request.form.get("front_positions_selected","")

    print_size_back= request.form.get("print_size_back","")
    print_size_back_custom= request.form.get("print_size_back_custom","")
    print_color_back= request.form.get("print_color_back","")
    font_no_back= request.form.get("font_no_back","")
    design_sample_back= request.form.get("design_sample_back","")
    position_data_back= request.files.get("position_data_back")
    back_positions_selected= request.form.get("back_positions_selected","")

    print_size_other= request.form.get("print_size_other","")
    print_size_other_custom= request.form.get("print_size_other_custom","")
    print_color_other= request.form.get("print_color_other","")
    font_no_other= request.form.get("font_no_other","")
    design_sample_other= request.form.get("design_sample_other","")
    position_data_other= request.files.get("position_data_other")

    back_name_number_opts = request.form.getlist("back_name_number_print[]")
    back_name_number_str = ",".join(back_name_number_opts) if back_name_number_opts else ""

    additional_design_position= request.form.get("additional_design_position","")
    additional_design_image= request.files.get("additional_design_image")

    # (2) S3アップロード
    pos_front_url = upload_file_to_s3(position_data_front, S3_BUCKET_NAME, prefix="uploads/")
    pos_back_url  = upload_file_to_s3(position_data_back,  S3_BUCKET_NAME, prefix="uploads/")
    pos_other_url = upload_file_to_s3(position_data_other, S3_BUCKET_NAME, prefix="uploads/")
    add_design_url= upload_file_to_s3(additional_design_image, S3_BUCKET_NAME, prefix="uploads/")

    # サイズ合計
    try:
        q_ss = int(size_ss)
        q_s  = int(size_s)
        q_m  = int(size_m)
        q_l  = int(size_l)
        q_ll = int(size_ll)
        q_lll= int(size_lll)
    except:
        q_ss=q_s=q_m=q_l=q_ll=q_lll=0
    total_qty = q_ss + q_s + q_m + q_l + q_ll + q_lll

    # (3) discount_option => 早割/通常
    discount_type = "通常"
    if discount_option == "早割":
        discount_type = "早割"

    # PRICE_TABLEで単価算出(ごく簡易的: base_unit_price x total_qty)
    row = None
    for r in PRICE_TABLE:
        if (r["item"]==product_name
            and r["discount_type"]==discount_type
            and r["min_qty"]<= total_qty <= r["max_qty"]):
            row = r
            break

    if row:
        base_unit_price = row["unit_price"]
        total_price = base_unit_price * total_qty
    else:
        base_unit_price = 0
        total_price = 0

    # 注文番号
    order_number = f"O{int(time.time())}"

    # (4) スプレッドシート書き込み
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_KEY)
    ws = get_or_create_worksheet(sh, "Orders")

    new_row = [
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
        size_ss, size_s, size_m, size_l, size_ll, size_lll,
        print_size_front,
        print_size_front_custom,
        print_color_front,
        font_no_front,
        design_sample_front,
        pos_front_url,
        front_positions_selected,
        print_size_back,
        print_size_back_custom,
        print_color_back,
        font_no_back,
        design_sample_back,
        pos_back_url,
        back_positions_selected,
        print_size_other,
        print_size_other_custom,
        print_color_other,
        font_no_other,
        design_sample_other,
        pos_other_url,
        back_name_number_str,
        additional_design_position,
        add_design_url,
        f"¥{total_price:,}",
        f"¥{base_unit_price:,}",
        order_number,
        user_id
    ]
    ws.append_row(new_row, value_input_option="USER_ENTERED")

    # (5) LINEに「注文番号・注文内容・合計金額・単価」を返す
    reply_msg = (
        f"【ご注文ありがとうございます】\n"
        f"注文番号: {order_number}\n"
        f"商品名: {product_name}\n"
        f"合計枚数: {total_qty}枚\n"
        f"合計金額: ¥{total_price:,}\n"
        f"単価: ¥{base_unit_price:,}\n"
    )
    if user_id:
        try:
            line_bot_api.push_message(to=user_id, messages=TextSendMessage(text=reply_msg))
        except Exception as e:
            print(f"[ERROR] push_message failed: {e}")

    return (
        "注文フォームを受け付けました。スプレッドシートに記録しました。<br>"
        f"注文番号: {order_number}<br>"
        f"合計枚数: {total_qty}枚<br>"
        f"合計金額: ¥{total_price:,} / 単価: ¥{base_unit_price:,}"
    ), 200

# -----------------------
# 動作確認用
# -----------------------
@app.route("/", methods=["GET"])
def health_check():
    return "LINE Bot is running.", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
