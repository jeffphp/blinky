"""Test RGB : anode commune, inversee. Cycle chaque canal 5 sec.
Vide le buffer serie pour que les hooks n'interferent pas."""
import board
import pwmio
import supervisor
import sys
import time

eye_r = pwmio.PWMOut(board.GP0, frequency=1000, duty_cycle=65535)
eye_b = pwmio.PWMOut(board.GP1, frequency=1000, duty_cycle=65535)
eye_g = pwmio.PWMOut(board.GP2, frequency=1000, duty_cycle=65535)

V = 65535 - 3000  # faible intensite, inversee

def drain_serial():
    while supervisor.runtime.serial_bytes_available:
        sys.stdin.read(1)

while True:
    drain_serial()

    # GP0 seul
    eye_r.duty_cycle = V
    eye_b.duty_cycle = 65535
    eye_g.duty_cycle = 65535
    time.sleep(5)
    drain_serial()

    # GP1 seul
    eye_r.duty_cycle = 65535
    eye_b.duty_cycle = V
    eye_g.duty_cycle = 65535
    time.sleep(5)
    drain_serial()

    # GP2 seul
    eye_r.duty_cycle = 65535
    eye_b.duty_cycle = 65535
    eye_g.duty_cycle = V
    time.sleep(5)
    drain_serial()

    # Eteint
    eye_r.duty_cycle = 65535
    eye_b.duty_cycle = 65535
    eye_g.duty_cycle = 65535
    time.sleep(2)
