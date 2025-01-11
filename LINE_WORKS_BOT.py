import os
import time
import jwt  # PyJWT library
import requests
from flask import Flask, request, jsonify
from google.cloud import vision
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS_PATH

# Constants
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
PRIVATE_KEY = os.getenv("PRIVATE_KEY").replace("\\n", "\n")
ISS = os.getenv("ISS")
TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"
BOT_NO = "6807091"
API_URL = f"https://www.worksapis.com/v1.0/bots/{BOT_NO}/messages"
IMAGE_SAVE_PATH = "/tmp/saved_images"
os.makedirs(IMAGE_SAVE_PATH, exist_ok=True)

# Flask app
app = Flask(__name__)

# JWT creation
def create_jwt():
    now = int(time.time())
    payload = {
        "iss": CLIENT_ID,
        "sub": ISS,
        "iat": now,
        "exp": now + 3600,
        "aud": TOKEN_URL
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")

# Access token retrieval
def get_access_token():
    jwt_token = create_jwt()
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    response.raise_for_status()
    return response.json().get("access_token")

# Message sending
def send_message(account_id, text):
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"{API_URL}/users/{account_id}/messages"
    payload = {"content": {"type": "text", "text": text}}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

# File URL retrieval
def get_file_url(file_id):
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{API_URL}/attachments/{file_id}"
    response = requests.get(url, headers=headers, allow_redirects=False)
    if response.status_code == 302:
        return response.headers.get("Location")
    response.raise_for_status()

# File downloading
def download_file(file_url):
    response = requests.get(file_url, stream=True)
    response.raise_for_status()
    file_path = os.path.join(IMAGE_SAVE_PATH, f"image_{int(time.time())}.jpg")
    with open(file_path, "wb") as f:
        for chunk in response.iter_content(1024):
            f.write(chunk)
    return file_path

# Process image with Vision API
def process_image(image_path):
    client = vision.ImageAnnotatorClient()
    with open(image_path, "rb") as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    if response.error.message:
        raise Exception(f"Vision API Error: {response.error.message}")
    return response.text_annotations[0].description if response.text_annotations else ""

# Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    content = data.get("content", {})
    content_type = content.get("type", "")
    user_id = data.get("source", {}).get("userId")

    if content_type == "text":
        send_message(user_id, content.get("text", ""))
    elif content_type == "image":
        file_id = content.get("fileId")
        if file_id:
            file_url = get_file_url(file_id)
            image_path = download_file(file_url)
            extracted_text = process_image(image_path)
            send_message(user_id, extracted_text or "No text found.")

    return jsonify({"status": "ok"}), 200

# Health check
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "LINE Works Bot is running!"}), 200

if __name__ == "__main__":
    app.run(port=3000, debug=True, host="0.0.0.0")
