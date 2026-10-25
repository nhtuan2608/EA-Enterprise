"""Council step 3b-1: the parts that are not AI - knowledge-base codes, the quantitative anchor, the answer validator, the
judge's fixed rules, the CUSUM drift monitor and the daily call budget.
Plan: docs/superpowers/plans/2026-10-25-council-3b.md. Standard library only.
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB_PATH = HERE.parent / "docs" / "ai-knowledge" / "knowledge-base.md"
FINGERPRINTS = HERE.parent / "research" / "lab" / "fingerprints.json"

# Fixed decision menu (design 4.2 / 4.4): the council may only keep, reduce or pause; never open or add risk.
MENU = {"giu_nguyen", "giam_rui_ro_50", "chan_boi_lenh", "tam_dung_bot", "dung_lenh_moi", "doi_sl_an_toan", "chot_mot_phan"}
CONFIDENCE = {"thap", "vua", "cao"}
MAX_HOLD_MINUTES = 480

# Quantitative anchor (agent 1): numbers measured in G156a2 / G156b / G156c, with their knowledge-base codes.
ANCHOR = {
    "huong_sau_pha_muc_vang": {"p": 0.51, "ma": "B8", "ghi_chu": "± 1 ATR M30 trong 4 giờ, không bối cảnh giá nào đoán tốt hơn"},
    "s07_dang_loi_di_tiep": {"p": 0.61, "ma": "B21", "ghi_chu": "lệnh S07 đang lời đi thêm +1R trước khi lùi 1R"},
    "s07_r_ky_vong": {"r": 0.3, "ma": "A1", "ghi_chu": "mọi lệnh S07 có R kỳ vọng như nhau; không bối cảnh nào xếp hạng được (G156b)"},
    "tinh_huong_co_ten": {"ma": "C18", "ghi_chu": "tình huống có tên không báo trước hướng; chỉ dùng cảnh báo / giải thích"},
}
DIRECTION_SLACK = 0.05

ROLE_KEYS = {"tin_tuc", "thuc_thi", "giam_sat_bot", "logic_bot", "phan_bien", "tham_phan"}


# ---------------------------------------------------------------------------------------------------------------- knowledge
def kb_codes(path: Path = KB_PATH) -> set[str]:
    """Codes of the knowledge base rows (A1.., B.., C.., E..) plus "D" for the bot-logic section."""
    text = path.read_text(encoding="utf-8")
    codes = set(re.findall(r"^\| ([ABCE]\d+) \|", text, flags=re.M))
    codes.add("D")
    return codes


def kb_rows(codes: set[str], path: Path = KB_PATH) -> str:
    """The table rows of the requested codes (what a role is allowed to cite), as plain text."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| ([ABCE]\d+) \|", line)
        if m and m.group(1) in codes:
            out.append(line)
    return "\n".join(out)


