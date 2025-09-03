import os
import re
import subprocess
import tempfile
import shutil

# Priority list of common boards (cheap & widely used) by FQBN
PRIORITY_BOARDS = [
    # Arduino AVR family
    "arduino:avr:uno",        # Most popular & cheap
    "arduino:avr:nano",       # Nano (compact, cheap)
    "arduino:avr:mega",       # Mega 2560 (bigger)
    "arduino:avr:micro",      # Pro Micro (ATmega32U4)
    "arduino:avr:leonardo",   # Leonardo (ATmega32U4)

    # ESP32 family (common dev boards)
    "esp32:esp32:esp32",              # Generic ESP32
    "esp32:esp32:esp32doit-devkit-v1",# DoIt DevKit V1
    "esp32:esp32:esp32cam",           # ESP32-CAM
    "esp32:esp32:node32s",            # NodeMCU-32S
]

def install_missing_libs(ino_path):
    """Parse .ino file and auto-install missing libraries using arduino-cli."""
    with open(ino_path, "r") as f:
        code = f.read()

    includes = re.findall(r'#include\s*<([^>]+)>', code)
    for lib in includes:
        print(f"🔍 Checking library: {lib}")
        result = subprocess.run(
            ["arduino-cli", "lib", "search", lib],
            capture_output=True,
            text=True
        )
        if "Name:" in result.stdout:
            lib_name = None
            for line in result.stdout.splitlines():
                if line.startswith("Name:"):
                    lib_name = line.replace("Name:", "").strip()
                    break
            if lib_name:
                print(f"📦 Installing {lib_name} ...")
                subprocess.run(["arduino-cli", "lib", "install", lib_name])
        else:
            print(f"⚠️ No match found for {lib}")

def get_installed_boards():
    """Get all installed board FQBNs dynamically using arduino-cli."""
    try:
        result = subprocess.run(
            ["arduino-cli", "board", "listall"],
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.splitlines()
        fqbn_list = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and ":" in parts[-1]:
                fqbn_list.append(parts[-1])
        return fqbn_list
    except Exception as e:
        return []

def compile_ino(ino_file):
    """Prepare Arduino structure, auto-install libs, and try compiling with priority first."""
    sketch_name = os.path.splitext(os.path.basename(ino_file))[0]

    # make temporary sketch folder
    temp_dir = tempfile.mkdtemp()
    sketch_dir = os.path.join(temp_dir, sketch_name)
    os.makedirs(sketch_dir, exist_ok=True)

    # copy ino file into sketch folder with correct name
    sketch_path = os.path.join(sketch_dir, f"{sketch_name}.ino")
    shutil.copy(ino_file, sketch_path)

    # auto-install required libraries
    install_missing_libs(sketch_path)

    boards = get_installed_boards()
    if not boards:
        return "failed", None, "❌ No boards installed."

    # Step 1: Try priority boards first
    for fqbn in PRIORITY_BOARDS:
        if fqbn in boards:
            print(f"⚡ Trying priority board: {fqbn}")
            cmd = ["arduino-cli", "compile", "--fqbn", fqbn, sketch_dir]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                output = result.stdout + "\n" + result.stderr
                shutil.rmtree(temp_dir)
                return "success", fqbn, output

    # Step 2: Try all remaining installed boards
    for fqbn in boards:
        if fqbn not in PRIORITY_BOARDS:  # skip already tried
            print(f"⚡ Trying fallback board: {fqbn}")
            cmd = ["arduino-cli", "compile", "--fqbn", fqbn, sketch_dir]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                output = result.stdout + "\n" + result.stderr
                shutil.rmtree(temp_dir)
                return "success", fqbn, output

    # all failed
    output = result.stdout + "\n" + result.stderr
    shutil.rmtree(temp_dir)
    return "failed", None, "❌ Compilation failed for all boards.\n" + output
