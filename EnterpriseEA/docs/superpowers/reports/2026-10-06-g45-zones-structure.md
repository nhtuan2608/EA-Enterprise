# G45: vùng giá, cấu trúc thị trường, mô hình đảo chiều — kết quả (06/10/2026)

Kế hoạch: `docs/superpowers/plans/2026-10-06-g45-zones-structure.md`. Chỉ dữ liệu MT5. H1, 5 symbol 2010–2025, chọn trên 2010–2016; kiểm chứng 2017–2020 và 2021–2025; ngoài mẫu 16 symbol H1 2024–2026. Script: `research/long/g45_zones.py`, `g45_filters.py`; số liệu: `research/long/results/g45_*.md`.

## Kết luận

**Không khái niệm mới nào đạt đủ chuẩn để đưa vào EA.** Hai họ có dấu hiệu, đều là lợi thế xu hướng đã biết (giống T2), nhưng quá mỏng sau chi phí:

- **Z2 order block + phá cấu trúc (lọc xu hướng D1, thoát trail 3 ATR):** dương 3 kỳ (+0,20 / +0,03 / +0,20R), RR 3,7, thắng vào lệnh ngẫu nhiên (p < 0,001); nhưng phí ×2 + trượt 0,1R chỉ còn +0,01R, ngoài mẫu ≈ 0 (2.257 lệnh), không bộ láng giềng nào dương 3 kỳ.
- **Z5 Fibonacci OTE 61,8% (chân sóng ≥ 3 ATR, lọc D1, 2R):** dương 3 kỳ (+0,08 / +0,03 / +0,09R), **ngoài mẫu dương (+0,07R, 2.417 lệnh)**, p < 0,001; nhưng phí ×2 + 0,1R −0,05R, láng giềng 0/4.

Hai họ này vào danh sách theo dõi; không dựng engine lúc này.

## Từng họ (bộ chọn trên train)

| Họ | Bộ dương 3 kỳ | Train / Validate / Test (R) | Ngẫu nhiên p | Phí ×2 + 0,1R | Ngoài mẫu | Kết luận |
|---|---|---|---|---|---|---|
| Z1 Supply/Demand base → impulse | 0/16 | −0,09 / −0,14 / −0,22 | 0,11 | −0,30 | −0,32 | loại |
| Z2 Order block + BOS | 1/12 | +0,20 / +0,03 / +0,20 | <0,001 | +0,01 | −0,00 | theo dõi |
| Z3 Fair value gap | 0/16 | +0,09 / −0,09 / +0,03 | <0,001 | −0,12 | −0,03 | loại |
| Z4 Quét thanh khoản + CHoCH | 0/12 | +0,05 / −0,13 / −0,00 | 0,26 | −0,15 | −0,12 | loại |
| Z5 Fibonacci OTE | 1/16 | +0,08 / +0,03 / +0,09 | <0,001 | −0,05 | **+0,07** | theo dõi |
| Z6 Phân kỳ RSI | 1/12 | +0,08 / −0,01 / +0,05 | 0,06 | −0,08 | −0,14 | loại |
| Z7 Hai đáy / hai đỉnh | 0/8 | −0,03 / +0,02 / −0,01 | 0,08 | −0,12 | −0,02 | loại |

Mọi họ: bản có lọc xu hướng D1 tốt hơn bản không lọc — cùng thông điệp với G38/G43: lợi thế nằm ở **xu hướng**, không ở vùng hay mô hình đảo chiều.

## Vùng supply/demand làm bộ lọc

Với T2 và S06B, bộ lọc "còn khoảng trống tới vùng supply/demand ngược chiều" gần như không bao giờ kích hoạt: hai setup vào khi phá đỉnh/đáy kênh hoặc hộp, nên phía trước không còn vùng tươi. "Vào từ vùng demand" chỉ chiếm 0–2% lệnh. Với S04, lọc bỏ 1–3% lệnh và không hơn bỏ ngẫu nhiên (p 0,68–0,93). ⇒ Không thêm thông tin.

## Liên hệ với các phần đã có

- Flip zone (S02 phá + retest) đã âm trên 2010–2025 (G23); kết quả G45 cho vùng base/OB/FVG cùng chiều.
- Quét thanh khoản dạng S04 có lợi thế biên (G37); bản Z4 (quét swing + CHoCH, vào thị trường) không có.

## Bước tiếp

Không thay đổi EA từ G45. Nếu tiếp tục: thử Z2/Z5 với thoát trail và lọc tài sản xu hướng (như T2) như một nghiên cứu riêng có đăng ký trước, vì mỗi phép thử thêm làm giảm độ tin cậy.
