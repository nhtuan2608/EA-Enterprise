# G41: T2 trên tài sản xu hướng chưa từng dùng để chọn (06/10/2026)

Người dùng xuất XAGUSD, ETHUSD, USOUSD (dầu), SP500 (MT5, 2024-02-20 .. 2026-10-06). Không chọn tham số nào trên chúng:
T2 giữ bộ chọn trên 2010–2016. Phí giả định: 6 USD/lot cho bạc và dầu, 0 cho SP500 và ETH (chỉ spread). Script
`research/long/trend_assets.py` (`convert_raw.py --extra`).

## Kết quả (R trung bình mỗi lệnh; T2 có tín hiệu từ khoảng cuối 2024 vì EMA200 D1)

| Nhóm | T2 | T1 | T6 |
|---|---|---|---|
| XAGUSD / ETHUSD / USOUSD / SP500 | +0,20 / +0,30 / +0,38 / −0,18 | | |
| 4 tài sản mới gộp | **+0,167** (148 lệnh, PF 1,28) | +0,34 (42) | +0,25 (23) |
| 8 cặp tiền (G36) | −0,27 (278) | −0,12 | −0,05 |
| XAUUSD + BTCUSD, cùng giai đoạn | +0,58 (72) | +1,54 (12) | −0,25 |
| EURUSD + GBPUSD + USDJPY, cùng giai đoạn | −0,08 (88) | −0,09 | +0,03 |

Vào lệnh ngẫu nhiên (T2, 4 tài sản gộp, 2.000 lần): p = 0,11 — đúng hướng, gần kỳ vọng nghiên cứu (+0,17R), nhưng mẫu
1,7 năm chưa đủ chắc.

**Kết luận**: bám xu hướng hiệu quả trên hàng hóa và crypto (vàng, bạc, dầu, BTC, ETH), không hiệu quả trên cặp tiền gần
đây và trên SP500 trong giai đoạn này. Giả thuyết đặt ra sau G36/G38 được kiểm tra ngoài mẫu trên bạc, ETH, dầu: dương.

## Danh mục (FTMO 1-Step, 0,3%/lệnh, 2010–2025)

| Danh mục | %/năm | DD | Năm dương | Năm tệ nhất | p10 năm | DD p90 | Điểm |
|---|---|---|---|---|---|---|---|
| M5 + T2 trên 5 symbol | +3,95% | 5,6% | 14/16 | −2,6% | +3,57% | 12,3% | 0,29 |
| **M5 + T2 trên XAU, BTC** | **+3,49%** | **2,4%** | **15/16** | **−1,1%** | +2,83% | **4,8%** | **0,59** |
| M5 + T2 trên XAU, BTC, USDJPY | +3,91% | 3,0% | 15/16 | −0,2% | +3,65% | 6,7% | 0,54 |
| M5 + T2 trên EUR, GBP, JPY | +2,15% | 9,9% | 10/16 | −5,0% | +0,99% | 15,6% | 0,06 |

Chọn XAU, BTC là hậu nghiệm với 5 symbol cũ (dữ liệu XAU/BTC chỉ có từ 2018, không nằm trong 2010–2016), nhưng được bạc,
ETH, dầu xác nhận ngoài mẫu. Kỳ vọng thận trọng nên lấy mức của 4 tài sản mới (+0,17R/lệnh), không phải +0,6R của XAU/BTC.

## Thay đổi EA (mặc định không đổi hành vi)

- `InpT2LiveSymbols` (mặc định `XAUUSD,BTCUSD`): khi `InpT2Mode=T2_LIVE`, chỉ các symbol này vào lệnh thật; các symbol khác
  vẫn chạy SHADOW để thu bằng chứng (`EEA_StrategyRuntimeEngineMode`).
- `edge_monitor`: thêm dòng `T2_POSITION ảo XAU+BTC` (ngưỡng từ 243 lệnh nghiên cứu XAU/BTC; vì kỳ vọng nghiên cứu cao
  +0,64R nên dòng này báo động sớm nếu thực tế kém hơn nhiều).
- 676 test đạt, compile 0/0.

## Bước tiếp đề xuất

- Thêm XAGUSD, ETHUSD, USOUSD vào EA cho T2 (SHADOW): cần danh sách symbol theo từng setup, vì hiện mọi setup chạy trên cùng
  danh sách symbol của EA (thêm symbol sẽ thêm cả S04 LIVE trên symbol đó).
