"""
Firmware CircuitPython pour RP2040-Zero — Blinky
LED RGB integree (NeoPixel sur GP16, format RGB).

Commandes serie :
  alert    — clignotement LED rouge
  working  — respiration LED bleue
  status <r,g,b> — couleur LED RGB
  off      — tout eteindre
"""

import board
import digitalio
import neopixel_write
import sys
import time
import supervisor

# --- LED RGB integree (NeoPixel sur GP16, format RGB) ---
rgb_pin = digitalio.DigitalInOut(board.GP16)
rgb_pin.direction = digitalio.Direction.OUTPUT

# --- Table de respiration (triangle, 100 pas) ---
MAX_RGB = 40
BT = []
for i in range(50):
    BT.append(i * MAX_RGB // 50)
for i in range(50, 0, -1):
    BT.append(i * MAX_RGB // 50)
BT_LEN = len(BT)

# --- Etat ---
mode = None
step = 0
last_t = time.monotonic()
buf = ""


def set_rgb(r, g, b):
    neopixel_write.neopixel_write(rgb_pin, bytearray([r, g, b]))


def process(cmd):
    global mode, step, last_t
    if cmd == "alert":
        mode = "alert"
        step = 0
        last_t = time.monotonic()
    elif cmd == "working":
        mode = "working"
        step = 0
        last_t = time.monotonic()
    elif cmd.startswith("status"):
        mode = None
        parts = cmd.split()
        if len(parts) > 1:
            r, g, b = parts[1].split(",")
            set_rgb(int(r), int(g), int(b))
    elif cmd == "off":
        mode = None
        set_rgb(0, 0, 0)


# --- Demarrage : flash vert ---
set_rgb(0, 255, 0)
time.sleep(0.5)
set_rgb(0, 0, 0)

while True:
    while supervisor.runtime.serial_bytes_available:
        ch = sys.stdin.read(1)
        if ch in ("\n", "\r"):
            cmd = buf.strip()
            buf = ""
            if cmd:
                process(cmd)
        else:
            buf += ch

    now = time.monotonic()

    if mode == "working" and now - last_t >= 0.03:
        last_t = now
        b = BT[step]
        set_rgb(0, 0, b)
        step = (step + 1) % BT_LEN

    elif mode == "alert" and now - last_t >= 0.15:
        last_t = now
        on = step % 2 == 0
        set_rgb(255 if on else 0, 0, 0)
        step += 1

    time.sleep(0.01)
