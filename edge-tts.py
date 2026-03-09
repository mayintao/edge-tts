from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import uuid
import requests
from datetime import datetime

from paddleocr import PaddleOCR
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


####################OCR文字识别####################
# 初始化 OCR（支持中英文日文）
ocr = PaddleOCR(
    use_textline_orientation=True,
    lang="ch",
    show_log=False,
    use_gpu=False
)

@app.route("/ai/api_ocr_image", methods=["POST"])
def api_ocr_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400
    file = request.files['image']
    uid = uuid.uuid4().hex
    filename = f"{uid}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    # 当前时间
    print("start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    result = ocr_image(filepath)
    # 当前时间
    print("finish time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    # 清理上传图
    if os.path.exists(filepath):
        os.remove(filepath)
    return result

def ocr_image(image_path):
    uid = uuid.uuid4().hex
    # 运行 OCR
    result = ocr.predict(input=image_path)
    first_image_result = result[0]  # 👈 获取第一张图的所有识别块
    texts = first_image_result['rec_texts']
    for i, text in enumerate(texts):
        print(f"{i + 1}. {text}")

    results_text = []
    image_base64_list = []

    # 保存标注图
    result_filename = f"{uid}.jpg"
    result_path = os.path.join(RESULT_FOLDER, result_filename)
    first_image_result.save_to_img(result_path)

    # 转 base64 图像
    image_base64 = image_to_base64(result_path)
    image_base64_list.append(image_base64)

    # 保存 JSON 并读入文字内容
    json_path = os.path.join(RESULT_FOLDER, f"{uid}.json")
    first_image_result.save_to_json(json_path)

    with open(json_path, 'r', encoding='utf-8') as f:
        json_str = f.read()
        results_text.append(json.loads(json_str))

    response = {
        'status': 'success',
        'images': image_base64_list,  # 多图 base64 数组
        'text': results_text  # 对应图的识别内容
    }

    # 清理生成的标注图和json
    if os.path.exists(result_path):
        os.remove(result_path)
    if os.path.exists(json_path):
        os.remove(json_path)

    return jsonify(response)

def image_to_base64(img_path):
    img = Image.open(img_path).convert('RGB')
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
