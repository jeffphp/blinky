# Blinky — Guide d'installation pour Claude Code

Blinky est une mascotte LEGO avec une LED NeoPixel integree pilotee par un RP2040-Zero. La LED respire en bleu quand Claude travaille, clignote en rouge quand Claude attend une reponse, et s'eteint quand Claude a fini. Plusieurs terminaux Claude Code sont coordonnes via `blinky_state.py`.

## Materiel

- 1x Waveshare RP2040-Zero (avec LED RGB WS2812B / NeoPixel integree sur GP16)
- Un cable USB-C data (pas charge-only)

Aucun composant externe requis. Le setup utilise uniquement la LED NeoPixel integree a la carte.

## Prerequis logiciel

```bash
pip install pyserial
```

## Etape 1 — Telecharger CircuitPython

macOS / Linux :
```bash
curl -L -o ~/Downloads/circuitpython-rp2040-zero.uf2 \
  "https://downloads.circuitpython.org/bin/waveshare_rp2040_zero/fr/adafruit-circuitpython-waveshare_rp2040_zero-fr-10.1.4.uf2"
```

Windows (PowerShell) :
```powershell
Invoke-WebRequest -Uri "https://downloads.circuitpython.org/bin/waveshare_rp2040_zero/fr/adafruit-circuitpython-waveshare_rp2040_zero-fr-10.1.4.uf2" -OutFile "$env:USERPROFILE\Downloads\circuitpython-rp2040-zero.uf2"
```

## Etape 2 — Passer la carte en mode bootloader

Action physique :
1. Debranche le RP2040-Zero du cable USB-C
2. Maintiens le bouton BOOT enfonce
3. Rebranche le cable USB-C tout en maintenant BOOT
4. Relache BOOT

Verifie :
```bash
# macOS
ls /Volumes/RPI-RP2
# Windows (PowerShell)
Get-Volume | Where-Object { $_.FileSystemLabel -eq 'RPI-RP2' }
```

## Etape 3 — Flasher CircuitPython

```bash
# macOS
cp ~/Downloads/circuitpython-rp2040-zero.uf2 /Volumes/RPI-RP2/
```
```powershell
# Windows — remplacer D: par la lettre du volume RPI-RP2
Copy-Item "$env:USERPROFILE\Downloads\circuitpython-rp2040-zero.uf2" "D:\"
```

Attends le redemarrage, puis verifie que le volume CIRCUITPY apparait.

## Etape 4 — Copier le firmware

```bash
# macOS
cp code.py /Volumes/CIRCUITPY/code.py
```
```powershell
# Windows — remplacer E: par la lettre du volume CIRCUITPY
Copy-Item "code.py" "E:\code.py"
```

La carte redemarre. Un flash vert confirme que le firmware tourne.

Le firmware utilise uniquement la LED NeoPixel integree sur GP16 (format **RGB** : `bytearray([r, g, b])`). Il lit les commandes serie byte par byte avec `sys.stdin.read(1)` pour ne pas bloquer la boucle d'animation. Mode working = respiration bleue (triangle wave, MAX_RGB=40). Mode alert = clignotement rouge a 0.15s.

## Etape 5 — Tester

```bash
python3 blinky.py working         # respiration bleue
python3 blinky.py alert           # clignotement rouge
python3 blinky.py status 0,255,0  # LED verte
python3 blinky.py off             # tout eteindre
```

Sur Windows, utiliser `python` au lieu de `python3`.

Sur macOS/Linux, `./lego_notify.sh <commande>` est un wrapper equivalent.
Sur Windows, `lego_notify.bat <commande>` est un wrapper equivalent.

`blinky.py` est le script cross-platform principal. Les wrappers `lego_notify.sh` et `lego_notify.bat` ne font qu'appeler `blinky.py`.

## Commandes

| Commande | Effet |
|---|---|
| `python3 blinky.py working` | Respiration bleue (NeoPixel) |
| `python3 blinky.py alert` | Clignotement rouge (NeoPixel) |
| `python3 blinky.py status 0,255,0` | LED RGB verte |
| `python3 blinky.py off` | Tout eteindre |

## Integration Claude Code (hooks multi-terminal)

Les hooks utilisent `blinky_state.py` pour supporter plusieurs terminaux Claude Code simultanes. Chaque session ecrit son etat dans `/tmp/blinky_states/<session_id>`, et le coordinateur determine la commande a envoyer selon la priorite : alert > working > off.

