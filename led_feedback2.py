import time
from machine import LED

led_red   = LED("LED_RED")
led_green = LED("LED_GREEN")
led_blue  = LED("LED_BLUE")

def all_off():
    led_red.off()
    led_green.off()
    led_blue.off()     
    
print("Testing RED - Rotten")
led_red.on()
time.sleep_ms(1000)
led_red.off()
time.sleep_ms(500)

print("Testing GREEN - Fresh")
led_green.on()
time.sleep_ms(1000)
led_green.off()
time.sleep_ms(500)

print("Testing BLUE - Unripe")
led_blue.on()
time.sleep_ms(1000)
led_blue.off()
time.sleep_ms(500)

print("ALL DONE - LEDs working!")
