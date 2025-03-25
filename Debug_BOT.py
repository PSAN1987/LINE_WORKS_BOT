
import os
import json
import time

import gspread
from flask import Flask, request, abort, render_template_string
from oauth2client.service_account import ServiceAccountCredentials

# line-bot-sdk v2 系
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
)

app = Flask(__name__)

# -----------------------
# 環境変数取得
# -----------------------
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
SERVICE_ACCOUNT_FILE = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")
SPREADSHEET_KEY = os.environ.get("SPREADSHEET_KEY", "")

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
        ws = sheet.add_worksheet(title=title, rows=2000, cols=20)
        # 必要であればヘッダをセット
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
    return ws

def write_to_spreadsheet_for_catalog(form_data: dict):
    """
    カタログ請求フォーム送信のデータをスプレッドシートに1行追加する
    """
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
# 簡易見積用データ構造
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

# ユーザの見積フロー管理用（簡易的セッション）
user_estimate_sessions = {}  # { user_id: {"step": n, "answers": {...}} }

def write_estimate_to_spreadsheet(user_id, estimate_data, total_price, unit_price):
    """
    計算が終わった見積情報をスプレッドシートの「簡易見積」に書き込む
    """
    gc = get_gspread_client()
    sh = gc.open_by_key(SPREADSHEET_KEY)
    worksheet = get_or_create_worksheet(sh, "簡易見積")

    quote_number = str(int(time.time()))  # 見積番号を UNIX時間 で仮生成

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
    """
    PRICE_TABLE から該当する行を探し返す。該当しない場合は None
    """
    for row in PRICE_TABLE:
        if (row["item"] == item_name
            and row["discount_type"] == discount_type
            and row["min_qty"] <= quantity <= row["max_qty"]):
            return row
    return None

def calculate_estimate(estimate_data):
    """
    入力された見積データから合計金額と単価を計算して返す
    """
    item_name = estimate_data['item']
    discount_type = estimate_data['discount_type']
    quantity = int(estimate_data['quantity'])
    print_position = estimate_data['print_position']
    color_choice = estimate_data['color_count']
    back_name = estimate_data['back_name']

    row = find_price_row(item_name, discount_type, quantity)
    if row is None:
        return 0, 0  # 見つからない場合

    base_price = row["unit_price"]

    # プリント位置追加
    if print_position in ["前のみ", "背中のみ"]:
        pos_add = 0
    else:
        pos_add = row["pos_add"]

    # 色数追加
    color_add_count, fullcolor_add_count = COLOR_COST_MAP[color_choice]
    color_fee = color_add_count * row["color_add"] + fullcolor_add_count * row["fullcolor_add"]

    # 背ネーム・番号
    if back_name == "ネーム&背番号セット":
        back_name_fee = row["set_name_num"]
    elif back_name == "ネーム(大)":
        back_name_fee = row["big_name"]
    elif back_name == "番号(大)":
        back_name_fee = row["big_num"]
    else:
        # 背ネーム・番号を使わない
        back_name_fee = 0

    unit_price = base_price + pos_add + color_fee + back_name_fee
    total_price = unit_price * quantity

    return total_price, unit_price


from linebot.models import FlexSendMessage

from linebot.models import FlexSendMessage

def flex_usage_date():
    """
    ❶使用日 (14日前以上 or 14日前以内)
    """
    flex_body = {
        "type": "bubble",
        # タイトルと説明文を hero 部分に配置
        "hero": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "❶使用日",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center"    # ★中央揃え
                },
                {
                    "type": "text",
                    "text": "大会やイベントで使用する日程を教えてください。(注文日が14日前以上なら早割)",
                    "size": "sm",
                    "wrap": True
                }
            ]
        },
        # ボタン群を footer に配置
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "action": {
                        "type": "message",
                        "label": "14日前以上",
                        "text": "14日前以上"
                    }
                },
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "action": {
                        "type": "message",
                        "label": "14日前以内",
                        "text": "14日前以内"
                    }
                }
            ],
            "flex": 0
        }
    }
    return FlexSendMessage(alt_text="使用日を選択してください", contents=flex_body)


