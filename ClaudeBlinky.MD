# Blinky — Physical LED Notification for Claude

You are an assistant helping the user build and configure Blinky, a USB LED indicator powered by an RP2040-Zero microcontroller. Blinky breathes blue when Claude is working, blinks red when Claude needs attention, and turns off when Claude is idle. It works across multiple Claude Code terminals simultaneously.

This file contains everything needed for a frictionless deployment. All code is embedded below — just create the files and follow the steps.

---

## 1. Order the hardware

Only one component is needed:

**RP2040-Zero** (~$5 / ~5 EUR)
- Search: [Google "RP2040-Zero"](https://www.google.com/search?q=Waveshare+RP2040-Zero)
- Available on Amazon, AliExpress, Waveshare official store
- Has a built-in RGB NeoPixel LED — no soldering, no extra components
- USB-C connector

You also need a **USB-C data cable** (not charge-only).

That's it. No LEDs, no resistors, no breadboard needed for the basic setup.

---

## 2. Install prerequisites

Python 3 and pyserial:

```bash
pip install pyserial
```

---

## 3. Create the project files

Create a folder called `blinky` and add the following 4 files.

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
Each Claude Code session writes its state. The coordinator picks the highest priority.

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

### File 4: `blinky_mcp.py` (MCP server for Claude Desktop — optional)

Only needed if you use Claude Desktop / Cowork / Dispatch.

Requires additional setup: `uv` and Python 3.12+.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # install uv
cd blinky
uv init --name blinky-mcp --no-readme
uv python pin 3.12
uv add "mcp[cli]" pyserial
```

```python
#!/usr/bin/env python3
"""MCP server for Blinky — lets Claude Desktop control the LED."""

import sys

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pip install pyserial", file=sys.stderr)
    sys.exit(1)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("blinky")


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


def send_command(cmd: str) -> str:
    port = find_rp2040()
    if not port:
        return "Error: Blinky not detected. Check USB connection."
    try:
        ser = serial.Serial(port, 115200, timeout=1, dsrdtr=False, rtscts=False)
        ser.dtr = False
        ser.write((cmd + "\r\n").encode())
        ser.flush()
        ser.close()
        return f"OK: {cmd} -> {port}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def blinky_working() -> str:
    """Activate Blinky breathing mode (slow blue pulse). Use when working on a task."""
    return send_command("working")


@mcp.tool()
def blinky_alert() -> str:
    """Activate Blinky alert mode (red blink). Use when waiting for user input."""
    return send_command("alert")


@mcp.tool()
def blinky_off() -> str:
    """Turn off Blinky completely. Use when done working."""
    return send_command("off")


@mcp.tool()
def blinky_blink(times: int = 3) -> str:
    """Blink Blinky a specific number of times.

    Args:
        times: number of blinks (default 3)
    """
    return send_command(f"blink {times}")


@mcp.tool()
def blinky_status(r: int, g: int, b: int) -> str:
    """Set Blinky LED to a specific color.

    Args:
        r: red component (0-255)
        g: green component (0-255)
        b: blue component (0-255)
    """
    return send_command(f"status {r},{g},{b}")


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

## 4. Flash the RP2040-Zero

### 4a. Download CircuitPython

macOS / Linux:
```bash
curl -L -o ~/Downloads/circuitpython-rp2040-zero.uf2 \
  "https://downloads.circuitpython.org/bin/waveshare_rp2040_zero/fr/adafruit-circuitpython-waveshare_rp2040_zero-fr-10.1.4.uf2"
```

Windows (PowerShell):
```powershell
Invoke-WebRequest -Uri "https://downloads.circuitpython.org/bin/waveshare_rp2040_zero/fr/adafruit-circuitpython-waveshare_rp2040_zero-fr-10.1.4.uf2" -OutFile "$env:USERPROFILE\Downloads\circuitpython-rp2040-zero.uf2"
```

### 4b. Enter bootloader mode

Physical action — the user must do this themselves:
1. Unplug the RP2040-Zero from USB
2. Hold the BOOT button (small button on the board)
3. Plug in USB-C while holding BOOT
4. Release BOOT

A volume named **RPI-RP2** should appear.

### 4c. Copy the firmware

```bash
# macOS
cp ~/Downloads/circuitpython-rp2040-zero.uf2 /Volumes/RPI-RP2/
```
```powershell
# Windows (adjust drive letter, e.g. D:)
Copy-Item "$env:USERPROFILE\Downloads\circuitpython-rp2040-zero.uf2" "D:\"
```
```bash
# Linux
cp ~/Downloads/circuitpython-rp2040-zero.uf2 /media/$USER/RPI-RP2/
```

The board reboots. After a few seconds, a **CIRCUITPY** volume appears.

### 4d. Copy code.py

Copy the `code.py` file (from step 3) onto the CIRCUITPY volume:

```bash
# macOS
cp code.py /Volumes/CIRCUITPY/code.py
```
```powershell
# Windows (adjust drive letter, e.g. E:)
Copy-Item "code.py" "E:\code.py"
```
```bash
# Linux
cp code.py /media/$USER/CIRCUITPY/code.py
```

A **green flash** confirms the firmware is running.

---

## 5. Test

```bash
python3 blinky.py working       # LED breathes blue
python3 blinky.py alert         # LED blinks red
python3 blinky.py status 0,255,0 # LED turns green
python3 blinky.py off           # LED off
```

---

## 6. Configure Claude Code hooks

Add to `~/.claude/settings.json` (macOS/Linux) or `%USERPROFILE%\.claude\settings.json` (Windows).

Replace `BLINKY_PATH` with the absolute path to the blinky folder.

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

On Windows, use `python` instead of `python3` and backslashes: `"python BLINKY_PATH\\blinky_state.py alert"`

After editing, open `/hooks` in Claude Code to reload.

### Behavior

| Event | Blinky |
|---|---|
| You send a message | Breathes blue |
| Claude asks a question | Blinks red |
| Claude needs permission | Blinks red |
| Any tool completes | Back to breathing blue |
| Claude is done | Turns off |

### Multi-terminal

Multiple Claude Code sessions coordinate automatically via `blinky_state.py`:
- **ANY** terminal needs attention → Blinky blinks red
- **ALL** alerts resolved, any terminal still working → Blinky breathes blue
- **ALL** terminals stopped → Blinky off
- States stored in `/tmp/blinky_states/` (one file per session)
- Stale sessions cleaned up after 30 minutes

---

## 7. Configure Claude Desktop (optional)

For Claude Desktop / Cowork / Dispatch, add the MCP server.

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

Replace `BLINKY_PATH` with the absolute path to the blinky folder. Quit and restart Claude Desktop to load.

For Cowork/Dispatch, add to your prompt: *"Call blinky_working when you start working, blinky_alert when you need my input, blinky_off when you're done."*

---

## Customization

| Setting | File | Variable | Default |
|---|---|---|---|
| Breathing intensity | `code.py` | `MAX_RGB` | 40 (of 255) |
| Breathing speed | `code.py` | `0.03` in working loop | 30ms per step |
| Blink speed | `code.py` | `0.15` in alert loop | 150ms per toggle |
| Alert color | `code.py` | `set_rgb(255, 0, 0)` | Red |
| Working color | `code.py` | `set_rgb(0, 0, b)` | Blue |
| Stale session timeout | `blinky_state.py` | `STALE_SECONDS` | 1800 (30 min) |

---

## Troubleshooting

**RPI-RP2 volume doesn't appear:**
Hold BOOT before plugging in. Try a different USB-C cable (some are charge-only).

**CIRCUITPY volume doesn't appear:**
Wait 10 seconds. If nothing, unplug and replug without BOOT.

**"RP2040-Zero not detected":**
- macOS: `ls /dev/cu.usbmodem*`
- Windows: Device Manager > Ports (COM & LPT)
- Linux: `ls /dev/ttyACM*`

**Commands sent but no animation:**
Make sure the firmware uses `sys.stdin.read(1)` (byte-by-byte), not `input()`. The `input()` function blocks the animation loop.

**On macOS, commands hang:**
Use `/dev/cu.usbmodem*` (callout device), never `/dev/tty.usbmodem*` (blocks waiting for DCD signal). `blinky.py` handles this automatically.

**Multi-terminal doesn't work:**
Check that `/tmp/blinky_states/` exists and is writable. Check hooks call `blinky_state.py`, not `blinky.py` directly.
