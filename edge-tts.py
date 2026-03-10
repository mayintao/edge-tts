from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import uuid
import requests
from datetime import datetime

import os, json, base64, uuid

from io import BytesIO
from PIL import Image


UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
RESULT_FOLDER = 'results'
os.makedirs(RESULT_FOLDER, exist_ok=True)

app = Flask(__name__)
CORS(app)

OUTPUT_DIR = "audio"
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route("/api/ai/tts", methods=["POST", "OPTIONS"])
def tts():
    if request.method == "OPTIONS":
        return '', 200  # CORS预检返回200即可

    data = request.json
    text = data.get("text", "")
    lang = data.get("lang", "zh-CN")  # 支持多语言
    if not text:
        return jsonify({"error": "No text provided"}), 400

    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(OUTPUT_DIR, filename)

    success = generate_tts_google(text, lang, filepath)
    if not success:
        return jsonify({"error": "Failed to generate TTS"}), 500

    url = request.host_url.rstrip('/') + f"/api/ai/audio/{filename}"
    return jsonify({"url": url})

def generate_tts_google(text, lang, path):
    """
    使用 Google Translate TTS 接口生成 mp3
    """
    base_url = "https://translate.google.com/translate_tts"
    params = {
        "ie": "UTF-8",
        "q": text,
        "tl": lang,
        "client": "tw-ob"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    }

    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            with open(path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print("Google TTS failed:", response.status_code)
            return False
    except Exception as e:
        print("Google TTS exception:", e)
        return False

@app.route("/api/ai/audio/<filename>")
def serve_audio(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path):
        return send_file(path, mimetype="audio/mpeg")
    else:
        return "File not found", 404

@app.route("/api/ai/clear-history", methods=["GET"])
def clear_history():
    for f in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, f)
        if os.path.isfile(path):
            os.remove(path)
    return jsonify({"message": "History cleared"})

@app.route("/api/ai/history", methods=["GET"])
def get_history():
    files = []
    for f in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, f)
        if os.path.isfile(path) and f.endswith(".mp3"):
            files.append({
                "filename": f,
                "url": request.host_url.rstrip('/') + f"/api/ai/audio/{f}",
                "timestamp": datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
            })
    files.sort(key=lambda x: x["timestamp"], reverse=True)  # 最近的在前
    return jsonify(files)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
