#!/usr/bin/env python3
# FILE: laptop_server.py — Runs on YOUR LAPTOP
# SETUP: pip install flask pyttsx3 plyer requests
# RUN:   python laptop_server.py

from flask import Flask, request, jsonify
import threading
import time
import requests
from plyer import notification
import subprocess

app = Flask(__name__)

# ---- CONFIGURATION ----
SERVER_PORT    = 5000
ALERT_COOLDOWN = 3       # seconds between alerts
MIN_CONFIDENCE = 0.70
NTFY_TOPIC     = "rotten-fruit-team5"
ENABLE_PHONE   = True
# -----------------------

# Freshness labels from freshness.txt
FRESHNESS_INFO = {
    "fresh apple":     ("Apple",    "FRESH",  "Good to eat."),
    "fresh banana":    ("Banana",   "FRESH",  "Good to eat."),
    "fresh cucumber":  ("Cucumber", "FRESH",  "Good to eat."),
    "fresh orange":    ("Orange",   "FRESH",  "Good to eat."),
    "fresh tomato":    ("Tomato",   "FRESH",  "Good to eat."),
    "rotten apple":    ("Apple",    "ROTTEN", "Remove it immediately!"),
    "rotten banana":   ("Banana",   "ROTTEN", "Remove it immediately!"),
    "rotten cucumber": ("Cucumber", "ROTTEN", "Remove it immediately!"),
    "rotten orange":   ("Orange",   "ROTTEN", "Remove it immediately!"),
    "rotten tomato":   ("Tomato",   "ROTTEN", "Remove it immediately!"),
    "unripe apple":    ("Apple",    "UNRIPE", "Not ready to eat yet."),
    "unripe banana":   ("Banana",   "UNRIPE", "Not ready to eat yet."),
    "unripe orange":   ("Orange",   "UNRIPE", "Not ready to eat yet."),
}

URGENCY_SETTINGS = {
    "ROTTEN": {"ntfy_priority": "urgent",  "speech_prefix": "Warning!",    "action": "Please remove it immediately."},
    "UNRIPE": {"ntfy_priority": "default", "speech_prefix": "Notice.",      "action": "This fruit is not ready to eat yet."},
    "FRESH":  {"ntfy_priority": "low",     "speech_prefix": "Good news.",   "action": "This fruit is fresh and good to eat."},
}
speech_lock = threading.Lock()

def speak(message):
    try:
        print(f"  [SPEAKING] {message}")

        safe_message = message.replace("'", "''")

        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Add-Type -AssemblyName System.Speech; "
                f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe_message}')"
            ],
            creationflags=subprocess.CREATE_NO_WINDOW
        )

    except Exception as e:
        print(f"  [TTS failed: {e}]")

def desktop_notif(title, message):
    try:
        notification.notify(title=title, message=message,
                            app_name="Fruit Quality Monitor", timeout=8)
    except Exception as e:
        print(f"  [Desktop notification failed: {e}]")


def phone_notif(title, message, priority="default"):
    if not ENABLE_PHONE:
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": priority},
            timeout=3,
        )
        print(f"  [Phone notification sent]")
    except Exception as e:
        print(f"  [Phone notification failed: {e}]")


def handle_no_fruit(confidence):
    """Notification 1 — No fruit in frame"""
    pct = int(confidence * 100)
    title   = "No Fruit Detected"
    message = f"No fruit in frame ({pct}% confidence)."
    speech  = "No fruit detected in front of the camera."
    print(f"\n  [NO FRUIT] {pct}%")
    threading.Thread(target=desktop_notif, args=(title, message), daemon=True).start()
    threading.Thread(target=phone_notif,   args=(title, message, "low"), daemon=True).start()
    speak(speech)


def handle_fruit_detected(fruit_name, confidence):
    """Notification 1 — What fruit is detected"""
    pct = int(confidence * 100)
    title   = f"Fruit Detected: {fruit_name}"
    message = f"{fruit_name} detected with {pct}% confidence."
    speech  = f"Fruit detected. It is a {fruit_name}, with {pct} percent confidence."
    print(f"\n  [FRUIT DETECTED] {fruit_name} at {pct}%")
    threading.Thread(target=desktop_notif, args=(title, message), daemon=True).start()
    threading.Thread(target=phone_notif,   args=(title, message, "default"), daemon=True).start()
    speak(speech)