def flatten(obj, prefix="ctx") -> set[str]:
    keys = {prefix}
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys |= flatten(v, f"{prefix}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:50]):
            keys |= flatten(v, f"{prefix}.{i}")
    return keys


# ---------------------------------------------------------------------------------------------------------------- validator
def extract_json(text: str):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


def _evidence_ok(items, codes, ctx_keys, allow_c):
    bad = []
    if not isinstance(items, list) or not items:
        return ["thiếu dẫn chứng"]
    for ref in items:
        ref = str(ref)
        if ref.startswith("ctx."):
            if ref not in ctx_keys:
                bad.append(f"trường không có: {ref}")
        elif ref in codes:
            if ref.startswith("C") and not allow_c:
                bad.append(f"dẫn {ref} (phần C: đã thất bại) làm lý do")
        else:
            bad.append(f"mã không có: {ref}")
    return bad


def validate(role: str, answer, codes: set[str], ctx: dict) -> tuple[bool, list[str]]:
    """Checks one role's answer. Returns (accepted, problems). Problems on a non-judge role about direction are flags."""
    problems = []
    if not isinstance(answer, dict):
        return False, ["không phải JSON"]
    if answer.get("agent") != role:
        problems.append(f"agent sai: {answer.get('agent')}")
    if answer.get("de_xuat") not in MENU:
        problems.append(f"de_xuat ngoài menu: {answer.get('de_xuat')}")
    if answer.get("muc_tu_tin") not in CONFIDENCE:
        problems.append("muc_tu_tin sai")
    ctx_keys = flatten(ctx)
    reasons = answer.get("ly_do")
    if not isinstance(reasons, list) or not reasons:
        problems.append("thiếu ly_do")
    else:
        for r in reasons[:12]:
            if not isinstance(r, dict) or not str(r.get("noi_dung", "")).strip():
                problems.append("ly_do sai khuôn")
                continue
            # C rows (failed ideas) may only be cited to reject something: bot logic, red team, judge
            problems += _evidence_ok(r.get("dan_chung"), codes, ctx_keys, allow_c=role in ("logic_bot", "phan_bien", "tham_phan"))
    probs = answer.get("xac_suat", {})
    if probs is not None and not isinstance(probs, dict):
        problems.append("xac_suat sai khuôn")
    elif probs:
        for k, v in probs.items():
            if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
                problems.append(f"xac_suat {k} ngoài 0..1")
    if role == "phan_bien":
        for b in answer.get("bac_bo", []) or []:
            if not isinstance(b, dict) or not b.get("doi_tuong"):
                problems.append("bac_bo sai khuôn")
            else:
                problems += _evidence_ok(b.get("dan_chung"), codes, ctx_keys, allow_c=True)
    if role == "tham_phan":
        if answer.get("phan_quyet") not in MENU:
            problems.append(f"phan_quyet ngoài menu: {answer.get('phan_quyet')}")
        th = answer.get("thoi_han_phut")
        if not isinstance(th, int) or not 0 < th <= MAX_HOLD_MINUTES:
            problems.append("thoi_han_phut sai")
        for step in answer.get("ke_hoach", []) or []:
            if not isinstance(step, dict) or not step.get("neu") or step.get("thi") not in MENU:
                problems.append("ke_hoach sai khuôn")
        if not str(answer.get("tom_tat_vi", "")).strip() or len(str(answer.get("tom_tat_vi"))) > 800:
            problems.append("tom_tat_vi sai")
    return (not problems), problems


def judge_clamp(answer: dict, anchors: dict) -> list[str]:
    """Code side of the judge's rule: a direction probability never leaves the anchor by more than 5 points."""
    notes = []
    for k, v in list((answer.get("xac_suat") or {}).items()):
        if k in anchors and "p" in anchors[k]:
            lo, hi = anchors[k]["p"] - DIRECTION_SLACK, anchors[k]["p"] + DIRECTION_SLACK
            nv = min(max(float(v), lo), hi)
            if nv != float(v):
                notes.append(f"kẹp {k}: {v} → {round(nv, 3)} (mỏ neo {anchors[k]['p']} ± {DIRECTION_SLACK})")
                answer["xac_suat"][k] = round(nv, 3)
    return notes


def safe_verdict(reason: str) -> dict:
    """What the council says when the judge's answer cannot be used: the rules decide."""
    return {"agent": "tham_phan", "phan_quyet": "giu_nguyen", "de_xuat": "giu_nguyen", "thoi_han_phut": 60, "ke_hoach": [],
            "muc_tu_tin": "thap", "ly_do": [{"noi_dung": reason, "dan_chung": ["D"]}],
            "tom_tat_vi": f"Hội đồng không ra phán quyết hợp lệ ({reason}); giữ nguyên quyết định của luật bot."}


# ---------------------------------------------------------------------------------------------------------------- CUSUM
class Cusum:
    """One-sided CUSUM for a fall of the mean R per closed leg: S = max(0, S + (mu - x) / sigma - k)."""

    def __init__(self, mu: float, sigma: float, k: float = 0.5, warn: float = 3.0, alarm: float = 5.0, s: float = 0.0):
        self.mu, self.sigma, self.k, self.warn, self.alarm, self.s = mu, sigma, k, warn, alarm, s

    def update(self, x: float) -> str:
        self.s = max(0.0, self.s + (self.mu - x) / self.sigma - self.k)
        if self.s >= self.alarm:
            return "LECH_HAN"
        if self.s >= self.warn:
            return "DANG_NGO"
        return "BINH_THUONG"


def load_fingerprints(path: Path = FINGERPRINTS) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------------------------------------------------- budget
class Budget:
    """Model calls per UTC day (failed calls count). Saved in current/council_state.json by the caller."""

    def __init__(self, state: dict, limit: int = 20, low: int = 6, max_meetings: int = 3, clock=time.time):
        self.state, self.limit, self.low, self.max_meetings, self.clock = state, limit, low, max_meetings, clock
        self._roll()

    def _roll(self):
        day = time.strftime("%Y-%m-%d", time.gmtime(self.clock()))
        if self.state.get("day") != day:
            self.state.update(day=day, calls=0, meetings=0)

    def left(self) -> int:
        self._roll()
        return self.limit - int(self.state.get("calls", 0))

    def can_meet(self, priority: int, calls_needed: int) -> tuple[bool, str]:
        self._roll()
        if int(self.state.get("meetings", 0)) >= self.max_meetings and priority > 1:
            return False, "đủ số cuộc họp trong ngày"
        if self.left() < calls_needed:
            return False, "hết lượt"
        if self.left() <= self.low and priority > 2:
            return False, f"còn ≤ {self.low} lượt: chỉ họp cho bất thường và tin lớn"
        return True, ""

    def spend(self):
        self._roll()
        self.state["calls"] = int(self.state.get("calls", 0)) + 1

    def meeting(self):
        self._roll()
        self.state["meetings"] = int(self.state.get("meetings", 0)) + 1


def market_open(utc: float) -> bool:
    """Gold trading week, roughly Sunday 22:00 to Friday 21:00 UTC."""
    t = time.gmtime(utc)
    wd, minutes = t.tm_wday, t.tm_hour * 60 + t.tm_min     # Monday = 0
    if wd == 5:
        return False
    if wd == 6:
        return minutes >= 22 * 60
    if wd == 4:
        return minutes < 21 * 60
    return True


def r_from_money(money: float, capital: float, risk_percent: float) -> float:
    unit = capital * risk_percent / 100.0
    return money / unit if unit > 0 else math.nan
