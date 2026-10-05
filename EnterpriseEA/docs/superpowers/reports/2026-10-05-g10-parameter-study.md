# G10: nghiên cứu tham số S02/S04 (05/10/2026)

## Phương pháp
- Dữ liệu: nến M5/H1/H4 của EURUSD, GBPUSD, XAUUSD, BTCUSD, USDJPY xuất từ MT5 (`research/bars_*.csv`), 01/01–04/10/2026.
- Công cụ: `research/g10` (Python). Bộ replay Python khớp với replay của EA: S02 497/497 candidate, S04 352/353; trạng thái và kết quả trùng khớp.
- Mô hình đánh giá "tm": spread ask/bid khi vào và thoát, Trade Manager như live (chốt 50% tại 1R, dời SL hòa vốn, trailing, thoát khi đóng xuyên vùng, time stop).
- Walk-forward: chọn tham số chỉ trên **train 01–06/2026**, báo cáo trên **test 07–10/2026**.
- Lưới: 54 biến thể engine × 72 biến thể lệnh cho mỗi setup/profile (tổng 15.552 tổ hợp). Biến thể lệnh gồm SL buffer, RR tối thiểu, TP cấu trúc hoặc cố định, lọc HTF, lọc giờ 07–20 UTC.

## Kết quả

| Nhóm | Tham số hiện tại (train / test, R mỗi lệnh) | Tốt nhất trên train → kết quả test |
|---|---|---|
| S02 SCALP | −0,15 / −0,36 (n 207 / 115) | −0,04 → **−0,30** (n 50) |
| S02 SWING | −0,31 / −0,60 (n 8 / 6) | +0,15 → **−0,30** (n 12) |
| S04 SCALP | −0,14 / −0,17 (n 130 / 70) | +0,04 → **−0,08** (n 67) |
| S04 SWING | +0,37 / +0,07 (n 5 / 3) | +0,80 → +1,36 (**chỉ 4 lệnh**) |

- S02 SCALP: 0/3.676 biến thể dương ở cả train và test. Biến thể tốt nhất trên test (không được phép chọn theo test) vẫn −0,15R.
- S04 SCALP: 3/2.511 biến thể dương ở cả hai giai đoạn, mức gần 0. Đó là nhiễu, không phải lợi thế.
- S04 SWING dương nhưng chỉ có 15 lệnh train và 4–5 lệnh test, không đủ để kết luận.
- Cửa sổ "quay lại trong vùng" của S04 (2/3/4 nến) không đổi kết quả: giá gần như luôn quay lại ngay nến kế tiếp hoặc phá vỡ được chấp nhận.

## Kết luận
Chỉnh tham số trong khuôn thiết kế hiện tại không tạo được lợi thế dương ngoài mẫu cho S02 và S04 khung SCALP. SWING có quá ít lệnh để đánh giá.

## Giới hạn
- Ghi chú 05/10: sweep chạy lại sau khi replay có commission (`f15915d`) và chỉ tính lệnh MARKET (`5eecfb1`) cho kết quả thấp hơn bảng trên 0,04–0,06R ở mọi nhóm (ví dụ S02 SCALP tốt nhất trên train −0,08 → test −0,36; S04 SCALP 0,00 → −0,11). Kết luận không đổi.
- Chưa mô phỏng lệnh LIMIT tại mép vùng của S02 (vào khi ARMED, cùng chiều HTF). Live S02 có dùng nhánh này.
- Chưa áp News Guard, sentiment, giới hạn phiên; chưa tính commission.
- Mô phỏng theo nến: trong một nến, chạm SL được tính trước TP.

## Phần 2 (phương án 3): nhánh LIMIT, chi phí, News Guard, setup mới

Bổ sung vào replay: nhánh LIMIT tại mép vùng của S02 (như live), commission ước tính (USD 6/lot khứ hồi cho FX và vàng, 0 cho BTC), News Guard từ lịch tin HIGH đã ghi (`news_reactions.jsonl`).

**S02/S04 với tham số hiện tại, mô hình đầy đủ (train 01–06 / test 07–10, R mỗi lệnh):**

| Nhóm | Chỉ MARKET | Chỉ LIMIT | Như live (MARKET + LIMIT) |
|---|---|---|---|
| S02 SCALP | −0,25 / −0,34 | −0,35 / −0,62 | −0,32 / **−0,53** |
| S02 SWING | −0,16 / −0,56 (n 4/5) | −0,57 / −1,02 | −0,47 / −0,88 |
| S04 SCALP | −0,15 / −0,22 | — | — |

**Prototype S01/S03/S05/S06** (`research/g10/setups.py`, 32–256 biến thể mỗi nhóm, chọn trên train):