def flex_budget():
    """
    ❷1枚当たりの予算
    """
    budgets = ["1,000円", "2,000円", "3,000円", "4,000円", "5,000円"]
    buttons = []
    for b in budgets:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "message",
                "label": b,
                "text": b
            }
        })

    flex_body = {
        "type": "bubble",
        "hero": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "❷1枚当たりの予算",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center"    # ★中央揃え
                },
                {
                    "type": "text",
                    "text": "ご希望の1枚あたり予算を選択してください。",
                    "size": "sm",
                    "wrap": True
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons,
            "flex": 0
        }
    }
    return FlexSendMessage(alt_text="予算を選択してください", contents=flex_body)


def flex_item_select():
    """
    ❸商品名
    """
    items = [
        "ドライTシャツ","ヘビーウェイトTシャツ","ドライポロシャツ","ドライメッシュビブス",
        "ドライベースボールシャツ","ドライロングスリープTシャツ","ドライハーフパンツ",
        "ヘビーウェイトロングスリープTシャツ","クルーネックライトトレーナー",
        "フーデッドライトパーカー","スタンダードトレーナー","スタンダードWフードパーカー",
        "ジップアップライトパーカー"
    ]

    # 商品リストを分割しながら、複数のbubbleを束ねたcarouselを作る
    item_bubbles = []
    chunk_size = 5
    for i in range(0, len(items), chunk_size):
        chunk_part = items[i:i+chunk_size]
        buttons = []
        for it in chunk_part:
            buttons.append({
                "type": "button",
                "style": "primary",
                "height": "sm",
                "action": {
                    "type": "message",
                    "label": it,
                    "text": it
                }
            })
        # 各bubbleにも hero と footer を設置
        bubble = {
            "type": "bubble",
            "hero": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "❸商品名",
                        "weight": "bold",
                        "size": "lg",
                        "align": "center"    # ★中央揃え
                    },
                    {
                        "type": "text",
                        "text": "ご希望の商品を選択してください。",
                        "size": "sm",
                        "wrap": True
                    }
                ]
            },
            # body を空にし、footer にボタンを置く
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": buttons
            }
        }
        item_bubbles.append(bubble)

    carousel = {
        "type": "carousel",
        "contents": item_bubbles
    }
    return FlexSendMessage(alt_text="商品名を選択してください", contents=carousel)


def flex_quantity():
    """
    ❹枚数
    """
    quantities = ["10", "20", "30", "40", "50", "100"]
    buttons = []
    for q in quantities:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "message",
                "label": q,
                "text": q
            }
        })

    flex_body = {
        "type": "bubble",
        "hero": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "❹枚数",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center"    # ★中央揃え
                },
                {
                    "type": "text",
                    "text": "必要枚数を選択してください。",
                    "size": "sm",
                    "wrap": True
                },
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons
        }
    }
    return FlexSendMessage(alt_text="必要枚数を選択してください", contents=flex_body)


def flex_print_position():
    """
    ❺プリント位置
    """
    positions = ["前のみ", "背中のみ", "前と背中"]
    buttons = []
    for pos in positions:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "message",
                "label": pos,
                "text": pos
            }
        })

    flex_body = {
        "type": "bubble",
        "hero": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "❺プリント位置",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center"   # ★中央揃え
                },
                {
                    "type": "text",
                    "text": "プリントを入れる箇所を選択してください。",
                    "size": "sm",
                    "wrap": True
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons
        }
    }
    return FlexSendMessage(alt_text="プリント位置を選択してください", contents=flex_body)


def flex_color_count():
    """
    ❻色数
    """
    color_list = [
        "前 or 背中 1色",
        "前 or 背中 2色",
        "前 or 背中 フルカラー",
        "前と背中 前1色 背中1色",
        "前と背中 前2色 背中1色",
        "前と背中 前1色 背中2色",
        "前と背中 前2色 背中2色",
        "前と背中 フルカラー",
    ]
    chunk_size = 4
    color_bubbles = []
    for i in range(0, len(color_list), chunk_size):
        chunk_part = color_list[i:i+chunk_size]
        buttons = []
        for c in chunk_part:
            buttons.append({
                "type": "button",
                "style": "primary",
                "height": "sm",
                "action": {
                    "type": "message",
                    "label": c[:12],  # 表示ラベルが長い場合に短縮
                    "text": c
                }
            })
        bubble = {
            "type": "bubble",
            "hero": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "❻色数",
                        "weight": "bold",
                        "size": "lg",
                        "align": "center"   # ★中央揃え
                    },
                    {
                        "type": "text",
                        "text": "プリントの色数を選択してください。",
                        "size": "sm",
                        "wrap": True
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": buttons
            }
        }
        color_bubbles.append(bubble)

    carousel = {
        "type": "carousel",
        "contents": color_bubbles
    }
    return FlexSendMessage(alt_text="色数を選択してください", contents=carousel)


