"""Daily forward check of the two forward-only leads (read-only, no orders):
  - V-reversal M30 (G118 candidate A, stop +-2 ATR, G116 hedge management): groups from 2026-10-10 on;
  - CtxBox (G106, context switch + BOX hold, M5 / M15 / M30 / H1): virtual trades from 2026-10-12 on.
Both are rebuilt from scratch on the running terminal's XAUUSD-VIP bars every run (deterministic), so the script can run
at any time. Signals and outcomes use one bar frame per run (no stale caches, lesson of the G108 test).

  python research/forward/daily_forward.py      (or run_daily_forward.bat)

Writes research/forward/forward_daily.md (summary + every trade) and appends one line per run to forward_history.csv.
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "long"))
import g134_extensions as g134  # noqa: E402

V_START = pd.Timestamp("2026-10-10")
HIST_R = {"V M30": 0.421}          # research mean (U per group), G118 / G134 reproduction


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = [f"# Forward hằng ngày (lệnh ảo, không đặt lệnh)", "", f"Cập nhật {now}. Nến: terminal XAUUSD-VIP (chỉ đọc).", ""]
    hist = []
    # V-reversal M30
    try:
        m = g134.prep_v(g134.terminal_m30())
        fw = g134.candidate_a(m)
        fw = fw[fw["t"] >= V_START]
        closed = fw[fw["r"].notna()]
        L += ["## Nến V M30 (G118 ứng viên A)", "",
              f"Nến M30 tới {m['ts'].iat[-1]:%Y-%m-%d %H:%M} (server). Từ {V_START:%d/%m/%Y}: {len(fw)} nhóm, đã đóng {len(closed)}, "
              f"tổng {closed['r'].sum():+.2f}U, trung bình {closed['r'].mean() if len(closed) else float('nan'):+.2f}U "
              f"(nghiên cứu {HIST_R['V M30']:+.2f}U/nhóm).", ""]
        if len(fw):
            L += ["| Nến quay về (server) | Chiều V | Kết quả (U) |", "|---|---|---|"]
            for r in fw.itertuples():
                L.append(f"| {r.t:%Y-%m-%d %H:%M} | {'lên' if r.vdir == 1 else 'xuống'} | {'đang mở' if r.r != r.r else f'{r.r:+.2f}'} |")
            L.append("")
        hist.append(("V_M30", len(fw), len(closed), float(closed["r"].sum())))
    except Exception as ex:
        L += ["## Nến V M30", "", f"Không đọc được terminal ({ex}).", ""]
    # CtxBox
    try:
        import g106_shadow as sh
        with redirect_stdout(io.StringIO()):
            sh.main()
        t = pd.read_csv(HERE / "g106_shadow_trades.csv")
        L += ["## CtxBox (G106)", ""]
        txt = (HERE / "g106_shadow_summary.md").read_text(encoding="utf-8").splitlines()
        L += [ln for ln in txt if ln.startswith("|") or ln.startswith("- ")] + [""]
        for (tf, d), x in t.groupby(["tf", "dir"]):
            c = x[x["status"] == "closed"]
            hist.append((f"CtxBox_{tf}_{d}", len(x), len(c), float(c["r"].sum())))
    except Exception as ex:
        L += ["## CtxBox", "", f"Không chạy được ({ex}).", ""]
    (HERE / "forward_daily.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    hp = HERE / "forward_history.csv"
    new = not hp.exists()
    with hp.open("a", encoding="utf-8") as f:
        if new:
            f.write("run_utc,item,trades,closed,total_r\n")
        for item, n, c, r in hist:
            f.write(f"{now},{item},{n},{c},{r:.2f}\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
