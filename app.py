# app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
import uuid, qrcode, io, json, os, threading, time
from pathlib import Path
import time


BASE_DIR = Path(__file__).parent

app = Flask(
    __name__, 
    static_folder=BASE_DIR / "static", 
    template_folder=BASE_DIR / "templates"
)
DATA_FILE = BASE_DIR / "queues.json" # --- CHANGE 3: Update DATA_FILE path ---
LOCK = threading.Lock()

def load_data():
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text())
        if "rules" in data:
            del data["rules"]
        # Safety: Initialize new fields for existing queues if they are missing
        for qid in data:
            data[qid].setdefault("service_history", [])
            data[qid].setdefault("last_call_time", time.time()) # Set a safe default
        return data
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
        "users": [],
        "service_history": [],      # <-- NEW: List of recent service durations
        "last_call_time": time.time() # <-- NEW: Timestamp of the last 'Call Next'
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

# app.py

@app.route("/api/queue/<qid>/data")
def queue_data(qid):
    data = load_data()
    if qid not in data:
        return jsonify({"error": "not_found"}), 404
    
    queue_data = data[qid]
    users = queue_data["users"]
    service_history = queue_data.get("service_history", [])
    
    # --- EWT Calculation ---
    if service_history:
        # Calculate Average Service Time from history
        avg_service_time = sum(service_history) / len(service_history)
    else:
        # Default to 5 minutes (300 seconds) if no history is available
        avg_service_time = 10
        
    # EWT = (Number of people ahead) * (Average time per person)
    ewt_seconds = len(users) * avg_service_time
    
    # --- End EWT Calculation ---
    
    return jsonify({
        "users": users, 
        "ewt": ewt_seconds # NEW: EWT in seconds
    })

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

# app.py

@app.route("/api/queue/<qid>/next", methods=["POST"])
def queue_next(qid):
    data = load_data()
    if qid not in data:
        return jsonify({"error": "not_found"}), 404
    
    current_time = time.time()
    queue_data = data[qid]
    
    if queue_data["users"]:
        
        # 1. Calculate duration since last call
        last_call = queue_data.get("last_call_time", current_time)
        service_duration = current_time - last_call
        
        # 2. Add duration to history (keeping only the last 3)
        history = queue_data.get("service_history", [])
        history.append(service_duration)
        queue_data["service_history"] = history[-3:] # Keep only the last 3 times
        
        removed = queue_data["users"].pop(0)
        
        # 3. Update the last call time
        queue_data["last_call_time"] = current_time 
        save_data(data)
        return jsonify({"removed": removed})
    
    # Update time even if the queue was empty when called
    queue_data["last_call_time"] = current_time 
    save_data(data)
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
