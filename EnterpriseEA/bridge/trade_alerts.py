"""Telegram alerts for real orders outside the EA audit (20/10/2026).

The bots (VHedge, XauRegime, CtxLimit) write their orders to logs/bots-YYYYMM.jsonl, not to the
audit the gateway already follows, and a broker rejection of any EA order only shows in the MT5
Journal ("failed market buy ... [No money]"). These helpers read new lines of both files from a
saved position and turn the lines worth a message into text. Read only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LIVE_EVENTS = {"ENTRY": "🟢 BOT VÀO LỆNH", "ORDER": "📌 BOT ĐẶT LỆNH CHỜ", "FILL": "✅ BOT KHỚP LỆNH",
               "CLOSE": "🏁 BOT ĐÓNG LỆNH", "EXIT": "🏁 BOT THOÁT LỆNH"}
FAILURE_TEXT = re.compile(r"từ chối|failed|lỗi|error|mã 10\d{3}", re.I)
# MT5 Journal reasons of a rejected request, in the operator's words.
BROKER_REASON = (("no money", "không đủ tiền ký quỹ"), ("not enough money", "không đủ tiền ký quỹ"),
                 ("invalid volume", "khối lượng không hợp lệ (dưới mức tối thiểu hoặc sai bước lot)"),
                 ("invalid stops", "SL/TP không hợp lệ (quá gần giá)"), ("market closed", "thị trường đang đóng cửa"),
                 ("trade disabled", "symbol không cho giao dịch"), ("autotrading disabled", "Algo Trading đang tắt"),
                 ("requote", "broker báo giá lại"), ("off quotes", "không có giá"), ("no prices", "không có giá"),
                 ("invalid price", "giá không hợp lệ"), ("invalid fill", "kiểu khớp lệnh không được hỗ trợ"),
                 ("unsupported filling", "kiểu khớp lệnh không được hỗ trợ"), ("too many requests", "gửi lệnh quá dày"),
                 ("position doesn't exist", "vị thế cần đóng/sửa không còn (đã đóng trước đó)"),
                 ("rejected", "broker từ chối"))
MT5_FAILURE = re.compile(r"\bfailed\b.*\b(market|buy|sell|limit|stop|modify|close|cancel|order|position)\b"
                         r"|\[(no money|not enough money|invalid volume|invalid stops|market closed|trade disabled|"
                         r"requote|off quotes|no prices|invalid price|rejected)\]", re.I)


def tail_jsonl(path: Path, pos: int) -> tuple[list[dict], int]:
    """New complete JSON lines after byte `pos`; a shorter file (rotated) restarts at 0."""
    try:
        size = path.stat().st_size
    except OSError:
        return [], pos
    if size < pos:
        pos = 0
    with open(path, "rb") as fh:
        fh.seek(pos)
        chunk = fh.read(2_000_000)
    end = chunk.rfind(b"\n")
    if end < 0:
        return [], pos
    rows = []
    for raw in chunk[:end].splitlines():
        try:
            rows.append(json.loads(raw.decode("utf-8", "replace")))
        except ValueError:
            continue
    return rows, pos + end + 1


def tail_utf16(path: Path, pos: int) -> tuple[list[str], int]:
    """New complete lines of an MT5 log (UTF-16 LE with BOM) after byte `pos`."""
    try:
        size = path.stat().st_size
    except OSError:
        return [], pos
    if size < pos:
        pos = 0
    pos -= pos % 2
    with open(path, "rb") as fh:
        fh.seek(pos)
        chunk = fh.read(2_000_000)
    end = -1
    i = chunk.rfind(b"\n\x00")
    while i >= 0:
        if (pos + i) % 2 == 0:
            end = i
            break
        i = chunk.rfind(b"\n\x00", 0, i)
    if end < 0:
        return [], pos
    text = chunk[:end + 2].decode("utf-16-le", "replace").lstrip("﻿")
    return [l.rstrip("\r") for l in text.split("\n") if l.strip()], pos + end + 2


def bot_message(row: dict, titles: dict) -> str | None:
    """Text for a LIVE bot journal line worth a message, else None (SHADOW, NEAR, decisions)."""
    if str(row.get("mode", "")).upper() != "LIVE":
        return None
    event = str(row.get("event", ""))
    text = " ".join(str(row.get("text", "")).split())
    bot = titles.get(row.get("bot"), row.get("bot"))
    when = row.get("server", "")
    if event in LIVE_EVENTS:
        return f"{LIVE_EVENTS[event]} · {bot}\n{text}\n(giờ server {when})"
    if FAILURE_TEXT.search(text):
        return f"❗ BOT LỖI ĐẶT LỆNH · {bot}\n{text}\n(giờ server {when})"
    return None


def mt5_failure_message(line: str) -> str | None:
    """Text for a rejected request in the MT5 Journal, else None."""
    parts = line.split("\t")                         # code, level, time, source, message
    body = "\t".join(parts[4:]).strip() if len(parts) >= 5 else line.strip()
    if not MT5_FAILURE.search(body):
        return None
    low = body.lower()
    why = next((vi for key, vi in BROKER_REASON if key in low), "")
    when = f"\n(giờ UTC {parts[2].split('.')[0]})" if len(parts) >= 5 else ""
    return "❗ LỖI GỬI LỆNH (MT5)\n" + body[:300] + (f"\nNghĩa là: {why}" if why else "") + when
