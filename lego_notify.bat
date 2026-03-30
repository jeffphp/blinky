@echo off
REM lego_notify.bat — Wrapper Windows pour blinky.py
REM Usage : lego_notify.bat <commande> [args]

python "%~dp0blinky.py" %*