def handle_freshness(label, confidence):
    """Notification 2 — Fresh/Rotten/Unripe result"""
    normalised = label.lower().strip().replace("_", " ")
    info = FRESHNESS_INFO.get(normalised)

    if info is None:
        print(f"  [Unknown freshness label: '{label}']")
        return

    fruit_name, urgency, action = info
    settings = URGENCY_SETTINGS[urgency]
    pct = int(confidence * 100)

    title   = f"{urgency} {fruit_name}"
    message = f"Confidence: {pct}% - {action}"
    speech  = (
        f"{settings['speech_prefix']} "
        f"The {fruit_name} is {urgency.lower()}, "
        f"with {pct} percent confidence. "
        f"{settings['action']}"
    )

    print(f"  [FRESHNESS] {urgency} {fruit_name} at {pct}%")
    threading.Thread(target=desktop_notif, args=(title, message), daemon=True).start()
    threading.Thread(target=phone_notif,   args=(title, message, settings["ntfy_priority"]), daemon=True).start()
    speak(speech)


@app.route("/alert", methods=["POST"])
def receive_alert():
    data       = request.get_json(force=True)
    label      = data.get("label", "unknown")
    confidence = float(data.get("confidence", 0))

    print(f"\n[ALERT RECEIVED] label='{label}'  confidence={confidence:.1%}")

    if confidence < MIN_CONFIDENCE:
        print(f"  -> Confidence too low ({confidence:.1%}) - skipping.")
        return jsonify({"status": "ignored", "reason": "low confidence"}), 200

    # --- Notification 1: No fruit ---
    if label == "No_Fruit_Detected":
        handle_no_fruit(confidence)

    # --- Notification 1: Fruit type detected ---
    elif label.startswith("Fruit_Detected:"):
        fruit_name = label.split("Fruit_Detected:")[1]
        handle_fruit_detected(fruit_name, confidence)

    # --- Notification 2: Freshness result ---
    else:
        handle_freshness(label, confidence)

    return jsonify({"status": "ok"}), 200


@app.route("/test", methods=["GET"])
def test_default():
    """Simulates the full two-notification flow for a rotten banana"""
    print("\n[TEST] Simulating rotten banana detection...")
    handle_fruit_detected("Banana", 0.95)
    time.sleep(20)
    handle_freshness("Rotten Banana", 0.91)
    return "Test sent! You should get 2 notifications and 2 voice alerts.", 200


@app.route("/test/<path:label>", methods=["GET"])
def test_label(label):
    """Test any freshness label e.g. /test/Rotten Apple or /test/Unripe Banana"""
    print(f"\n[TEST] Simulating: {label}")
    handle_freshness(label, 0.92)
    return f"Test fired for: {label}", 200


@app.route("/labels", methods=["GET"])
def list_labels():
    html = "<h2>Fruit Quality Monitor - Supported Labels</h2><ul>"
    for label, (fruit, urgency, action) in FRESHNESS_INFO.items():
        display = label.title()
        html += (f"<li><b>{display}</b> - {urgency} - {action} "
                 f"<a href='/test/{display}'>[Test]</a></li>")
    html += "</ul>"
    return html, 200


@app.route("/", methods=["GET"])
def index():
    import socket as sock
    local_ip = sock.gethostbyname(sock.gethostname())
    return (
        f"<h2>Fruit Quality Monitor - Running</h2>"
        f"<p>IP: <b>{local_ip}</b> | Port: <b>{SERVER_PORT}</b></p>"
        f"<p>"
        f"<a href='/test'>Test full flow (Rotten Banana)</a> | "
        f"<a href='/labels'>See all labels</a>"
        f"</p>"
    ), 200


if __name__ == "__main__":
    import socket as sock
    local_ip = sock.gethostbyname(sock.gethostname())
    print("=" * 55)
    print("  Fruit Quality Monitor Server")
    print("=" * 55)
    print(f"  Laptop IP:    {local_ip}")
    print(f"  Server port:  {SERVER_PORT}")
    print(f"  ntfy topic:   {NTFY_TOPIC}")
    print()
    print(f"  Put this in openmv_wifi_sender.py:")
    print(f"    LAPTOP_IP   = \"{local_ip}\"")
    print(f"    LAPTOP_PORT = {SERVER_PORT}")
    print()
    print(f"  Test: http://localhost:{SERVER_PORT}/test")
    print(f"  All labels: http://localhost:{SERVER_PORT}/labels")
    print("=" * 55)
    app.run(host="0.0.0.0", port=SERVER_PORT, debug=False)
