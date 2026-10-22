# G148 — bản đồ rủi ro 7 tầng (22/10/2026)

Kế hoạch đăng ký trước: [2026-10-22-g148-layered-risk-map.md](../plans/2026-10-22-g148-layered-risk-map.md). Script
[`g148_layered_risk_map.py`](../../research/long/g148_layered_risk_map.py). Bảng đầy đủ của 147 trạng thái: `results/g148/layered.json`.

Vũ trụ: mọi nến M30 vàng từ 05/2018, mua và bán, SL 1,5 ATR / TP 3 ATR / ≤ 24 giờ, chi phí harsh, tổng 187.006 lệnh. Không lọc:
- kỳ chọn: −0,16 (mua) / −0,23 (bán);
- 2022–23: −0,15 / −0,14;
- 2024–26: +0,04 / −0,13.

## Kết quả

**Không tầng nào chọn được trạng thái** (cần cùng dấu ở mọi ô năm × chiều của 2018–2021, |Δ| ≥ 0,03R, ≥ 5% số lệnh). Hệ thống vì vậy là
vũ trụ không lọc: validate −0,118R, test −0,070R, p 0,61. **KHÔNG ĐẠT.**

## Bản đồ: trạng thái tác động mạnh nhất mỗi tầng và vì sao không ổn định

Δ = R của lệnh có trạng thái − R của lệnh không có. Thứ tự 8 ô: 2018 mua, 2018 bán, 2019 mua, 2019 bán, 2020 mua, 2020 bán, 2021 mua,
2021 bán.

| Tầng | Trạng thái | Δ trung bình | Ô âm | Ghi chú |
|---|---|---|---|---|
| Nến | biên độ nến "bùng" (> 1,5 ATR) | +0,039 | 2/8 | đổi dấu 2019 bán, 2021 mua |
| Nến | râu từ chối ngược chiều lệnh | +0,027 | 1/8 | gần ổn định nhưng nhỏ (< 0,03) |
| Indicator | RSI > 70 theo chiều lệnh | +0,074 | 3/8 | ±0,2–0,36 tùy năm: rất bất ổn |
| Indicator | kéo căng > 2 ATR khỏi EMA20 | +0,050 | 3/8 | như RSI |
| Bối cảnh | EMA200 H4 ngược chiều lệnh | +0,028 | 3/8 | 2018–19 xấu, 2020–21 tốt: đổi theo chế độ thị trường |
| Bối cảnh | D1 SMA50/200 cùng chiều | −0,028 | 4/6 | 2020 không có ô ngược |
| Volume/biến động | ATR cao | +0,058 | 1/8 | gần ổn định (như G147); một nửa là chi phí |
| Volume/biến động | ATR thấp | −0,029 | 5/8 | |
| Price action | quét đỉnh / đáy hôm qua rồi quay về theo chiều lệnh | +0,051 | 1/8 | **gần ổn định nhất** của tầng (chỉ 2018 bán âm) |
| Price action | đang retest mức vừa phá (P7 "không" = +0,085) | | 1/8 | retest đỉnh / đáy hôm qua là chỗ xấu, nhưng chỉ 2% số lệnh |
| Thời gian | Thứ Tư | −0,058 | 6/8 | gần là "tránh" nhưng hai ô dương |
| Thời gian | ngày Fed / NFP | | 4/8 | ±0,3–0,45: rất bất ổn |
| Phân phối/FOMO | giá cách EMA200 D1 0–1 ATR (sát EMA200 D1) | **−0,178** | **7/8** | **tác động xấu mạnh nhất và gần ổn định nhất**: lệnh ngay sát EMA200 D1 kém |
| Phân phối/FOMO | ngược phía EMA200 D1 | +0,218 | 3/8 | lớn nhưng chỉ 2019 bán–2021: theo chế độ |

## Kết luận

1. Với cách vào lệnh "mọi nến", **không có điều kiện nào trong 147 trạng thái của 50 yếu tố có tác dụng ổn định**. Các tác động lớn nhất
   (RSI, kéo căng, ngày Fed / NFP, phía EMA200 D1) đều đổi dấu theo năm. Đây là bằng chứng mạnh nhất từ trước tới giờ cho điều các nghiên
   cứu trước gặp: thị trường vàng không có "yếu tố tốt cố định", chỉ có yếu tố tốt trong một chế độ.
2. Ba ứng viên "gần ổn định", nên đo lại ở G149 (hành vi lặp lại):
   - **sát EMA200 D1 (0–1 ATR D1) là vùng xấu** (7/8 ô);
   - **quét đỉnh / đáy hôm qua rồi quay về là điểm vào tốt hơn** (7/8 ô);
   - **biến động cao tốt hơn, biến động thấp tệ hơn** (như G147).
3. Gợi ý của người dùng (tư duy ngược: tìm hành vi giá lặp lại để đặt điểm vào và điểm chốt) phù hợp với kết quả này hơn việc tìm thêm
   điều kiện lọc.
