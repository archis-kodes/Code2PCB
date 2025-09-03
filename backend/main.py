from flask import Flask, request, jsonify, send_from_directory
import os
import shutil
from compile import compile_ino

app = Flask(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.route("/upload", methods=["POST"])
def upload_ino():
    if "file" not in request.files:
        return jsonify({"status": "failed", "error": "No file uploaded"}), 400

    file = request.files["file"]
    filepath = os.path.join(UPLOAD_DIR, file.filename)
    file.save(filepath)

    # Call compile function
    status, chip, logs = compile_ino(filepath)

    result = {
        "status": status,
        "chip": chip,
        "logs": logs,
        "gerber": "/downloads/example_gerber.zip" if status == "success" else None
    }
    return jsonify(result)


# Optional: serve frontend directly from Flask
@app.route("/")
def serve_index():
    return send_from_directory("frontend", "index.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("frontend", path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