def flex_back_name():
    """
    ❼背ネーム・番号
    """
    names = ["ネーム&背番号セット", "ネーム(大)", "番号(大)", "背ネーム・番号を使わない"]
    buttons = []
    for nm in names:
        buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "message",
                "label": nm,
                "text": nm
            }
        })

    flex_body = {
        "type": "bubble",
        "hero": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "❼背ネーム・番号",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center"   # ★中央揃え
                },
                {
                    "type": "text",
                    "text": "背ネームや番号を入れる場合は選択してください。",
                    "size": "sm",
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": "不要な場合は「背ネーム・番号を使わない」を選択してください。",
                    "size": "sm",
                    "wrap": True
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons
        }
    }
    return FlexSendMessage(alt_text="背ネーム・番号を選択してください", contents=flex_body)



# -----------------------
# 1) LINE Messaging API 受信 (Webhook)
# -----------------------
@app.route("/line/callback", methods=["POST"])
def line_callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400, "Invalid signature. Please check your channel access token/channel secret.")

    return "OK", 200

# -----------------------
# 2) LINE上でメッセージ受信時
# -----------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # すでに見積りフロー中かどうか
    if user_id in user_estimate_sessions and user_estimate_sessions[user_id]["step"] > 0:
        process_estimate_flow(event, user_message)
        return

    # 見積りフロー開始
    if user_message == "お見積り":
        start_estimate_flow(event)
        return

    # カタログ案内
    # 完全一致で新しい案内文を返信
    if "カタログ" in user_message or "catalog" in user_message.lower():
        send_catalog_info(event)
        return

    # その他のメッセージ
    return

def send_catalog_info(event: MessageEvent):
    """
    カタログ案内メッセージ（ご指定の文面を完全一致で返す）
    """
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
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# -----------------------
# 見積りフロー
# -----------------------
def start_estimate_flow(event: MessageEvent):
    """
    見積りフロー開始: ステップ1(使用日) へ
    """
    user_id = event.source.user_id
    user_estimate_sessions[user_id] = {
        "step": 1,
        "answers": {}
    }
    line_bot_api.reply_message(
        event.reply_token,
        flex_usage_date()
    )

