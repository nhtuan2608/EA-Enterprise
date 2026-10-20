@echo off
REM Daily forward check (read-only, no orders): V-reversal M30 (G118 A) + CtxBox (G106).
REM Output: research\forward\forward_daily.md and forward_history.csv
cd /d "%~dp0..\long"
python "%~dp0daily_forward.py"
