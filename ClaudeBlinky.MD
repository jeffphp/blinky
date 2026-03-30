# Blinky — Physical LED Notification for Claude

You are an assistant helping the user build and configure Blinky, a USB LED indicator for Claude Code. Blinky shows blue when Claude is working, red when Claude needs attention, and green when Claude is ready. It works across multiple Claude Code terminals simultaneously.

Two hardware options are supported:

| | Luxafor Flag USB | RP2040-Zero |
|---|---|---|
| Price | ~$30 | ~$5 |
| Setup | Plug & play | Flash firmware |
| Dependencies | `hidapi` | `pyserial` |
| LED type | 6 RGB LEDs | 1 NeoPixel |

---

# Option A: Luxafor Flag USB

## A1. Hardware

**Luxafor Flag USB** — available on [luxafor.com](https://luxafor.com) or Amazon.

That's it. Plug it in via USB and it's ready.

## A2. Install prerequisites

```bash
pip install hidapi
```

Or with uv:
```bash
uv add hidapi
```

## A3. Project files

### File 1: `luxafor.py` (send commands to the Luxafor)

```python
#!/usr/bin/env python3
"""
luxafor.py — Send commands to the Luxafor Flag USB.
Cross-platform: macOS, Linux, Windows.

Prerequisite: pip install hidapi

Usage:
    python3 luxafor.py working
    python3 luxafor.py alert
    python3 luxafor.py status 0,255,0
    python3 luxafor.py done
    python3 luxafor.py off
"""

import sys

try:
    import hid
except ImportError:
    print("Error: hidapi missing. Install with: pip install hidapi")
    sys.exit(1)

VENDOR_ID = 0x04D8
PRODUCT_ID = 0xF372


def find_luxafor():
    """Detect the Luxafor Flag USB."""
    for dev in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        return dev
    return None


def send(cmd_bytes):
    """Send an HID command to the Luxafor."""
    device = hid.device()
    device.open(VENDOR_ID, PRODUCT_ID)
    padded = [0] + cmd_bytes + [0] * (8 - len(cmd_bytes))
    device.write(padded)
    device.close()


def cmd_static(r, g, b):
    """Static color on all LEDs."""
    return [1, 0xFF, r, g, b, 0, 0, 0]


def cmd_fade(r, g, b, speed=20):
    """Fade to a color."""
    return [2, 0xFF, r, g, b, speed, 0, 0]


def cmd_strobe(r, g, b, speed=10, repeat=0):
    """Strobe (repeat=0 = infinite)."""
    return [3, 0xFF, r, g, b, speed, 0, repeat]


def cmd_wave(wave_type, r, g, b, speed=10, repeat=0):
    """Wave animation 1-5 (repeat=0 = infinite)."""
    return [4, wave_type, r, g, b, 0, repeat, speed]


def process(cmd):
    """Process a text command and send it to the Luxafor."""
    if cmd == "working":
        send(cmd_strobe(0, 0, 255, speed=20, repeat=0))
    elif cmd == "alert":
        send(cmd_strobe(255, 0, 0, speed=5, repeat=0))
    elif cmd.startswith("status"):
        parts = cmd.split()
        if len(parts) > 1:
            r, g, b = parts[1].split(",")
            send(cmd_static(int(r), int(g), int(b)))
    elif cmd == "done":
        # Cancel ongoing strobe, then static green (ready)
        send(cmd_strobe(0, 0, 0, speed=1, repeat=1))
        send(cmd_static(0, 1, 0))
    elif cmd == "off":
        send(cmd_strobe(0, 0, 0, speed=1, repeat=1))


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 luxafor.py <command> [args]")
        print("Commands: working, alert, done, status <r,g,b>, off")
        sys.exit(1)

    cmd = " ".join(sys.argv[1:])
    info = find_luxafor()

    if not info:
        print("Error: Luxafor not detected. Check USB connection.")
        sys.exit(1)

    try:
        process(cmd)
        print(f"Sent: {cmd} -> Luxafor")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

> **Important:** The Luxafor hardware runs strobe animations autonomously. A `cmd_static(0,0,0)` does NOT cancel an ongoing strobe. You must send `cmd_strobe(0,0,0, repeat=1)` first to stop the animation.

### File 2: `luxafor_state.py` (multi-terminal coordinator)

```python
#!/usr/bin/env python3
"""
Multi-terminal state coordinator for Luxafor.

Priority: alert > working > done
- ANY terminal in alert -> red strobe
- ALL alerts resolved + ANY terminal working -> blue strobe
- ALL terminals stopped -> green (ready)

Called by hooks. Reads session_id from hook JSON on stdin.
"""

import sys
import os
import json
import glob
import time

from luxafor import find_luxafor, process as luxafor_process

STATE_DIR = "/tmp/blinky_states"
STALE_SECONDS = 1800

os.makedirs(STATE_DIR, exist_ok=True)


def get_session_id():
    try:
        data = json.load(sys.stdin)
        return data.get("session_id", f"unknown_{os.getpid()}")
    except Exception:
        return f"unknown_{os.getpid()}"


def cleanup_stale():
    now = time.time()
    for f in glob.glob(os.path.join(STATE_DIR, "*")):
        try:
            if now - os.path.getmtime(f) > STALE_SECONDS:
                os.remove(f)
        except Exception:
            pass


def set_state(session_id, action):
    state_file = os.path.join(STATE_DIR, session_id)
    if action == "stop":
        try:
            os.remove(state_file)
        except FileNotFoundError:
            pass
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
```

## A4. Test

```bash
python3 luxafor.py working        # Blue strobe — Claude is working
python3 luxafor.py alert          # Red strobe — needs attention
python3 luxafor.py done           # Green static — ready
python3 luxafor.py status 255,0,0 # Static red
python3 luxafor.py off            # Off
```

## A5. Configure Claude Code hooks

Add to `~/.claude/settings.json`. Replace `BLINKY_PATH` with the absolute path to the blinky folder.

If using **uv** (recommended):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --directory BLINKY_PATH python3 BLINKY_PATH/luxafor_state.py working",
            "timeout": 10
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
            "command": "uv run --directory BLINKY_PATH python3 BLINKY_PATH/luxafor_state.py alert",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "AskUserQuestion",
        "hooks": [
          {
            "type": "command",
            "command": "uv run --directory BLINKY_PATH python3 BLINKY_PATH/luxafor_state.py working",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --directory BLINKY_PATH python3 BLINKY_PATH/luxafor_state.py stop",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### Behavior

| Event | Luxafor |
|---|---|
| You send a message | Blue strobe |
| Claude asks a question | Red strobe |
| You answer | Back to blue strobe |
| Claude is done | Green (ready) |

### Multi-terminal

Multiple Claude Code sessions coordinate automatically via `luxafor_state.py`:
- **ANY** terminal needs attention -> red strobe
- **ALL** alerts resolved, any terminal still working -> blue strobe
- **ALL** terminals stopped -> green (ready)
- States stored in `/tmp/blinky_states/` (one file per session)
- Stale sessions cleaned up after 30 minutes

---

# Option B: RP2040-Zero

## B1. Order the hardware

**RP2040-Zero** (~$5 / ~5 EUR)
- Search: [Google "RP2040-Zero"](https://www.google.com/search?q=Waveshare+RP2040-Zero)
- Available on Amazon, AliExpress, Waveshare official store
- Has a built-in RGB NeoPixel LED — no soldering, no extra components
- USB-C connector

You also need a **USB-C data cable** (not charge-only).

## B2. Install prerequisites

```bash
pip install pyserial
```

## B3. Create the project files

### File 1: `code.py` (firmware — goes on the RP2040)

```python
"""
Firmware CircuitPython for RP2040-Zero — Blinky
Built-in NeoPixel LED on GP16 (RGB format).

Serial commands:
  alert         — blink red
  working       — breathe blue
  status <r,g,b> — set LED color
  off           — turn off
"""

import board
import digitalio
import neopixel_write
import sys
import time
import supervisor

rgb_pin = digitalio.DigitalInOut(board.GP16)
rgb_pin.direction = digitalio.Direction.OUTPUT

MAX_RGB = 40
BT = []
for i in range(50):
    BT.append(i * MAX_RGB // 50)
for i in range(50, 0, -1):
    BT.append(i * MAX_RGB // 50)
BT_LEN = len(BT)

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
```

### File 2: `blinky.py` (send commands to the board — cross-platform)

```python
#!/usr/bin/env python3
"""Send commands to Blinky. Cross-platform: macOS, Linux, Windows."""

import sys

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pip install pyserial")
    sys.exit(1)


def find_rp2040():
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


def send(port, cmd):
    ser = serial.Serial(port, 115200, timeout=1, dsrdtr=False, rtscts=False)
    ser.dtr = False
    ser.write((cmd + "\r\n").encode())
    ser.flush()
    ser.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 blinky.py <command>")
        print("Commands: alert, working, status <r,g,b>, off")
        sys.exit(1)

    cmd = " ".join(sys.argv[1:])
    port = find_rp2040()

    if not port:
        print("Error: RP2040-Zero not detected. Check USB connection.")
        sys.exit(1)

    try:
        send(port, cmd)
        print(f"Sent: {cmd} -> {port}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### File 3: `blinky_state.py` (multi-terminal coordinator)

```python
#!/usr/bin/env python3
"""
Multi-terminal state coordinator for Blinky.

Priority: alert > working > off
- ANY terminal in alert -> Blinky blinks red
- ALL alerts resolved + ANY terminal working -> Blinky breathes blue
- ALL terminals stopped -> Blinky off

Called by hooks. Reads session_id from hook JSON on stdin.
"""

import sys
import os
import json
import glob
import time
import subprocess

STATE_DIR = "/tmp/blinky_states"
STALE_SECONDS = 1800

os.makedirs(STATE_DIR, exist_ok=True)


def get_session_id():
    try:
        data = json.load(sys.stdin)
        return data.get("session_id", f"unknown_{os.getpid()}")
    except Exception:
        return f"unknown_{os.getpid()}"


def cleanup_stale():
    now = time.time()
    for f in glob.glob(os.path.join(STATE_DIR, "*")):
        try:
            if now - os.path.getmtime(f) > STALE_SECONDS:
                os.remove(f)
        except Exception:
            pass


def set_state(session_id, action):
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
```

## B4. Flash the RP2040-Zero

### Download CircuitPython

macOS / Linux:
```bash
curl -L -o ~/Downloads/circuitpython-rp2040-zero.uf2 \
  "https://downloads.circuitpython.org/bin/waveshare_rp2040_zero/fr/adafruit-circuitpython-waveshare_rp2040_zero-fr-10.1.4.uf2"
```

Windows (PowerShell):
```powershell
Invoke-WebRequest -Uri "https://downloads.circuitpython.org/bin/waveshare_rp2040_zero/fr/adafruit-circuitpython-waveshare_rp2040_zero-fr-10.1.4.uf2" -OutFile "$env:USERPROFILE\Downloads\circuitpython-rp2040-zero.uf2"
```

### Enter bootloader mode

1. Unplug the RP2040-Zero from USB
2. Hold the BOOT button (small button on the board)
3. Plug in USB-C while holding BOOT
4. Release BOOT

A volume named **RPI-RP2** should appear.

### Copy the firmware

```bash
# macOS
cp ~/Downloads/circuitpython-rp2040-zero.uf2 /Volumes/RPI-RP2/
```
```powershell
# Windows (adjust drive letter)
Copy-Item "$env:USERPROFILE\Downloads\circuitpython-rp2040-zero.uf2" "D:\"
```
```bash
# Linux
cp ~/Downloads/circuitpython-rp2040-zero.uf2 /media/$USER/RPI-RP2/
```

The board reboots. After a few seconds, a **CIRCUITPY** volume appears.

### Copy code.py

```bash
# macOS
cp code.py /Volumes/CIRCUITPY/code.py
```
```powershell
# Windows (adjust drive letter)
Copy-Item "code.py" "E:\code.py"
```
```bash
# Linux
cp code.py /media/$USER/CIRCUITPY/code.py
```

A **green flash** confirms the firmware is running.

## B5. Test

```bash
python3 blinky.py working        # LED breathes blue
python3 blinky.py alert          # LED blinks red
python3 blinky.py status 0,255,0 # LED turns green
python3 blinky.py off            # LED off
```

## B6. Configure Claude Code hooks

Add to `~/.claude/settings.json`. Replace `BLINKY_PATH` with the absolute path to the blinky folder.

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
        "matcher": "AskUserQuestion",
        "hooks": [
          {
            "type": "command",
            "command": "python3 BLINKY_PATH/blinky_state.py working",
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

On Windows, use `python` instead of `python3` and backslashes.

### Behavior

| Event | Blinky |
|---|---|
| You send a message | Breathes blue |
| Claude asks a question | Blinks red |
| You answer | Back to breathing blue |
| Claude is done | Turns off |

### Multi-terminal

Multiple Claude Code sessions coordinate automatically via `blinky_state.py`:
- **ANY** terminal needs attention -> Blinky blinks red
- **ALL** alerts resolved, any terminal still working -> Blinky breathes blue
- **ALL** terminals stopped -> Blinky off
- States stored in `/tmp/blinky_states/` (one file per session)
- Stale sessions cleaned up after 30 minutes

---

# MCP Server (optional — for Claude Desktop)

Only needed if you use Claude Desktop / Cowork / Dispatch.

Requires: `uv` and Python 3.12+.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
cd blinky
uv init --name blinky-mcp --no-readme
uv python pin 3.12
uv add "mcp[cli]" pyserial
```

See `blinky_mcp.py` for the MCP server code.

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

---

# Troubleshooting

**Luxafor not detected:**
- Check USB connection
- macOS: may need to allow HID access in System Settings > Privacy & Security
- Try `python3 -c "import hid; print(hid.enumerate(0x04D8, 0xF372))"`

**Luxafor stays blinking after Claude stops:**
The Luxafor runs strobe animations autonomously in hardware. A `cmd_static(0,0,0)` does NOT cancel an ongoing strobe — the hardware ignores it. To stop it, you must send a `cmd_strobe(0,0,0, repeat=1)` which replaces the infinite strobe with a single black one.

Quick fix to stop the blinking immediately:
```bash
python3 -c "import hid; d=hid.device(); d.open(0x04D8,0xF372); d.write([0,3,0xFF,0,0,0,1,0,1]); d.close()"
```

If your `luxafor.py` uses `cmd_static(0,0,0)` for "done"/"off", update it to:
```python
elif cmd == "done":
    send(cmd_strobe(0, 0, 0, speed=1, repeat=1))
    send(cmd_static(0, 1, 0))  # green = ready
elif cmd == "off":
    send(cmd_strobe(0, 0, 0, speed=1, repeat=1))
```

**RP2040: RPI-RP2 volume doesn't appear:**
Hold BOOT before plugging in. Try a different USB-C cable (some are charge-only).

**RP2040: CIRCUITPY volume doesn't appear:**
Wait 10 seconds. If nothing, unplug and replug without BOOT.

**RP2040: "RP2040-Zero not detected":**
- macOS: `ls /dev/cu.usbmodem*`
- Windows: Device Manager > Ports (COM & LPT)
- Linux: `ls /dev/ttyACM*`

**Commands sent but no animation (RP2040):**
Make sure the firmware uses `sys.stdin.read(1)` (byte-by-byte), not `input()`.

**Multi-terminal doesn't work:**
Check that `/tmp/blinky_states/` exists and is writable. Check hooks call `*_state.py`, not `blinky.py`/`luxafor.py` directly.

---

# Customization

## Luxafor

| Setting | File | Location | Default |
|---|---|---|---|
| Working animation | `luxafor.py` | `process("working")` | Blue strobe, speed=20 |
| Alert animation | `luxafor.py` | `process("alert")` | Red strobe, speed=5 |
| Ready color | `luxafor.py` | `process("done")` | Green static (0,1,0) |
| Stale session timeout | `luxafor_state.py` | `STALE_SECONDS` | 1800 (30 min) |

## RP2040-Zero

| Setting | File | Variable | Default |
|---|---|---|---|
| Breathing intensity | `code.py` | `MAX_RGB` | 40 (of 255) |
| Breathing speed | `code.py` | `0.03` in working loop | 30ms per step |
| Blink speed | `code.py` | `0.15` in alert loop | 150ms per toggle |
| Alert color | `code.py` | `set_rgb(255, 0, 0)` | Red |
| Working color | `code.py` | `set_rgb(0, 0, b)` | Blue |
| Stale session timeout | `blinky_state.py` | `STALE_SECONDS` | 1800 (30 min) |
