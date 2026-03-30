#!/usr/bin/env python3
"""
blinky.py — Envoie des commandes au bonhomme Lego RP2040-Zero.
Cross-platform : macOS, Linux, Windows.

Prerequis : pip install pyserial

Usage :
    python3 blinky.py alert
    python3 blinky.py working
    python3 blinky.py blink 5
    python3 blinky.py eyes_on
    python3 blinky.py eyes_off
    python3 blinky.py status 0,255,0
    python3 blinky.py off
"""

import sys

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Erreur : pyserial manquant. Installe-le avec : pip install pyserial")
    sys.exit(1)


def find_rp2040():
    """Detecte le port serie du RP2040-Zero."""
    for p in serial.tools.list_ports.comports():
        dev = p.device.lower()
        desc = (p.description or "").lower()
        # macOS : /dev/cu.usbmodem*
        if "usbmodem" in dev:
            return p.device.replace("tty.", "cu.")
        # Windows : description contient "CircuitPython" ou "RP2040"
        if "circuitpython" in desc or "rp2040" in desc:
            return p.device
        # Linux : /dev/ttyACM*
        if "ttyacm" in dev:
            return p.device
    return None


def send(port, cmd):
    """Envoie une commande au RP2040 via le port serie."""
    ser = serial.Serial(port, 115200, timeout=1, dsrdtr=False, rtscts=False)
    ser.dtr = False
    ser.write((cmd + "\r\n").encode())
    ser.flush()
    ser.close()


def main():
    if len(sys.argv) < 2:
        print("Usage : python3 blinky.py <commande> [args]")
        print("Commandes : eyes_on, eyes_off, blink <n>, alert, working, status <r,g,b>, off")
        sys.exit(1)

    cmd = " ".join(sys.argv[1:])
    port = find_rp2040()

    if not port:
        print("Erreur : RP2040-Zero non detecte. Verifie le branchement USB.")
        sys.exit(1)

    try:
        send(port, cmd)
        print(f"Envoye : {cmd} -> {port}")
    except Exception as e:
        print(f"Erreur : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
