#!/usr/bin/env python3
"""
Gestionnaire d'etat multi-terminal pour Blinky.
Chaque session Claude Code ecrit son etat, le coordinateur determine la priorite.

Priorite : alert > working > off
- Si UN terminal est en alert → Blinky clignote
- Si TOUS les alerts sont resolus mais UN terminal travaille → respiration
- Si TOUS les terminaux sont arretes → eteint

Usage (appele par les hooks, recoit le JSON du hook sur stdin) :
    blinky_state.py working
    blinky_state.py alert
    blinky_state.py stop
"""

import sys
import os
import json
import glob
import time
import subprocess

STATE_DIR = "/tmp/blinky_states"
STALE_SECONDS = 1800  # 30 min : nettoyer les sessions mortes

os.makedirs(STATE_DIR, exist_ok=True)


def get_session_id():
    """Lire le session_id depuis le JSON du hook sur stdin."""
    try:
        data = json.load(sys.stdin)
        return data.get("session_id", f"unknown_{os.getpid()}")
    except Exception:
        return f"unknown_{os.getpid()}"


def cleanup_stale():
    """Supprimer les fichiers d'etat trop vieux."""
    now = time.time()
    for f in glob.glob(os.path.join(STATE_DIR, "*")):
        try:
            if now - os.path.getmtime(f) > STALE_SECONDS:
                os.remove(f)
        except Exception:
            pass


def set_state(session_id, action):
    """Ecrire l'etat d'une session."""
    state_file = os.path.join(STATE_DIR, session_id)
    if action == "stop":
        try:
            os.remove(state_file)
        except FileNotFoundError:
            pass
    else:
        with open(state_file, "w") as f:
            f.write(action)


def get_global_state():
    """Determiner l'etat global : alert > working > off."""
    states = []
    for f in glob.glob(os.path.join(STATE_DIR, "*")):
        try:
            with open(f) as fh:
                states.append(fh.read().strip())
        except Exception:
            pass

    if "alert" in states:
        return "alert"
    elif "working" in states:
        return "working"
    else:
        return "off"


def send_to_board(cmd):
    """Envoyer la commande a Blinky."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blinky.py")
    try:
        subprocess.run(
            [sys.executable, script, cmd],
            capture_output=True,
            timeout=5
        )
    except Exception:
        pass


def main():
    if len(sys.argv) < 2:
        print("Usage: blinky_state.py <working|alert|stop>")
        sys.exit(1)

    action = sys.argv[1]
    session_id = get_session_id()

    cleanup_stale()
    set_state(session_id, action)
    cmd = get_global_state()
    send_to_board(cmd)

    print(f"Blinky: session={session_id[:8]} action={action} -> global={cmd}")


if __name__ == "__main__":
    main()
