#!/usr/bin/env python3
"""
Serveur MCP pour Blinky — permet a Claude Desktop de piloter la mascotte LEGO.

Prerequis :
    pip install "mcp[cli]" pyserial

Usage :
    Ajouter dans claude_desktop_config.json (voir ClaudeBlinky.MD)
"""

import sys

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Erreur : pip install pyserial", file=sys.stderr)
    sys.exit(1)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("blinky")


def find_rp2040():
    """Detecte le port serie du RP2040-Zero."""
    for p in serial.tools.list_ports.comports():
        dev = p.device.lower()
        desc = (p.description or "").lower()
        if "usbmodem" in dev:
            return p.device.replace("tty.", "cu.")
        if "circuitpython" in desc or "rp2040" in desc:
            return p.device
        if "ttyacm" in dev:
            return p.device
    return None


def send_command(cmd: str) -> str:
    """Envoie une commande au RP2040 via le port serie."""
    port = find_rp2040()
    if not port:
        return "Erreur : Blinky non detecte. Verifie le branchement USB."
    try:
        ser = serial.Serial(port, 115200, timeout=1, dsrdtr=False, rtscts=False)
        ser.dtr = False
        ser.write((cmd + "\r\n").encode())
        ser.flush()
        ser.close()
        return f"OK : {cmd} -> {port}"
    except Exception as e:
        return f"Erreur : {e}"


@mcp.tool()
def blinky_working() -> str:
    """Active le mode respiration de Blinky (fondu lent des yeux).
    Utilise ce mode quand tu travailles sur une tache."""
    return send_command("working")


@mcp.tool()
def blinky_alert() -> str:
    """Active le clignotement d'alerte de Blinky (yeux + LED rouge).
    Utilise ce mode quand tu attends une reponse de l'utilisateur."""
    return send_command("alert")


@mcp.tool()
def blinky_off() -> str:
    """Eteint completement Blinky (yeux + LED RGB).
    Utilise ce mode quand tu as termine ton travail."""
    return send_command("off")


@mcp.tool()
def blinky_eyes_on() -> str:
    """Allume les yeux de Blinky en continu."""
    return send_command("eyes_on")


@mcp.tool()
def blinky_eyes_off() -> str:
    """Eteint les yeux de Blinky."""
    return send_command("eyes_off")


@mcp.tool()
def blinky_blink(times: int = 3) -> str:
    """Fait clignoter les yeux de Blinky un certain nombre de fois.

    Args:
        times: nombre de clignotements (defaut 3)
    """
    return send_command(f"blink {times}")


@mcp.tool()
def blinky_status(r: int, g: int, b: int) -> str:
    """Change la couleur de la LED RGB integree de Blinky.

    Args:
        r: composante rouge (0-255)
        g: composante verte (0-255)
        b: composante bleue (0-255)
    """
    return send_command(f"status {r},{g},{b}")


if __name__ == "__main__":
    mcp.run(transport="stdio")
