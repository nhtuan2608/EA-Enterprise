# G149 — bản đồ hành vi lặp lại → điểm vào / điểm chốt (22/10/2026)

Kế hoạch đăng ký trước: [2026-10-22-g149-repeating-behaviour.md](../plans/2026-10-22-g149-repeating-behaviour.md) (commit `f25e100`). Script
[`g149_repeating.py`](../../research/long/g149_repeating.py). Vàng M30 từ 05/2018, chi phí harsh.

## Phần 1 — quy luật lặp lại (tỷ lệ theo từng năm 2018 → 2026)

| Quy luật | Tỷ lệ mỗi năm | Ổn định? |
|---|---|---|
| Chạm đỉnh hôm qua / chạm đáy hôm qua / chạm cả hai | 45–59% / 37–50% / 9–13% | rất ổn định |
| Thủng đỉnh (đáy) hôm qua → đóng ngày lại trong biên | 41–59% / 44–62% | quanh 50%: **như tung đồng xu** |
| Phá biên phiên Á (00–09) sau 09:00 | **92–100%** | rất ổn định |
| Đã phá đỉnh (đáy) Á → quay lại trong biên trước 22:30 | **80–92%** | rất ổn định: **phá biên Á gần như luôn bị kéo lại** |
| Giá cách VWAP ngày ≥ 1,5 ATR → đi thêm 1 ATR trước / chạm lại VWAP trước | **54–71%** / 25–38% | rất ổn định: **giá xa VWAP thường chạy tiếp, không quay về** |
| Lệnh đã đi +1 ATR → tới +2 ATR trước khi về lại giá vào (≤ 24 giờ) | **28–31%** | rất ổn định: **khoảng 70% lệnh đã lời 1 ATR quay về giá vào trước khi lời 2 ATR** |
| Giờ hình thành đỉnh / đáy ngày | đỉnh: 01 giờ (9%), 15–17 giờ (25%); đáy: 01 giờ (12%), 15–17 giờ (25%) | ổn định (giờ mở phiên Á và mở cửa Mỹ) |

## Phần 2 — 6 ô lệnh

| Ô | Lựa chọn (chọn trên 2018–21) | Kỳ chọn | Validate | Test | Tỷ lệ thắng / chạm TP | p | Kết luận |
|---|---|---|---|---|---|---|---|
| K1 quét đỉnh/đáy hôm qua rồi quay về | TP giữa biên hôm qua | −0,187 | −0,249 | −0,195 | 30% / 22% | 0,87 | **KHÔNG ĐẠT** |
| K2 phá biên Á rồi quay về | TP biên Á đối diện | −0,286 | −0,194 | −0,252 | 30% / 22% | 0,71 | **KHÔNG ĐẠT** |
| K3 hồi trong nhịp mạnh (limit 0,382) | f 0,382 | −0,187 | −0,165 | −0,107 | 47% / 45% | 0,90 | **KHÔNG ĐẠT** |
| K4 giá xa VWAP | ngược về VWAP | −0,259 | −0,280 | −0,143 | 32% / 27% | 0,85 | **KHÔNG ĐẠT** |
| W1 phá đỉnh/đáy tuần trước (swing) | không TP | −0,021 | +0,053 | +0,148 | 49% | 0,19 | **KHÔNG ĐẠT** (mua +0,32, bán −0,16; tháng không tăng −0,19) |
| W2 quét đỉnh/đáy tuần trước rồi quay về | TP giữa biên tuần | −0,063 | −0,384 | −0,124 | 38% / 36% | 0,91 | **KHÔNG ĐẠT** |

Hai gợi ý của G148 (bỏ vùng sát EMA200 D1, bỏ ATR thấp) làm các ô bớt âm 0,02–0,08R, nhưng không ô nào thành dương.

## Kết luận

1. **Hành vi lặp lại có thật và rất ổn định qua mọi năm**: biên Á bị phá rồi kéo về 80–92%; giá xa VWAP chạy tiếp 54–71%; 70% lệnh đã lời
   1 ATR quay về giá vào trước khi lời 2 ATR; đỉnh / đáy ngày hay hình thành lúc 01 giờ và 15–17 giờ server.
2. **Nhưng "lặp lại" không tự thành lợi nhuận.** Mọi cách đặt lệnh theo các quy luật đó đều âm sau chi phí, không hơn vào lệnh ngẫu nhiên.
   Lý do: tỷ lệ lặp lại cao luôn đi kèm phần thưởng nhỏ hoặc stop gần. Ví dụ: biên Á bị kéo lại 85%, nhưng chỉ 22% lệnh chạm TP trước
   SL. Thị trường "định giá" đúng xác suất của các hành vi quen thuộc.
3. **Giá trị dùng ngay là danh sách "đừng làm"**, mỗi điều có tỷ lệ ổn định 8–9 năm:
   - **đừng đuổi theo cú phá biên phiên Á** (80–92% bị kéo lại);
   - **đừng bắt giá quay về VWAP khi đã xa ≥ 1,5 ATR** (chỉ 25–38% quay về; phần lớn chạy tiếp);
   - **đừng đặt stop sát quanh 01 giờ và 15–17 giờ server** (đỉnh / đáy ngày thường hình thành lúc đó);
   - **đừng kỳ vọng lệnh trong ngày đã lời 1 ATR sẽ đi tiếp tới 2 ATR**: chỉ khoảng 30%. Đây là lý do các setup trong ngày cần chốt sớm
     hoặc có lợi thế vào lệnh rất rõ. Với S07 (đà sau nén, giữ nhiều ngày), G135 đã cho thấy cách thoát hiện tại gần tối ưu, nên không áp
     điều này vào S07.
4. W1 (phá đỉnh / đáy tuần trước) dương ở 2022–2026 nhưng chỉ nhờ lệnh mua trong chu kỳ tăng, kỳ chọn âm, p 0,19. Cùng mẫu hình của mọi
   ứng viên trước.
