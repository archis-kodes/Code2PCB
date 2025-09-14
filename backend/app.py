### TEMPORARY FILE
# Arduino to compile
# Compile to OPENAI Agent
# OPENAI Agent to Terminal

## OPENAI Agent to pcbgen
## pcbgen to output

from flask import Flask, request, jsonify, send_from_directory
import os
import shutil
from compile import compile_ino
from openai_agent import analyze_code  # your dynamic agent
# Removed pcbgen import since it doesn't exist

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

    # Call compile function dynamically
    status, chip, logs = compile_ino(filepath)

    pcb_data = None
    if status == "success":
        # Call OpenAI agent dynamically with uploaded file + chip
        pcb_data = analyze_code(filepath, chip)
        
        # Print the OpenAI agent output to terminal
        print("\n" + "="*50)
        print("OPENAI AGENT OUTPUT:")
        print("="*50)
        print(pcb_data)
        print("="*50 + "\n")

    result = {
        "status": status,
        "chip": chip,
        "logs": logs,
        "pcb_data": pcb_data,
        "gerber": None  # Set to None since we're not generating PCBs
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
