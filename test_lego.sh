#!/bin/bash
# test_lego.sh — Test complet de Blinky

DIR="$(cd "$(dirname "$0")" && pwd)"
B="$DIR/blinky.py"

echo "=== Test de Blinky ==="
echo ""

echo "1. Allumage des yeux..."
python3 "$B" eyes_on
sleep 2

echo "2. Extinction des yeux..."
python3 "$B" eyes_off
sleep 1

echo "3. Clignotement 3 fois..."
python3 "$B" blink 3
sleep 3

echo "4. Mode working (respiration)..."
python3 "$B" working
sleep 5

echo "5. Mode alerte (clignotement continu)..."
python3 "$B" alert
sleep 3

echo "6. LED RGB verte..."
python3 "$B" status 0,255,0
sleep 2

echo "7. Tout eteindre..."
python3 "$B" off
sleep 1

echo ""
echo "=== Test termine ! ==="
echo "Si tu as vu les yeux respirer, clignoter et la LED changer de couleur, Blinky est operationnel."