| Nhóm | Biến thể dương ở cả train và test | Tốt nhất trên train → kết quả test |
|---|---|---|
| S01 Asian Range Break (SCALP) | 0 | −0,05 → +0,11 (n 39) |
| S03 PDH/PDL Break SCALP / SWING | 0 / 0 | −0,14 → −0,20 / +0,02 → −0,20 |
| S05 Trend Pullback SCALP / SWING | 0 / 8 | −0,12 → −0,15 / +0,26 → −0,14 |
| S06 Compression Expansion SCALP / SWING | 0 / 3 | −0,07 → −0,09 / +0,35 → −0,15 |

**Đối chứng vào lệnh ngẫu nhiên** (SL 1 ATR, TP 1,5R, cùng chi phí và Trade Manager):

| Khung | Không chi phí | Có spread + commission | Chi phí trung bình mỗi lệnh |
|---|---|---|---|
| M5 (SCALP) | −0,02R | **−0,24R** | **0,27R** |
| H1 (SWING) | −0,02R | −0,10R | 0,10R |

## Kết luận phần 2
1. Không setup nào (S01–S06) có lợi thế dương ổn định ngoài mẫu trên dữ liệu 01–10/2026.
2. Trên M5, spread và commission ăn khoảng 0,27R mỗi lệnh. Các setup SCALP (−0,15 đến −0,5R) ngang hoặc kém hơn vào lệnh ngẫu nhiên. Với stop cỡ 1–2 ATR M5, SCALP không có cửa thắng ở mức chi phí này.
3. SWING (H1) chịu chi phí thấp hơn nhiều (0,10R) nhưng 9 tháng dữ liệu chỉ cho vài chục lệnh mỗi setup, chưa đủ để kết luận.
4. Nhánh LIMIT của S02 làm kết quả tệ hơn.

## Hướng tiếp theo đề xuất
- Không dùng M5 cho vào lệnh. Nghiên cứu SWING H1/H4 trên lịch sử dài hơn (2023–2026) để đủ mẫu.
- Thêm `InpS02Mode` (OFF/SHADOW/LIVE) để chuyển S02 sang chỉ ghi nhận khi cần.

## Phần 3: SWING trên lịch sử dài (H1, vùng từ H4)

- Dữ liệu: H1/H4 của 5 symbol từ 20/02/2024 (giới hạn lịch sử của broker) tới 05/10/2026.
- Ba giai đoạn: chọn tham số trên 2024, kiểm tra trên 2025, kiểm chứng cuối trên 2026.
- Chi phí (spread + commission ước tính) và Trade Manager SWING có áp dụng. News Guard không áp (lịch tin chỉ có từ 2026).
- Đối chứng vào lệnh ngẫu nhiên (SL 1,5 ATR, TP 2R): −0,01 / −0,07 / −0,03 R mỗi lệnh.

| Setup | Biến thể dương ở cả 3 giai đoạn | Tốt nhất trên 2024 → 2025 / 2026 |
|---|---|---|
| S02 Break Retest | 0 / 453 | +0,06 → −0,19 / −0,14 |
| S03 PDH/PDL Break | 0 / 48 | −0,05 → +0,02 / −0,03 |
| S04 Failed Break | 0 / 66 | −0,07 → +0,00 / +0,37 (n ~30 mỗi giai đoạn) |
| S05 Trend Pullback | 16 / 192 | +0,22 → −0,05 / −0,01 |
| **S06 Compression Expansion** | **8 / 96** | **+0,12 → +0,02 / +0,21** |

### S06 SWING: cấu hình box 12 nến H1, box ≤ 3 ATR, ATR ≤ 0,85 × ATR 48 nến trước, vào lệnh ở nến xác nhận, SL ở mép xa của box, chỉ cùng chiều HTF, TP cố định 3R
- 550 lệnh, +0,10R mỗi lệnh (2024 +0,09 / 2025 +0,06 / 2026 +0,15), tỷ lệ thắng 51%, sụt giảm tối đa 22R. t ≈ 1,8: chưa có ý nghĩa thống kê chắc chắn.
- Theo symbol: EURUSD +0,14, GBPUSD +0,04, XAUUSD +0,42, USDJPY +0,16, **BTCUSD −0,07**.
- Lân cận tham số (box 8/12/16, box ≤ 2,5/3/4 ATR, co hẹp 0,75/0,85/0,95): **tất cả dương**, từ +0,06 đến +0,19R. Đây là dấu hiệu bền, không phải một điểm tối ưu cô lập.
- Theo quý: 7/11 quý dương.
- Bỏ lọc HTF: +0,09R. Không tính chi phí: +0,11R.

## Kết luận phần 3
- S02, S03, S04, S05 SWING không có lợi thế ổn định.
- S06 Compression Expansion trên H1 là ứng viên duy nhất: dương ở cả ba giai đoạn, ổn định quanh tham số lân cận, vượt đối chứng ngẫu nhiên khoảng 0,15R mỗi lệnh. Mức lợi thế nhỏ (+0,1R) và chưa chắc chắn về thống kê.
- Đề xuất: đưa S06 SWING vào EA ở chế độ SHADOW để kiểm chứng tiến tới (forward), không bật LIVE ngay.
