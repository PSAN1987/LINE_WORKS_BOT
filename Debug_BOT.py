﻿import os
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
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage,
    ImageMessage
)
from werkzeug.utils import secure_filename

# --- 別ファイルに分割されているテーブル類をインポート ---
from price_table import PRICE_TABLE, COLOR_COST_MAP
from webform_template import FORM_HTML  # HTMLテンプレート

import openai
from google.cloud import vision
from google.oauth2 import service_account

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

openai_api_key = os.environ.get("OPENAI_API_KEY", "")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# -----------------------
# グローバル辞書
# -----------------------
# 「注文用紙から注文」フローで OCR & OpenAI により抽出したフォーム入力データを保持する
# キー: user_id, 値: dict (extracted_form_data)
webform_prepopulate_data = {}

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
        ws = sheet.add_worksheet(title=title, rows=2000, cols=120)
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
            ws.update('A1:BG1', [[
                # ①基本情報
                "申込日", "配達日", "使用日", "学割特典",
                "学校名", "LINEアカウント名", "団体名", "学校住所",
                "学校TEL", "担任名", "担任携帯", "担任メール",
                "代表者名", "代表者TEL", "代表者メール",

                # ②お届け先
                "お届け先 郵便番号", "お届け先 住所", "お届け先 建物名・部屋番号",

                # ③その他
                "デザイン確認方法", "お支払い方法",
                "商品名", "商品カラー",

                "サイズ(SS)", "サイズ(S)", "サイズ(M)", "サイズ(L)", "サイズ(LL)", "サイズ(LLL)",

                "前プリントサイズ", "前プリントサイズ指定",
                "前プリントカラー", "前フォントNo", "前デザインサンプル", "前位置データURL",
                "前位置選択",

                "背面プリントサイズ", "背面プリントサイズ指定",
                "背面プリントカラー", "背面フォントNo", "背面デザインサンプル", "背面位置データURL",
                "背面位置選択",

                "その他プリントサイズ", "その他プリントサイズ指定",
                "その他プリントカラー", "その他フォントNo", "その他デザインサンプル", "その他位置データURL",

                "背ネーム・背番号プリント",
                "追加デザイン位置", "追加デザイン画像URL",

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
    戻り値: アップロード先のS3ファイルURL (無い場合は空文字)
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
# 簡易見積
# -----------------------
user_estimate_sessions = {}

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
# 注文用紙から注文フロー用: ユーザーが画像を送るまでの簡易管理
# -----------------------
user_order_form_image_sessions = {}


# -----------------------
# Google Vision OCR (実際のAPI呼び出し)
# -----------------------
def google_vision_ocr(image_data: bytes) -> str:
    """
    Google Vision APIを使用して実際にOCRを行う関数。
    """
    if not SERVICE_ACCOUNT_FILE:
        raise ValueError("環境変数 GCP_SERVICE_ACCOUNT_JSON が設定されていません。")

    service_account_dict = json.loads(SERVICE_ACCOUNT_FILE)
    credentials = service_account.Credentials.from_service_account_info(service_account_dict)

    client = vision.ImageAnnotatorClient(credentials=credentials)
    image = vision.Image(content=image_data)

    response = client.text_detection(image=image)
    if response.error.message:
        raise RuntimeError(f"Google Vision OCRエラー: {response.error.message}")

    ocr_text = response.full_text_annotation.text
    return ocr_text


# -----------------------
# OpenAI でフォーム項目抽出 (実際のAPI呼び出し)
# -----------------------
def openai_extract_form_data(ocr_text: str) -> dict:
    """
    OCRテキストをOpenAIに渡して分析し、注文フォーム入力用データを抽出する。
    あなたは注文用紙のOCR結果から必要な項目を抽出するアシスタントです。
    入力として渡されるテキスト（OCR結果）を解析し、次のフォーム項目に合致する値を抽出してJSONで返してください。
    日付項目（application_date, delivery_date, use_date etc）は必ず YYYY-MM-DD の形式で返してください
    必ず JSON のみを返し、余計な文章は一切出力しないでください。
    JSONはコードブロック (\\\\`) で囲まず、そのままのプレーンテキストで出力してください。さらに、先頭や末尾に余計な文章を付けず、JSON 以外の文字は出力しないでください。
    application_date, delivery_date, use_date は必ず「YYYY-MM-DD」形式の文字列で返す。discount_option は "早割", "タダ割", "いっしょ割り" のうち1つのみ。size_s, size_m, size_l などは必ず整数値とし、文字列ではなく数字として返す。print_color_front は カンマ区切りの1つの文字列にまとめる (例: "赤,白" )
    """
    if not openai_api_key:
        raise ValueError("環境変数 OPENAI_API_KEY が設定されていません。")
    openai.api_key = openai_api_key

    system_message = {
        "role": "system",
        "content": (
            "You are an AI assistant that extracts order form information from the provided text.\n\n"

            "You must output ONLY valid JSON (no code block fences or extra text) with the following keys:\n\n"

            "1) application_date (string, format: YYYY-MM-DD or empty)\n"
            "2) delivery_date (string, format: YYYY-MM-DD or empty)\n"
            "3) use_date (string, format: YYYY-MM-DD or empty)\n"
            "4) discount_option (string) — possible values are '早割','タダ割','いっしょ割り' or empty\n"
            "5) school_name (string)\n"
            "6) line_account (string)\n"
            "7) group_name (string)\n"
            "8) school_address (string)\n"
            "9) school_tel (string)\n"
            "10) teacher_name (string)\n"
            "11) teacher_tel (string)\n"
            "12) teacher_email (string)\n"
            "13) representative (string)\n"
            "14) rep_tel (string)\n"
            "15) rep_email (string)\n"
            "16) delivery_zip (string)\n"
            "17) delivery_address (string)\n"
            "18) delivery_address2 (string)\n"
            "19) design_confirm (string)\n"
            "20) payment_method (string)\n"
            "21) product_name (string)\n"
            "22) product_color (string)\n"
            "23) size_ss (string, digits only or empty)\n"
            "24) size_s (string, digits only or empty)\n"
            "25) size_m (string, digits only or empty)\n"
            "26) size_l (string, digits only or empty)\n"
            "27) size_ll (string, digits only or empty)\n"
            "28) size_lll (string, digits only or empty)\n"
            "29) print_size_front (string)\n"
            "30) print_size_front_custom (string)\n"
            "31) print_color_front (array of strings)\n"
            "32) font_no_front (string)\n"
            "33) design_sample_front (string)\n"
            "34) front_positions_selected (array of strings)\n"
            "35) print_size_back (string)\n"
            "36) print_size_back_custom (string)\n"
            "37) print_color_back (array of strings)\n"
            "38) font_no_back (string)\n"
            "39) design_sample_back (string)\n"
            "40) back_positions_selected (array of strings)\n"
            "41) print_size_other (string)\n"
            "42) print_size_other_custom (string)\n"
            "43) print_color_other (array of strings)\n"
            "44) font_no_other (string)\n"
            "45) design_sample_other (string)\n"
            "46) other_positions_selected (array of strings)\n"
            "47) back_name_number_print (array of strings)\n"
            "48) name_number_color_type (string)\n"
            "49) single_color_choice (string)\n"
            "50) outline_type (string)\n"
            "51) outline_text_color (string)\n"
            "52) outline_edge_color (string)\n"
            "53) additional_design_position (string)\n\n"

            "If a value is not found, use an empty string or empty array.\n"
            "Do not include any keys beyond this list. Do not include any extra text.\n"
            "Return only valid JSON with double quotes for keys and string values.\n"
            "Do not wrap the JSON in triple backticks.\n"
        )
    }


    user_message = {
        "role": "user",
        "content": f"Extract the form data from this OCR text:\n{ocr_text}"
    }

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[system_message, user_message],
        temperature=0.0
    )

    assistant_text = response["choices"][0]["message"]["content"].strip()
    assistant_text = assistant_text.strip()
    # もし「```json」～「```」というブロックがあれば取り除く (最小限の例)
    assistant_text = assistant_text.replace("```json", "")
    assistant_text = assistant_text.replace("```", "")
    # 余計な改行やスペースをさらに strip
    assistant_text = assistant_text.strip()
    # その上で json.loads する
    parsed_data = json.loads(assistant_text)
    
    # JSONとしてパース
    try:
        parsed_data = json.loads(assistant_text)
    except json.JSONDecodeError:
        raise ValueError("OpenAI応答がJSONとしてパースできませんでした。\n応答内容:\n" + assistant_text)

    return parsed_data


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
def handle_text_message(event: MessageEvent):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 簡易見積りフロー中かどうか
    if user_id in user_estimate_sessions and user_estimate_sessions[user_id]["step"]>0:
        process_estimate_flow(event, text)
        return

    # 「お見積り」フロー開始
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

    # 注文用紙から注文
    if text == "注文用紙から注文":
        user_order_form_image_sessions[user_id] = "waiting_for_image"
        reply_text = "注文用紙の写真を送ってください。(スマホで撮影した写真でOKです)"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event: MessageEvent):
    """
    注文用紙から注文のフロー:
      1) 画像受信 → OCR実行 → OpenAI解析
      2) 抽出結果を一時保存
      3) ユーザーにフォームURLを案内
    """
    user_id = event.source.user_id
    if user_id not in user_order_form_image_sessions:
        return
    if user_order_form_image_sessions[user_id] != "waiting_for_image":
        return

    try:
        # 1) まずOCR中メッセージを返す
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="画像を受信しました。OCR解析を行っています。少しお待ちください...")
        )

        # 2) 画像バイナリ取得
        message_id = event.message.id
        message_content = line_bot_api.get_message_content(message_id)
        image_data = b""
        for chunk in message_content.iter_content():
            image_data += chunk

        # 3) Google VisionでOCR
        ocr_text = google_vision_ocr(image_data)

        # 4) OpenAIでフォーム項目抽出
        extracted_form_data = openai_extract_form_data(ocr_text)

        # 5) 抽出結果をグローバル辞書に保存
        webform_prepopulate_data[user_id] = extracted_form_data
        
        # ▼▼ ここでログに出す ▼▼
        logger.info(f"[DEBUG] user_id={user_id} の extracted_form_data: {extracted_form_data}")
        
        # 6) フォームURLを案内
        form_url = f"https://{request.host}/webform?user_id={user_id}"
        finish_text = (
            "注文用紙の画像から情報を読み取りました。\n"
            "WEBフォームに自動入力しておりますので、内容をご確認・修正のうえ送信ください。\n\n"
            f"{form_url}"
        )
        line_bot_api.push_message(user_id, TextSendMessage(text=finish_text))

    except Exception as e:
        error_msg = (
            f"OCRまたはOpenAI解析でエラーが発生しました: {e}\n"
            "メニューに戻っていただき、「注文用紙から注文」を再度クリックお願いします。"
        )
        line_bot_api.push_message(user_id, TextSendMessage(text=error_msg))

    finally:
        # セッション解除
        if user_id in user_order_form_image_sessions:
            del user_order_form_image_sessions[user_id]


