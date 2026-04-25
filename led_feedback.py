import pyb
import time

# OpenMV RT1062 onboard RGB LED
led_red   = pyb.LED(1)  # Red
led_green = pyb.LED(2)  # Green
led_blue  = pyb.LED(3)  # Blue (use for Unripe)

def all_off():
    led_red.off()
    led_green.off()
    led_blue.off()

def blink(led, times=3, delay_ms=150):
    """Fast blink for Rotten — draws attention."""
    for _ in range(times):
        led.on()
        time.sleep_ms(delay_ms)
        led.off()
        time.sleep_ms(delay_ms)

def pulse(led, cycles=2, step_ms=20):
    """Slow intensity pulse for Unripe using PWM-style toggling."""
    for _ in range(cycles):
        for i in range(0, 10):
            led.on()
            time.sleep_ms(step_ms)
            led.off()
            time.sleep_ms(step_ms * (10 - i) // 5)

def update_led(label: str):
    """
    Call this with the top prediction label from the classifier.
    e.g. update_led("Rotten_Apple")
    """
    all_off()
    label_lower = label.lower()

    if "rotten" in label_lower:
        blink(led_red, times=3)          # Urgent: red fast blink

    elif "fresh" in label_lower:
        led_green.on()                   # Good: solid green
        time.sleep_ms(800)
        led_green.off()

    elif "unripe" in label_lower:
        pulse(led_blue, cycles=2)        # Wait: blue pulse
