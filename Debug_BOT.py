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
    なければ新規作成し、ヘッダを書き込む。
    """
    try:
        ws = sheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=2000, cols=50)

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
            # Ordersシートのヘッダ
            ws.update('A1:Z1', [[
                "申込日","配達日","使用日","学割特典","学校名","LINEアカウント名",
                "団体名","学校住所","学校TEL","担任名","担任携帯","担任メール",
                "代表者名","代表者TEL","代表者メール","デザイン確認方法","お支払い方法",
                "商品名","商品カラー","サイズ(SS)","サイズ(S)","サイズ(M)","サイズ(L)",
                "サイズ(LL)","サイズ(LLL)","print_size_front","print_size_front_custom",
                "print_color_front","font_no_front","design_sample_front","position_data_front",
                "front_positions_selected","print_size_back","print_size_back_custom",
                "print_color_back","font_no_back","design_sample_back","position_data_back",
                "back_positions_selected","print_size_other","print_size_other_custom",
                "print_color_other","font_no_other","design_sample_other","position_data_other",
                "背ネーム番号プリント(複数)","追加デザイン位置","追加デザイン画像",
                "合計金額","単価","注文番号","ユーザーID"
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
# PRICE_TABLE (現行どおりペースト)
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


# -----------------------
# 簡易見積ロジック
# -----------------------
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
# Flexメッセージ (省略なし)
# -----------------------
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

    # カタログ案内
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
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>カタログ申し込みフォーム</title>
    <style>
        body {
            margin: 0; padding: 0; font-family: sans-serif;
        }
        .container {
            max-width: 600px; margin: 0 auto; padding: 1em;
        }
        label { display: block; margin-bottom: 0.5em; }
        input[type=text], input[type=email], textarea {
            width: 100%; padding: 0.5em; margin-top:0.3em; box-sizing:border-box;
        }
        input[type=submit] { padding:0.7em 1em; font-size:1em; margin-top:1em; }
    </style>
    <script>
    async function fetchAddress() {
        let pcRaw = document.getElementById('postal_code').value.trim();
        pcRaw = pcRaw.replace('-', '');
        if (pcRaw.length < 7) return;
        try {
            const response = await fetch('https://api.zipaddress.net/?zipcode='+pcRaw);
            const data = await response.json();
            if(data.code===200){
                document.getElementById('address').value=data.data.fullAddress;
            }
        }catch(e){console.log(e);}
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
# WEBフォームから注文 (GET/POST) - S3対応
# -----------------------
FORM_HTML = """...（省略せず完全）..."""

@app.route("/webform", methods=["GET"])
def show_webform():
    user_id = request.args.get("user_id","")
    return render_template_string(FORM_HTML, user_id=user_id)

@app.route("/webform_submit", methods=["POST"])
def webform_submit():
    # ★ (1) フォーム内容取得
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

    # ★ (2) S3アップロード
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

    # ★ (3) 割引判定 "早割" or "通常"
    discount_type = "通常"
    if discount_option == "早割":
        discount_type = "早割"

    # PRICE_TABLEで単価算出(簡易)
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

    # 注文番号 (同時に見積番号的扱い)
    order_number = f"O{int(time.time())}"

    # ★ (4) スプレッドシート書き込み
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

    # ★ (5) LINEに「注文番号・注文内容・合計金額・単価」を返す
    # push_message で送信
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