# -----------------------
# 簡易見積りフロー
# -----------------------
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

            edata = session_data["answers"]
            quantity = int(edata["quantity"])
            row = find_price_row(edata["item"], edata["discount_type"], quantity)
            if row is None:
                total_price, unit_price = 0, 0
            else:
                base_unit_price = row["unit_price"]
                if edata["print_position"] in ["前のみ","背中のみ"]:
                    pos_add = 0
                else:
                    pos_add = row["pos_add"]
                unit_price = base_unit_price + pos_add
                total_price = unit_price * quantity

            quote_number = write_estimate_to_spreadsheet(
                user_id, edata, total_price, unit_price
            )

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
# (追加) 背ネームカラー加算用の辞書
# -----------------------
BACKNAME_COLOR_MAP = {
    "シルバー": 100,
    "ゴールド": 100,
    "グリッターシルバー": 200,
    "グリッターゴールド": 200,
    "グリッターピンク": 200,
}


# -----------------------
# WEBフォーム注文 (GET/POST)
# -----------------------
def parse_print_colors(color_str):
    """
    カンマ区切りの色リストを解析:
      - 通常色の個数
      - フルカラー固定加算(合計)
      - グリッター／蛍光色の個数
    を返すタプル (normal_color_count, fullcolor_cost, glitter_fluo_count)
    """
    if not color_str.strip():
        return 0, 0, 0

    colors = [c.strip() for c in color_str.split(",") if c.strip()]
    normal_color_count = 0
    fullcolor_cost = 0
    glitter_fluo_count = 0

    glitter_or_fluo_list = [
        "グリッターシルバー","グリッターゴールド","グリッターブラック","グリッターイエロー",
        "グリッターピンク","グリッターレッド","グリッターグリーン","グリッターブルー","グリッターパープル",
        "蛍光オレンジ","蛍光ピンク","蛍光グリーン"
    ]

    for c in colors:
        if "フルカラー(小)" in c:
            fullcolor_cost += 350
        elif "フルカラー(中)" in c:
            fullcolor_cost += 550
        elif "フルカラー(大)" in c:
            fullcolor_cost += 990
        else:
            normal_color_count += 1
            if c in glitter_or_fluo_list:
                glitter_fluo_count += 1

    return normal_color_count, fullcolor_cost, glitter_fluo_count


