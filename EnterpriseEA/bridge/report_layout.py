"""Telegram layout of an AI report (19/10/2026): HTML with a header, sections and a collapsible summary.

Pure: takes the validated report the bridge wrote (ai/reports/<KIND>.json) and returns Telegram HTML
(parse_mode=HTML) no longer than the message limit. Every text from the report is escaped; the only
tags are the ones built here (b, i, blockquote expandable), so the message always parses.
"""
from __future__ import annotations

import html
import re
import time

KIND_ICON = {"EA_DIAGNOSTICS": "🩺", "NEWS_DATA_REVIEW": "📊", "NEWS_PRE_BRIEF": "⏰",
             "NEWS_FLASH": "⚡", "NEWS_EVENT_REVIEW": "🕓"}
CONFIDENCE = {"LOW": "thấp", "MEDIUM": "trung bình", "HIGH": "cao"}
SCALP_ICON = (("NÊN SCALP MUA", "🟢"), ("NÊN SCALP BÁN", "🔴"), ("KHÔNG NÊN", "⚪"), ("CHỜ", "🟡"))
ACTION_LABEL = {"RECOMMEND_WINDOW_CHANGE": "đổi khoảng chặn", "RECOMMEND_REVIEW": "xem lại", "REPORT": "ghi nhận",
                "WARN": "cảnh báo"}
RULE = "━━━━━━━━━━━━━━━━"
FOOTER = "<i>AI chỉ báo cáo và khuyến nghị: không đặt lệnh, không đổi cấu hình.</i>"


def esc(value, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        text = text[:limit - 1].rstrip() + "…"
    return html.escape(text, quote=False)


def scalp_line(rec: dict) -> str:
    proposal = " ".join(str(rec.get("proposal") or "").split())
    icon, label, reason = "🔹", "", proposal
    upper = proposal.upper()
    for key, mark in SCALP_ICON:
        if upper.startswith(key):
            icon, label = mark, key
            # Drop the separator after the label (": " or " - "), never a number's minus sign.
            reason = re.sub(r"^\s*(?::\s*|[-–—]\s+|\.\s*|,\s*)?", "", proposal[len(key):])
            break
    head = f"{icon} <b>{esc(rec.get('target'), 24)}</b>"
    if label:
        head += f" · <b>{html.escape(label)}</b>"
    return head + (f"\n      <i>{esc(reason, 220)}</i>" if reason else "")


def _sections(rep: dict, summary_limit: int, warn_max: int, info_max: int, recs_max: int) -> list[str]:
    recs = [r for r in rep.get("recommendations", []) if isinstance(r, dict)]
    scalp = [r for r in recs if r.get("action") == "SCALP_VIEW"]
    others = [r for r in recs if r.get("action") != "SCALP_VIEW"]
    findings = [f for f in rep.get("findings", []) if isinstance(f, dict)]
    warn = [f for f in findings if str(f.get("severity", "")).upper() == "WARN"]
    info = [f for f in findings if str(f.get("severity", "")).upper() != "WARN"]
    out = []
    if scalp:
        out.append("🎯 <b>Nhận định scalp</b> <i>(EA không tự vào lệnh)</i>\n" +
                   "\n".join(scalp_line(r) for r in scalp[:8]))
    summary = esc(rep.get("summary"), summary_limit)
    if summary:
        out.append(f"📝 <b>Tóm tắt</b>\n<blockquote expandable>{summary}</blockquote>")
    if warn[:warn_max]:
        out.append("⚠️ <b>Cần chú ý</b>\n" + "\n".join(f"• {esc(f.get('detail'), 260)}" for f in warn[:warn_max]))
    if others[:recs_max]:
        out.append("👉 <b>Đề xuất</b>\n" + "\n".join(
            f"• <b>{esc(r.get('target'), 60)}</b> <i>({ACTION_LABEL.get(r.get('action'), 'đề xuất')})</i>: "
            f"{esc(r.get('proposal'), 260)}" for r in others[:recs_max]))
    if info[:info_max]:
        out.append("ℹ️ <b>Ghi chú</b>\n" + "\n".join(f"• {esc(f.get('detail'), 220)}" for f in info[:info_max]))
    return out


def format_report(kind: str, title: str, rep: dict, limit: int = 3500) -> str:
    """Telegram HTML for one AI report, shortened until it fits `limit` characters."""
    created = int(rep.get("created_at_utc", 0) or 0)
    when = time.strftime("%H:%M %d/%m", time.localtime(created)) if created > 0 else ""
    confidence = CONFIDENCE.get(str(rep.get("confidence_label", "")).upper(), "")
    meta = " · ".join(x for x in (when, f"độ tin cậy {confidence}" if confidence else "") if x)
    header = f"{KIND_ICON.get(kind, '🤖')} <b>{html.escape(title)}</b> · AI" + (f"\n<i>{meta}</i>" if meta else "")
    # Shorten in order: notes, suggestions, warnings, then the summary.
    for summary_limit, warn_max, info_max, recs_max in ((1200, 4, 3, 4), (1200, 4, 1, 3), (900, 3, 0, 2),
                                                        (700, 2, 0, 1), (400, 2, 0, 0), (250, 1, 0, 0)):
        text = "\n\n".join([header, RULE] + _sections(rep, summary_limit, warn_max, info_max, recs_max) + [FOOTER])
        if len(text) <= limit:
            return text
    return "\n\n".join([header, RULE, f"📝 {esc(rep.get('summary'), 250)}", FOOTER])


def plain_text(text: str) -> str:
    """Fallback when Telegram rejects the HTML: the same message without tags."""
    return html.unescape(re.sub(r"<[^>]+>", "", text))
