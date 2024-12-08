from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, FileMessage
import psycopg2
import os

app = Flask(__name__)

# LINE Worksアクセストークンとシークレット
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# PostgreSQL接続設定
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", 5432)
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def save_to_db(file_name, file_content):
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO files (file_name, file_content) VALUES (%s, %s)",
        (file_name, file_content)
    )
    conn.commit()
    cur.close()
    conn.close()

@app.route("/callback", methods=['POST'])
def callback():
    # X-Line-Signatureヘッダーの検証
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature', 400
    return 'OK', 200

@handler.add(MessageEvent, message=FileMessage)
def handle_file_message(event):
    message_id = event.message.id
    file_name = event.message.file_name
    file_content = line_bot_api.get_message_content(message_id).content
    save_to_db(file_name, file_content)

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    text = event.message.text
    save_to_db("text_message.txt", text.encode("utf-8"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

