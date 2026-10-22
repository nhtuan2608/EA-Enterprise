# G151 việc 2 — so engine Python với tester MT5 (S07)

Mục đích: kiểm sổ S07 bản Python (G89), nền của gần như mọi nghiên cứu S07, có ra cùng lệnh với EA S07Tester chạy trong tester MT5 không.
Kế hoạch: `docs/superpowers/plans/2026-10-22-g151-bot-time-map.md`, mục "Việc 2".

## Cách A — bấm trong MT5 (không cần tắt MT5 đang chạy)

1. MT5 → View → Strategy Tester (Ctrl+R).
2. Expert: `EnterpriseEA\S07Tester`. Symbol: `XAUUSD-VIP`. Timeframe: `M30`.
3. Date: Custom, `2024.02.20` → `2026.10.20`. Model: **Every tick based on real ticks**. Deposit 10000 USD, leverage 1:100.
4. Tab Inputs → chuột phải → **Load** → chọn `S07Tester_parity.set` (thư mục này). Các input quan trọng: News Guard tắt, sentiment tắt, lọc
   spread tắt, chặn lệnh ngược chiều tắt, khung vào lệnh M15.
5. Start. Chạy xong → tab Backtest → chuột phải → **Report → HTML** → lưu thành `S07Tester_parity.htm`.
6. Chạy so sánh:

```
python research/long/g151_parity_s07.py research/long/data <đường dẫn S07Tester_parity.htm> research/long/results/g151/parity.json
```

## Cách B — dòng lệnh (cần đóng MT5 đang chạy demo)

Chép `S07Tester_parity.set` vào `MQL5\Profiles\Tester\` của terminal. Chép `S07Tester_parity.ini` ra chỗ bất kỳ, rồi chạy:

```
"C:\Program Files\MetaTrader 5\terminal64.exe" /config:"<đường dẫn>\S07Tester_parity.ini"
```

Terminal tự chạy tester, ghi `S07Tester_parity.htm` vào thư mục terminal, rồi tự tắt. Sau đó mở lại MT5 như thường.

## Ngưỡng (ghi trước)

≥ 80% lệnh khớp ở mỗi bên và |chênh tổng R| ≤ 10% → engine Python tin cậy. Thấp hơn thì các nghiên cứu S07 bằng Python phải ghi chú độ lệch.
