from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import edge_tts
import asyncio
import os
import uuid
from datetime import datetime

# 创建 requirements.txt：pip freeze > requirements.txt
# Start Command: python app.py

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
    voice = data.get("voice", "XiaoxiaoNeural")
    print(voice)
    if not text:
        return jsonify({"error": "No text provided"}), 400

    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = os.path.join(OUTPUT_DIR, filename)

    asyncio.run(generate_tts(text, filepath, voice))
    url = request.host_url.rstrip('/') + f"/api/ai/audio/{filename}"
    return jsonify({"url": url})


async def generate_tts(text, path, voice):
    communicate = edge_tts.Communicate(
        text,
        voice=voice,
        rate="-20%",
        pitch="-2Hz"
    )
    await communicate.save(path)


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
    port = int(os.environ.get("PORT", 10000))  # Render 默认 10000
    app.run(host="0.0.0.0", port=port)