Comportement multi-terminal :
- **UN terminal en alert** → Blinky clignote rouge
- **TOUS les alerts resolus + UN terminal working** → Blinky respire bleu
- **TOUS les terminaux arretes** → Blinky eteint
- Sessions inactives nettoyees apres 30 min

Ajouter dans `~/.claude/settings.json` (macOS/Linux) ou `%USERPROFILE%\.claude\settings.json` (Windows) :

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 BLINKY_PATH/blinky_state.py working",
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "AskUserQuestion",
        "hooks": [
          {
            "type": "command",
            "command": "python3 BLINKY_PATH/blinky_state.py alert",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 BLINKY_PATH/blinky_state.py working",
            "timeout": 5
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 BLINKY_PATH/blinky_state.py alert",
            "timeout": 5
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 BLINKY_PATH/blinky_state.py stop",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Remplacer `BLINKY_PATH` par le chemin absolu vers le dossier blinky. Sur Windows, utiliser `python` au lieu de `python3` et des backslashes.

Comportement :
- **Message envoye** → respiration bleue (NeoPixel)
- **Question de Claude** (`PreToolUse` / `AskUserQuestion`) → clignotement rouge (NeoPixel)
- **Demande de permission** (`PermissionRequest`) → clignotement rouge (NeoPixel)
- **Question repondue** (`PostToolUse` / `AskUserQuestion`) → retour en respiration bleue
- **Claude a fini** (`Stop`) → tout s'eteint

## Integration Claude Desktop (MCP)

Pour utiliser Blinky avec Claude Desktop (ou Cowork/Dispatch), un serveur MCP est disponible via `blinky_mcp.py`.

### Prerequis MCP

- `uv` (gestionnaire de paquets Python)
- Python 3.12+

### Configuration

Editer le fichier de configuration Claude Desktop :

- macOS : `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows : `%APPDATA%\Claude\claude_desktop_config.json`

Ajouter :

```json
{
  "mcpServers": {
    "blinky": {
      "command": "uv",
      "args": ["--directory", "BLINKY_PATH", "run", "blinky_mcp.py"]
    }
  }
}
```

Remplacer `BLINKY_PATH` par le chemin absolu vers le dossier blinky.

Outils MCP disponibles : `blinky_working`, `blinky_alert`, `blinky_off`, `blinky_blink`, `blinky_status`, `blinky_eyes_on`, `blinky_eyes_off`.

### Utilisation avec Cowork/Dispatch

Ajouter dans le prompt : "Appelle blinky_working quand tu travailles, blinky_alert quand tu attends une reponse, blinky_off quand tu as fini"

## Depannage

**Le volume RPI-RP2 n'apparait pas :**
Maintiens bien BOOT avant de brancher. Essaie un autre cable USB-C (certains sont charge-only).

**Le volume CIRCUITPY n'apparait pas :**
Attends 10 secondes. Si rien, debranche et rebranche sans BOOT.

**"RP2040-Zero non detecte" :**
Verifie le branchement USB. Sur macOS : `ls /dev/cu.usbmodem*`. Sur Windows : verifier le Gestionnaire de peripheriques (Ports COM). Sur Linux : `ls /dev/ttyACM*`.

**Le multi-terminal ne fonctionne pas :**
Verifier que `/tmp/blinky_states/` existe et est accessible en ecriture. Verifier que les hooks appellent `blinky_state.py` et non `blinky.py` directement.

**Les commandes passent mais pas d'animation :**
Verifier que le firmware utilise `sys.stdin.read(1)` et non `input()`.

**Sur macOS, les commandes bloquent :**
Utiliser `/dev/cu.usbmodem*`, jamais `/dev/tty.usbmodem*`. Le script `blinky.py` fait cette substitution automatiquement.

## Fichiers

- `code.py` — Firmware CircuitPython (NeoPixel uniquement, zero dependance externe)
- `blinky.py` — Script Python cross-platform pour envoyer des commandes au board
- `blinky_state.py` — Coordinateur multi-terminal (priorite alert > working > off, nettoyage sessions 30 min)
- `blinky_mcp.py` — Serveur MCP pour Claude Desktop / Cowork / Dispatch
- `lego_notify.sh` — Wrapper bash (macOS/Linux) pour blinky.py
- `lego_notify.bat` — Wrapper batch (Windows) pour blinky.py
- `INSTALL.md` — Ce fichier
- `ClaudeBlinky.MD` — Guide complet pour Claude Desktop
