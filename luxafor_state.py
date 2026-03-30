#!/usr/bin/env python3
"""
Gestionnaire d'etat multi-terminal pour Luxafor.
Replique de blinky_state.py adaptee au Luxafor Flag USB.

Priorite : alert > working > off
- Si UN terminal est en alert → Luxafor strobe rouge
- Si TOUS les alerts sont resolus mais UN terminal travaille → Luxafor wave bleue
- Si TOUS les terminaux sont arretes → eteint

Usage (appele par les hooks, recoit le JSON du hook sur stdin) :
    luxafor_state.py working
    luxafor_state.py alert
    luxafor_state.py stop
"""

import sys
import os
import json
import glob
import time

from luxafor import find_luxafor, process as luxafor_process

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
        # Si le session_id n'a pas ete transmis (fallback unknown_*),
        # nettoyer tous les fichiers d'etat
        if session_id.startswith("unknown_"):
            for f in glob.glob(os.path.join(STATE_DIR, "*")):
                try:
                    os.remove(f)
                except Exception:
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
        return "done"


def send_to_device(cmd):
    """Envoyer la commande au Luxafor (appel direct, sans sous-processus)."""
    try:
        luxafor_process(cmd)
    except Exception:
        pass


def main():
    if len(sys.argv) < 2:
        print("Usage: luxafor_state.py <working|alert|stop>")
        sys.exit(1)

    action = sys.argv[1]
    session_id = get_session_id()

    cleanup_stale()
    set_state(session_id, action)
    cmd = get_global_state()
    send_to_device(cmd)

    print(f"Blinky: session={session_id[:8]} action={action} -> global={cmd}")


if __name__ == "__main__":
    main()