@app.route("/webform", methods=["GET"])
def show_webform():
    """
    注文用WEBフォームを表示する。
    もし事前に OCR & OpenAI で抽出したデータがあれば、それをデフォルト値として埋め込む。
    """
    user_id = request.args.get("user_id","")
    extracted_data = webform_prepopulate_data.get(user_id, {})

    return render_template_string(FORM_HTML, user_id=user_id, extracted_data=extracted_data)


@app.route("/webform_submit", methods=["POST"])
def webform_submit():
    """
    フォームの入力を受け取り、合計金額を計算してスプレッドシートに書き込み、
    さらにLINEに注文番号などを通知。
    """
    user_id = request.form.get("user_id","")

    # 以下、フォームからの入力取得 (全て同一)
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

    delivery_zip = request.form.get("delivery_zip","")
    delivery_address = request.form.get("delivery_address","")
    delivery_address2 = request.form.get("delivery_address2","")

    design_confirm= request.form.get("design_confirm","")
    payment_method= request.form.get("payment_method","")
    product_name = request.form.get("product_name","")
    product_color= request.form.get("product_color","")

    def to_int(val):
        try:
            return int(val)
        except:
            return 0

    size_ss = to_int(request.form.get("size_ss","0"))
    size_s  = to_int(request.form.get("size_s","0"))
    size_m  = to_int(request.form.get("size_m","0"))
    size_l  = to_int(request.form.get("size_l","0"))
    size_ll = to_int(request.form.get("size_ll","0"))
    size_lll= to_int(request.form.get("size_lll","0"))
    total_qty = size_ss + size_s + size_m + size_l + size_ll + size_lll

    print_size_front= request.form.get("print_size_front","")
    print_size_front_custom= request.form.get("print_size_front_custom","")
    print_color_front_list = request.form.getlist("print_color_front[]")
    print_color_front = ",".join(print_color_front_list)
    font_no_front= request.form.get("font_no_front","")
    design_sample_front= request.form.get("design_sample_front","")
    position_data_front= request.files.get("position_data_front")
    front_positions_selected= request.form.get("front_positions_selected","")

    print_size_back= request.form.get("print_size_back","")
    print_size_back_custom= request.form.get("print_size_back_custom","")
    print_color_back_list = request.form.getlist("print_color_back[]")
    print_color_back = ",".join(print_color_back_list)
    font_no_back= request.form.get("font_no_back","")
    design_sample_back= request.form.get("design_sample_back","")
    position_data_back= request.files.get("position_data_back")
    back_positions_selected= request.form.get("back_positions_selected","")

    print_size_other= request.form.get("print_size_other","")
    print_size_other_custom= request.form.get("print_size_other_custom","")
    print_color_other_list = request.form.getlist("print_color_other[]")
    print_color_other = ",".join(print_color_other_list)
    font_no_other= request.form.get("font_no_other","")
    design_sample_other= request.form.get("design_sample_other","")
    position_data_other= request.files.get("position_data_other")
    other_positions_selected= request.form.get("other_positions_selected","")

    back_name_number_opts = request.form.getlist("back_name_number_print[]")
    back_name_number_str = ",".join(back_name_number_opts) if back_name_number_opts else ""

    name_number_color_type= request.form.get("name_number_color_type","")
    single_color_choice= request.form.get("single_color_choice","")
    outline_type= request.form.get("outline_type","")
    outline_text_color= request.form.get("outline_text_color","")
    outline_edge_color= request.form.get("outline_edge_color","")

    additional_design_position= request.form.get("additional_design_position","")
    additional_design_image= request.files.get("additional_design_image")

    # 画像アップロード (S3)
    pos_front_url = upload_file_to_s3(position_data_front, S3_BUCKET_NAME, prefix="uploads/")
    pos_back_url  = upload_file_to_s3(position_data_back,  S3_BUCKET_NAME, prefix="uploads/")
    pos_other_url = upload_file_to_s3(position_data_other, S3_BUCKET_NAME, prefix="uploads/")
    add_design_url= upload_file_to_s3(additional_design_image, S3_BUCKET_NAME, prefix="uploads/")

    # 割引区分
    discount_type = "通常"
    if discount_option == "早割":
        discount_type = "早割"

    row = find_price_row(product_name, discount_type, total_qty)
    if row is None:
        base_unit_price = 0
        base_pos_add = 0
        base_color_add = 0
    else:
        base_unit_price = row["unit_price"]
        base_pos_add = row["pos_add"]
        base_color_add = row["color_add"]

    # プリント位置数での追加費用
    front_used = bool(print_color_front.strip())
    back_used  = bool(print_color_back.strip())
    other_used = bool(print_color_other.strip())
    used_positions = sum([front_used, back_used, other_used])
    if used_positions <= 1:
        pos_add_fee = 0
    else:
        pos_add_fee = base_pos_add

    # 色数解析
    f_normal, f_full, f_gf = parse_print_colors(print_color_front)
    b_normal, b_full, b_gf = parse_print_colors(print_color_back)
    o_normal, o_full, o_gf = parse_print_colors(print_color_other)

    total_normal_color = f_normal + b_normal + o_normal
    total_fullcolor_cost = f_full + b_full + o_full
    total_glitter_fluo_count = f_gf + b_gf + o_gf

    # 通常色2色目以降
    if total_normal_color > 1:
        normal_color_fee = base_color_add * (total_normal_color - 1)
    else:
        normal_color_fee = 0

    # グリッター／蛍光 加算
    glitter_fluo_fee = total_glitter_fluo_count * 100

    # 背ネーム・番号
    backname_fee = 0
    if back_name_number_opts:
        for val in back_name_number_opts:
            v = val.strip()
            if v == "ネーム&背番号セット":
                backname_fee += 900
            elif v == "ネーム(大)":
                backname_fee += 550
            elif v == "ネーム(小)":
                backname_fee += 250
            elif v == "番号(大)":
                backname_fee += 550
            elif v == "番号(小)":
                backname_fee += 250

    # フチ付き指定
    backname_outline_base = 0
    if name_number_color_type == "outline":
        backname_outline_base = 100

    backname_colors_fee = 0
    if name_number_color_type == "outline":
        backname_colors_fee += BACKNAME_COLOR_MAP.get(outline_text_color, 0)
        backname_colors_fee += BACKNAME_COLOR_MAP.get(outline_edge_color, 0)
    elif name_number_color_type == "single":
        backname_colors_fee += BACKNAME_COLOR_MAP.get(single_color_choice, 0)

    backname_color_fee = backname_outline_base + backname_colors_fee

    # 単価計算
    unit_price = (
        base_unit_price
        + pos_add_fee
        + normal_color_fee
        + total_fullcolor_cost
        + backname_fee
        + backname_color_fee
        + glitter_fluo_fee
    )
    total_price = unit_price * total_qty

    calculation_breakdown = (
        "【単価計算内訳】\n"
        f"📚 ベース単価: ¥{base_unit_price:,}\n"
        f"📚 プリント位置追加: ¥{pos_add_fee:,}\n"
        f"📚 通常色: ¥{normal_color_fee:,}\n"
        f"📚 フルカラー: ¥{total_fullcolor_cost:,}\n"
        f"📚 グリッター／蛍光色加算: ¥{glitter_fluo_fee:,}\n"
        f"📚 背ネーム/番号プリント: ¥{backname_fee:,}\n"
        f"📚 背ネームカラー: ¥{backname_color_fee:,}\n"
        "--------------------------------------\n"
        f"📚 1枚あたり単価: ¥{unit_price:,}\n"
        f"📚 合計枚数: {total_qty}枚\n"
        f"📚【合計金額】¥{total_price:,}\n"
    )

    order_number = f"O{int(time.time())}"

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

        delivery_zip,
        delivery_address,
        delivery_address2,

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
        f"¥{unit_price:,}",
        order_number,
        user_id
    ]
    ws.append_row(new_row, value_input_option="USER_ENTERED")

    front_text = f"前面プリント色: {print_color_front}" if front_used else ""
    back_text  = f"背面プリント色: {print_color_back}"  if back_used  else ""
    oth_text   = f"その他プリント色: {print_color_other}" if other_used else ""
    used_positions_text = "\n".join([t for t in [front_text, back_text, oth_text] if t])

    backname_text = back_name_number_str if back_name_number_str else "無し"

    if name_number_color_type == "single":
        backname_color_text = f"単色({single_color_choice})"
    else:
        backname_color_text = f"フチ付き(文字色:{outline_text_color}, フチ色:{outline_edge_color}, タイプ:{outline_type})"

    reply_msg = (
        f"🎁【ご注文ありがとうございます】🎁 \n"
        f"📦 注文番号: {order_number}\n"
        f"📦 商品名: {product_name}\n"
        f"📦 商品カラー: {product_color}\n"
        f"📦 合計枚数: {total_qty}枚\n"
        f"📦 {used_positions_text}\n\n"
        f"📦 背ネーム・背番号プリント: {backname_text}\n"
        f"📦 背ネーム・背番号カラー: {backname_color_text}\n"
        f"{calculation_breakdown}\n"
        f"⚠️ 合計金額が3万円未満、または無地ご注文は別途送料を申し受けます。"
    )
    
    webform_prepopulate_data.pop(user_id, None)
    
    if user_id:
        try:
            line_bot_api.push_message(
                to=user_id,
                messages=TextSendMessage(text=reply_msg)
            )
        except Exception as e:
            print(f"[ERROR] push_message failed: {e}")

    return (
        "注文フォームを受け付けました。スプレッドシートに記録しました。<br>"
        f"注文番号: {order_number}<br>"
        f"合計枚数: {total_qty}枚<br>"
        f"合計金額: ¥{total_price:,} / 単価: ¥{unit_price:,}"
    ), 200


# -----------------------
# 動作確認用
# -----------------------
@app.route("/", methods=["GET"])
def health_check():
    return "LINE Bot is running.", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)