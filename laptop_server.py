from flask import Flask, request, jsonify
import pyttsx3
import threading
import time
import requests
from plyer import notification

app = Flask(__name__)

# ---- CONFIGURATION ----
SERVER_PORT    = 5000
ALERT_COOLDOWN = 5       # seconds between alerts
MIN_CONFIDENCE = 0.70    # only alert above 70%
NTFY_TOPIC     = "rotten-fruit-team5"
ENABLE_PHONE   = True
# -----------------------

# All labels from teammate's dataset
# Format: "normalised_label" : (fruit name, urgency, action message)
LABEL_INFO = {
    # Rotten
    "rotten apple":    ("Apple",    "ROTTEN", "Remove it immediately!"),
    "rotten banana":   ("Banana",   "ROTTEN", "Remove it immediately!"),
    "rotten orange":   ("Orange",   "ROTTEN", "Remove it immediately!"),
    "rotten tomato":   ("Tomato",   "ROTTEN", "Remove it immediately!"),
    "rotten cucumber": ("Cucumber", "ROTTEN", "Remove it immediately!"),
    # Unripe
    "unripe apple":    ("Apple",    "UNRIPE", "Not ready to eat yet."),
    "unripe banana":   ("Banana",   "UNRIPE", "Not ready to eat yet."),
    "unripe orange":   ("Orange",   "UNRIPE", "Not ready to eat yet."),
    # Fresh
    "fresh apple":     ("Apple",    "FRESH",  "Good to eat."),
    "fresh banana":    ("Banana",   "FRESH",  "Good to eat."),
    "fresh orange":    ("Orange",   "FRESH",  "Good to eat."),
    "fresh tomato":    ("Tomato",   "FRESH",  "Good to eat."),
    "fresh cucumber":  ("Cucumber", "FRESH",  "Good to eat."),
}

URGENCY_SETTINGS = {
    "ROTTEN": {
        "ntfy_priority": "urgent",
        "speech_prefix": "Warning!",
        "action":        "Please remove it immediately.",
    },
    "UNRIPE": {
        "ntfy_priority": "default",
        "speech_prefix": "Notice.",
        "action":        "This fruit is not ready to eat yet.",
    },
    "FRESH": {
        "ntfy_priority": "low",
        "speech_prefix": "Good news.",
        "action":        "This fruit is fresh and good to eat.",
    },
}

tts_engine = pyttsx3.init()
tts_engine.setProperty("rate", 150)
tts_engine.setProperty("volume", 1.0)
last_alert_time = 0
tts_lock = threading.Lock()


def parse_label(label):
    # Handles both "Rotten Apple" and "rotten_apple" formats
    return label.lower().strip().replace("_", " ")


def speak(message):
    def _speak():
        with tts_lock:
            tts_engine.say(message)
            tts_engine.runAndWait()
    threading.Thread(target=_speak, daemon=True).start()


def desktop_notification(title, message):
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="Fruit Quality Monitor",
            timeout=8,
        )
    except Exception as e:
        print(f"  [Desktop notification failed: {e}]")


def phone_notification(title, message, priority="default"):
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


def fire_alert(label, confidence):
    global last_alert_time

    normalised = parse_label(label)
    info = LABEL_INFO.get(normalised)

    if info is None:
        print(f"  [Unknown label: '{label}'] - skipping")
        return

    fruit_name, urgency, action = info
    settings = URGENCY_SETTINGS[urgency]
    pct = int(confidence * 100)

    # Fresh fruits - just log, no alert needed
    if urgency == "FRESH":
        print(f"  -> Fresh {fruit_name} detected ({pct}%) - no alert needed.")
        return

    if confidence < MIN_CONFIDENCE:
        print(f"  -> Confidence too low ({pct}%) - skipping.")
        return

    # Cooldown check
    now = time.time()
    if now - last_alert_time < ALERT_COOLDOWN:
        print(f"  -> Cooldown active - skipping.")
        return
    last_alert_time = now

    # Build messages dynamically based on actual fruit + urgency
    notif_title = f"{urgency} {fruit_name} Detected"
    notif_body  = f"Confidence: {pct}% - {action}"
    speech_text = (
        f"{settings['speech_prefix']} "
        f"{urgency.capitalize()} {fruit_name} detected "
        f"with {pct} percent confidence. "
        f"{settings['action']}"
    )

    print(f"\n  [{urgency}] {fruit_name} at {pct}%")
    print(f"  Notification: {notif_title}")
    print(f"  Speaking: {speech_text}")

    threading.Thread(target=desktop_notification,
                     args=(notif_title, notif_body), daemon=True).start()
    threading.Thread(target=phone_notification,
                     args=(notif_title, notif_body, settings["ntfy_priority"]),
                     daemon=True).start()
    speak(speech_text)


@app.route("/alert", methods=["POST"])
def receive_alert():
    data = request.get_json(force=True)
    label      = data.get("label", "unknown")
    confidence = float(data.get("confidence", 0))
    print(f"\n[ALERT RECEIVED] label='{label}'  confidence={confidence:.1%}")
    fire_alert(label, confidence)
    return jsonify({"status": "ok"}), 200


@app.route("/test/<path:label>", methods=["GET"])
def test_specific(label):
    """Test any label in browser e.g:
       /test/Rotten Apple
       /test/Unripe Banana
       /test/Fresh Orange
    """
    print(f"\n[TEST] Simulating: {label}")
    fire_alert(label, 0.92)
    return f"Test fired for: {label}", 200


@app.route("/test", methods=["GET"])
def test_default():
    print("\n[TEST] Simulating rotten banana...")
    fire_alert("Rotten Banana", 0.94)
    return "Test sent! Check desktop popup and phone.", 200


@app.route("/labels", methods=["GET"])
def list_labels():
    """Shows all supported labels with test links"""
    html = "<h2>Fruit Quality Monitor - Supported Labels</h2><ul>"
    for label, (fruit, urgency, action) in LABEL_INFO.items():
        display = label.title()
        html += (
            f"<li><b>{display}</b> - {urgency} - {action} "
            f"<a href='/test/{display}'>[Test this]</a></li>"
        )
    html += "</ul><p>Fresh fruits are detected but no alert is triggered for them.</p>"
    return html, 200


@app.route("/", methods=["GET"])
def index():
    import socket as sock
    local_ip = sock.gethostbyname(sock.gethostname())
    return (
        f"<h2>Fruit Quality Monitor - Running</h2>"
        f"<p>IP: <b>{local_ip}</b> | Port: <b>{SERVER_PORT}</b></p>"
        f"<p>"
        f"<a href='/test'>Test Rotten Banana</a> | "
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
    print(f"  Test URL:   http://localhost:{SERVER_PORT}/test")
    print(f"  All labels: http://localhost:{SERVER_PORT}/labels")
    print("=" * 55)
    app.run(host="0.0.0.0", port=SERVER_PORT, debug=False)