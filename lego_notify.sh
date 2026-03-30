#!/bin/bash
# lego_notify.sh — Wrapper macOS/Linux pour blinky.py
# Usage : ./lego_notify.sh <commande> [args]

DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$DIR/blinky.py" "$@"
