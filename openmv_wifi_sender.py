# ============================================================
# FILE: openmv_wifi_sender.py
# Runs ON the OpenMV RT1062 board
# ============================================================

import network
import usocket as socket
import ujson
import utime

# ---- CONFIGURATION — edit these ----
WIFI_SSID     = "YourHotspotName"     # Your hotspot name
WIFI_PASSWORD = "YourPassword"        # Your hotspot password
LAPTOP_IP     = "192.168.x.x"         # Your laptop IP when connected to hotspot
LAPTOP_PORT   = 5000
# ------------------------------------

# All labels exactly as your teammate's Edge Impulse model outputs them
FRUIT_LABELS = [
    "Fresh Apple",    "Rotten Apple",    "Unripe Apple",
    "Fresh Banana",   "Rotten Banana",   "Unripe Banana",
    "Fresh Orange",   "Rotten Orange",   "Unripe Orange",
    "Fresh Tomato",   "Rotten Tomato",
    "Fresh Cucumber", "Rotten Cucumber",
]

wlan = network.WLAN(network.STA_IF)

def connect_wifi():
    """Connect to WiFi. Call once at startup."""
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi:", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            utime.sleep(1)
            timeout -= 1
    if wlan.isconnected():
        print("WiFi connected:", wlan.ifconfig()[0])
        return True
    else:
        print("WiFi connection failed")
        return False

def send_alert(label, confidence):
    """
    Send detection result to the laptop server.
    Works for ALL labels — fresh, rotten, and unripe.
    The laptop server decides what notification to show.

    Args:
        label      (str):   exactly as Edge Impulse outputs it
                            e.g. "Rotten Apple", "Unripe Banana", "Fresh Orange"
        confidence (float): 0.0 to 1.0
    """
    if not wlan.isconnected():
        print("Not connected to WiFi, skipping alert")
        return

    payload = ujson.dumps({
        "label":      label,
        "confidence": round(confidence, 3),
        "timestamp":  utime.time()
    })

    try:
        addr = socket.getaddrinfo(LAPTOP_IP, LAPTOP_PORT)[0][-1]
        s = socket.socket()
        s.settimeout(3)
        s.connect(addr)

        request = (
            "POST /alert HTTP/1.1\r\n"
            "Host: {}:{}\r\n".format(LAPTOP_IP, LAPTOP_PORT) +
            "Content-Type: application/json\r\n"
            "Content-Length: {}\r\n".format(len(payload)) +
            "Connection: close\r\n"
            "\r\n" +
            payload
        )
        s.sendall(request.encode())
        response = s.recv(128)
        s.close()
        print("Alert sent:", label, confidence, "| Server:", response[:12])

    except Exception as e:
        print("Alert failed:", e)

# ============================================================
# HOW TO INTEGRATE with teammate's object detection code
# ============================================================
#
# Step 1 — At the TOP of their main.py add:
#   from openmv_wifi_sender import connect_wifi, send_alert
#   connect_wifi()
#
# Step 2 — Inside their detection LOOP add:
#
#   LAST_ALERT_TIME = 0
#   ALERT_COOLDOWN  = 5   # seconds between alerts
#
#   label      = top_prediction["label"]       # e.g. "Rotten Apple"
#   confidence = top_prediction["value"]       # e.g. 0.94
#
#   now = utime.time()
#   if confidence > 0.70 and now - LAST_ALERT_TIME > ALERT_COOLDOWN:
#       send_alert(label, confidence)
#       LAST_ALERT_TIME = now
#
# That's it — send ALL labels (fresh, rotten, unripe).
# The laptop server handles what notification to show for each.
# ============================================================