def process_estimate_flow(event: MessageEvent, user_message: str):
    """
    見積フロー中のやり取り
    """
    user_id = event.source.user_id
    session_data = user_estimate_sessions[user_id]
    step = session_data["step"]

    if step == 1:
        # 1.使用日
        if user_message in ["14日前以上", "14日前以内"]:
            session_data["answers"]["usage_date"] = user_message
            session_data["answers"]["discount_type"] = "早割" if user_message == "14日前以上" else "通常"
            session_data["step"] = 2
            line_bot_api.reply_message(event.reply_token, flex_budget())
        else:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="「14日前以上」または「14日前以内」を選択してください。"))
    elif step == 2:
        # 2.1枚当たりの予算
        budgets = ["1,000円", "2,000円", "3,000円", "4,000円", "5,000円"]
        if user_message in budgets:
            session_data["answers"]["budget"] = user_message
            session_data["step"] = 3
            line_bot_api.reply_message(event.reply_token, flex_item_select())
        else:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="1枚あたりの予算をボタンから選択してください。"))
    elif step == 3:
        # 3.商品名
        items = [
            "ドライTシャツ","ヘビーウェイトTシャツ","ドライポロシャツ","ドライメッシュビブス",
            "ドライベースボールシャツ","ドライロングスリープTシャツ","ドライハーフパンツ",
            "ヘビーウェイトロングスリープTシャツ","クルーネックライトトレーナー",
            "フーデッドライトパーカー","スタンダードトレーナー","スタンダードWフードパーカー",
            "ジップアップライトパーカー"
        ]
        if user_message in items:
            session_data["answers"]["item"] = user_message
            session_data["step"] = 4
            line_bot_api.reply_message(event.reply_token, flex_quantity())
        else:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="商品名をボタンから選択してください。"))
    elif step == 4:
        # 4.枚数
        # ★修正： '50', '100' が追加されている
        valid_choices = ["10","20","30","40","50","100"]
        if user_message in valid_choices:
            # ここでは選んだ数字をそのまま採用
            session_data["answers"]["quantity"] = user_message
            session_data["step"] = 5
            line_bot_api.reply_message(event.reply_token, flex_print_position())
        else:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="枚数をボタンから選択してください。"))
    elif step == 5:
        # 5.プリント位置
        valid_positions = ["前のみ", "背中のみ", "前と背中"]
        if user_message in valid_positions:
            session_data["answers"]["print_position"] = user_message
            session_data["step"] = 6
            line_bot_api.reply_message(event.reply_token, flex_color_count())
        else:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="プリント位置を選択してください。"))
    elif step == 6:
        # 6.色数
        color_list = list(COLOR_COST_MAP.keys())
        if user_message in color_list:
            session_data["answers"]["color_count"] = user_message
            session_data["step"] = 7
            line_bot_api.reply_message(event.reply_token, flex_back_name())
        else:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="色数を選択してください。"))
    elif step == 7:
        # 7.背ネーム・番号
        valid_back_names = ["ネーム&背番号セット", "ネーム(大)", "番号(大)", "背ネーム・番号を使わない"]
        if user_message in valid_back_names:
            session_data["answers"]["back_name"] = user_message
            session_data["step"] = 8
            # 計算
            est_data = session_data["answers"]
            quantity = int(est_data["quantity"])
            total_price, unit_price = calculate_estimate(est_data)
            quote_number = write_estimate_to_spreadsheet(user_id, est_data, total_price, unit_price)

            reply_text = (
                f"お見積りが完了しました。\n\n"
                f"見積番号: {quote_number}\n"
                f"使用日: {est_data['usage_date']}（{est_data['discount_type']}）\n"
                f"予算: {est_data['budget']}\n"
                f"商品: {est_data['item']}\n"
                f"枚数: {quantity}枚\n"
                f"プリント位置: {est_data['print_position']}\n"
                f"色数: {est_data['color_count']}\n"
                f"背ネーム・番号: {est_data['back_name']}\n\n"
                f"【合計金額】¥{total_price:,}\n"
                f"【1枚あたり】¥{unit_price:,}\n"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

            # フロー終了
            del user_estimate_sessions[user_id]
        else:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="背ネーム・番号の選択肢からお選びください。"))
    else:
        # それ以外
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text="エラーが発生しました。最初からやり直してください。"))
        if user_id in user_estimate_sessions:
            del user_estimate_sessions[user_id]

# -----------------------
# 3) カタログ申し込みフォーム表示 (GET)
# -----------------------
@app.route("/catalog_form", methods=["GET"])
def show_catalog_form():
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>カタログ申し込みフォーム</title>
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
            const response = await fetch(`https://api.zipaddress.net/?zipcode=${pcRaw}`);
            const data = await response.json();
            if (data.code === 200) {
                document.getElementById('address').value = data.data.fullAddress;
            }
        } catch (error) {
            console.log("住所検索失敗:", error);
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

# -----------------------
# 4) カタログ申し込みフォームの送信処理
# -----------------------
@app.route("/submit_form", methods=["POST"])
def submit_catalog_form():
    form_data = {
        "name": request.form.get("name", "").strip(),
        "postal_code": request.form.get("postal_code", "").strip(),
        "address": request.form.get("address", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "email": request.form.get("email", "").strip(),
        "sns_account": request.form.get("sns_account", "").strip(),
        "school_grade": request.form.get("school_grade", "").strip(),
        "other": request.form.get("other", "").strip(),
    }

    try:
        write_to_spreadsheet_for_catalog(form_data)
    except Exception as e:
        return f"エラーが発生しました: {e}", 500

    return "フォーム送信ありがとうございました！ カタログ送付をお待ちください。", 200

# -----------------------
# 動作確認用
# -----------------------
@app.route("/", methods=["GET"])
def health_check():
    return "LINE Bot is running.", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
