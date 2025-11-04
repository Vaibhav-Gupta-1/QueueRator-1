# app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
import uuid, qrcode, io, json, os, threading, time
from pathlib import Path

app = Flask(__name__, static_folder="static", template_folder="templates")

DATA_FILE = Path("queues.json")
LOCK = threading.Lock()

def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}

def save_data(data):
    with LOCK:
        DATA_FILE.write_text(json.dumps(data))

# Initialize storage
if not DATA_FILE.exists():
    save_data({})

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/create_queue", methods=["POST"])
def create_queue():
    data = load_data()
    queue_id = uuid.uuid4().hex[:8]
    data[queue_id] = {
        "created": time.time(),
        "users": []  # list of strings
    }
    save_data(data)
    queue_url = url_for("queue_view", qid=queue_id, _external=True)
    return jsonify({"queue_id": queue_id, "queue_url": queue_url})

@app.route("/queue/<qid>")
def queue_view(qid):
    data = load_data()
    if qid not in data:
        return "Queue not found", 404
    return render_template("queue.html", qid=qid)

@app.route("/queue/<qid>/qr")
def queue_qr(qid):

    data = load_data()
    if qid not in data:
        return "Queue not found", 404
    # queue_url = request.host_url.rstrip("/") + url_for("queue_page", qid=qid)
    queue_url = url_for("queue_view", qid=qid, _external=True)
    img = qrcode.make(queue_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/api/queue/<qid>/data")
def queue_data(qid):
    data = load_data()
    if qid not in data:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"users": data[qid]["users"]})

@app.route("/api/queue/<qid>/join", methods=["POST"])
def queue_join(qid):
    payload = request.json or {}
    name = payload.get("name") or f"User_{str(uuid.uuid4())[:6]}"
    data = load_data()
    if qid not in data:
        return jsonify({"error": "not_found"}), 404
    # push at end
    data[qid]["users"].append(name)
    save_data(data)
    # return the name assigned and position
    pos = len(data[qid]["users"])
    return jsonify({"name": name, "position": pos})

@app.route("/api/queue/<qid>/add", methods=["POST"])
def queue_add(qid):
    payload = request.json or {}
    name = payload.get("name")
    if not name:
        return jsonify({"error": "missing_name"}), 400
    data = load_data()
    if qid not in data:
        return jsonify({"error": "not_found"}), 404
    data[qid]["users"].append(name)
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/queue/<qid>/next", methods=["POST"])
def queue_next(qid):
    data = load_data()
    if qid not in data:
        return jsonify({"error": "not_found"}), 404
    if data[qid]["users"]:
        removed = data[qid]["users"].pop(0)
        save_data(data)
        return jsonify({"removed": removed})
    return jsonify({"removed": None})

@app.route("/api/queue/<qid>/clear", methods=["POST"])
def queue_clear(qid):
    data = load_data()
    if qid not in data:
        return jsonify({"error": "not_found"}), 404
    data[qid]["users"] = []
    save_data(data)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
