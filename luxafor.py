#!/usr/bin/env python3
"""
luxafor.py — Envoie des commandes au Luxafor Flag USB.
Cross-platform : macOS, Linux, Windows.

Prerequis : pip install hidapi

Usage :
    python3 luxafor.py working
    python3 luxafor.py alert
    python3 luxafor.py status 0,255,0
    python3 luxafor.py off
"""

import sys

try:
    import hid
except ImportError:
    print("Erreur : hidapi manquant. Installe-le avec : pip install hidapi")
    sys.exit(1)

VENDOR_ID = 0x04D8
PRODUCT_ID = 0xF372


def find_luxafor():
    """Detecte le Luxafor Flag USB."""
    for dev in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        return dev
    return None


def send(cmd_bytes):
    """Envoie une commande HID au Luxafor."""
    device = hid.device()
    device.open(VENDOR_ID, PRODUCT_ID)
    # 9 octets : report ID (0) + 8 octets de donnees
    padded = [0] + cmd_bytes + [0] * (8 - len(cmd_bytes))
    device.write(padded)
    device.close()


def cmd_static(r, g, b):
    """Couleur statique sur toutes les LEDs."""
    return [1, 0xFF, r, g, b, 0, 0, 0]


def cmd_fade(r, g, b, speed=20):
    """Fondu vers une couleur."""
    return [2, 0xFF, r, g, b, speed, 0, 0]


def cmd_strobe(r, g, b, speed=10, repeat=0):
    """Clignotement (repeat=0 → infini)."""
    return [3, 0xFF, r, g, b, speed, 0, repeat]


def cmd_wave(wave_type, r, g, b, speed=10, repeat=0):
    """Animation wave 1-5 (repeat=0 → infini)."""
    return [4, wave_type, r, g, b, 0, repeat, speed]


def process(cmd):
    """Traite une commande texte et l'envoie au Luxafor."""
    if cmd == "working":
        # Bleu pulse (battement de coeur) — Claude travaille
        send(cmd_strobe(0, 0, 255, speed=20, repeat=0))
    elif cmd == "alert":
        # Rouge clignotant rapide — attention requise
        send(cmd_strobe(255, 0, 0, speed=5, repeat=0))
    elif cmd.startswith("status"):
        parts = cmd.split()
        if len(parts) > 1:
            r, g, b = parts[1].split(",")
            send(cmd_static(int(r), int(g), int(b)))
    elif cmd == "done":
        # Annuler le strobe en cours, puis vert statique — prêt
        send(cmd_strobe(0, 0, 0, speed=1, repeat=1))
        send(cmd_static(0, 1, 0))
    elif cmd == "off":
        send(cmd_strobe(0, 0, 0, speed=1, repeat=1))


def main():
    if len(sys.argv) < 2:
        print("Usage : python3 luxafor.py <commande> [args]")
        print("Commandes : working, alert, status <r,g,b>, off")
        sys.exit(1)

    cmd = " ".join(sys.argv[1:])
    info = find_luxafor()

    if not info:
        print("Erreur : Luxafor non detecte. Verifie le branchement USB.")
        sys.exit(1)

    try:
        process(cmd)
        print(f"Envoye : {cmd} -> Luxafor")
    except Exception as e:
        print(f"Erreur : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
