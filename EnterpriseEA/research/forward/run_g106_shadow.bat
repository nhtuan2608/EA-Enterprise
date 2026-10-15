@echo off
REM G106 shadow forward: rebuilds the virtual trades from 2026-10-12 on fresh MT5 bars (read-only, no orders).
cd /d "%~dp0..\long"
python g106_shadow.py
