# G23: kiểm định trên lịch sử dài 2010–2025 (05/10/2026)

## Dữ liệu và phương pháp
- Nguồn: xuất MT5 do người dùng cung cấp (`D:\Work\Private\AI APP\Trading-with-AI\input\raw`), chỉ đọc. Chuyển đổi bằng `research/long/convert_raw.py`.
- H1/H4: EURUSD, GBPUSD, USDJPY từ 2010; XAUUSD từ 03/2018, BTCUSD từ 2018 (trước đó dữ liệu thưa, khoảng 260 nến H1/năm, đã bỏ). M5: 06/2024–10/2025 (không có BTCUSD).
- Chi phí: spread của dữ liệu, đặt sàn bằng trung vị 2024–2025 của từng symbol (vài năm có spread 1 point bất thường); commission ước tính như G10. Mô hình Trade Manager "tm" của G10; trong một nến chạm SL tính trước TP. Không áp News Guard (không có lịch tin trước 2026).
- Giả định giờ server UTC+2/+3 theo giờ mùa hè Mỹ (như broker hiện tại); nguồn dữ liệu có thể là broker khác.
- Script: `research/long/long_study.py live | scalp | grid`.

## A. Cấu hình đang LIVE, không tối ưu (SWING, 2010–2025)

| Setup | Lệnh | R/lệnh | 2010–16 / 2017–20 / 2021–25 | Năm dương | Sụt giảm tối đa |
|---|---|---|---|---|---|
| S02 SWING (MARKET + LIMIT như live) | 949 | **−0,32** | −0,30 / −0,40 / −0,27 | 1/16 | 311R |
| S04 SWING | 157 | **+0,12** | +0,13 / +0,04 / +0,14 | 11/16 | 10R |
| S06 SWING (hộp 12, chờ xác nhận, 3R, cùng HTF) | 2.447 | **−0,01** | −0,05 / −0,04 / +0,06 | 7/16 | 109R |

Theo symbol: S02 âm ở cả 5; S04 dương ở GBPUSD (+0,28), USDJPY (+0,16), BTCUSD (+0,34), âm nhẹ EURUSD (−0,04), XAUUSD (−0,10); S06 trong khoảng −0,04..+0,04.

## B. SCALP ngoài mẫu (M5 06/2024–10/2025, không trùng dữ liệu G10)
- Cấu hình LIVE: S02 SCALP **−0,37R** (802 lệnh), S04 SCALP **−0,22R** (244 lệnh); âm ở cả hai nửa giai đoạn và mọi symbol.
- Lưới S01–S06 SCALP (chọn trên 06/2024–01/2025, kiểm trên 02–10/2025): **0 biến thể dương ở cả hai nửa** cho mọi setup.

## C. Lưới SWING (chọn trên 2010–2016, kiểm 2017–2020 và 2021–2025)

| Setup | Biến thể dương cả 3 giai đoạn | Tốt nhất trên 2010–16 → 2017–20 / 2021–25 |
|---|---|---|
| S02 | 0 / 430 | +0,06 → −0,16 / −0,17 |
| S03 | 0 / 32 | −0,02 → −0,13 / −0,07 |
| S04 | 21 / 270 | +0,10 → +0,01 / −0,04 (cấu hình live +0,12 ổn định hơn) |
| S05 | 0 / 128 | −0,02 → −0,07 / −0,04 |
| S06 | 4 / 87 | **hộp 24, vào ngay nến thoát, SL mép xa, TP 3R, không lọc HTF: +0,24 → +0,31 / +0,29** (69 / 42 / 60 lệnh) |

## Kết luận
1. **S02 không có lợi thế** ở cả SWING và SCALP, trên 16 năm và mọi symbol: âm ổn định khoảng −0,3R/lệnh. Kết luận của G10 được xác nhận trên dữ liệu độc lập, dài gấp 6 lần.
2. **SCALP của mọi setup đều âm** sau chi phí (xác nhận lần 2, giai đoạn độc lập).
3. **S04 SWING (cấu hình live) là setup duy nhất dương ổn định**: +0,12R, dương ở cả 3 giai đoạn, sụt giảm nhỏ; mẫu nhỏ (khoảng 10 lệnh/năm trên 5 symbol).
4. **S06 cấu hình live (hộp 12, chờ xác nhận) ≈ 0R trên 16 năm**: lợi thế +0,10R của G10 phản ánh giai đoạn 2020–2025, không bền. Biến thể **hộp 24, vào ngay** dương ở cả 3 giai đoạn (+0,24..+0,31R) nhưng chỉ 171 lệnh/16 năm; cần forward trước khi tin.
5. S01/S03/S05 không có lợi thế; không đưa vào EA.

## Đề xuất (quyết định của người dùng)
- S02: SHADOW (cả SCALP và SWING).
- S04: SWING giữ LIVE; SCALP sang SHADOW (cần thêm chế độ theo khung, vì `InpS04Mode` áp cho cả hai khung).
- S06: cấu hình hiện tại sang SHADOW; thêm biến thể "hộp 24, vào ngay" ở SHADOW để forward.
- Sổ candidate (G18) vẫn ghi mọi candidate SHADOW nên không mất số liệu.
