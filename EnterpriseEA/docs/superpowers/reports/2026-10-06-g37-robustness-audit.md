# G37: kiểm chứng độ bền nhiều chiều và chọn phương pháp (06/10/2026)

Chỉ dữ liệu MT5, SWING H1 2010–2025, 5 symbol, Trade Manager hiện tại, lệnh dừng lỗ gap khớp tại giá mở.
Công cụ: `research/long/robustness.py` (số liệu đầy đủ: `research/long/results/robustness_random_params_portfolio.md`), `box_walkforward.py`, `box_fine.py`, `edge_calibrate.py`; monitor: `research/g10/edge_monitor.py`.

## Kết luận

**Phương pháp chọn: M5 = S04 + S06B lọc USD + bồi +1R** (điểm bootstrap cao nhất 0,23, trong số phương án mà mọi setup đều thắng vào lệnh ngẫu nhiên). Khớp cấu hình G29/G31. Kỳ vọng thực tế khiêm tốn: khoảng +1–1,5%/năm ở 0,3%/lệnh, DD p90 ≈ 4%.

## Kết quả theo chiều

| Chiều | Kết quả | Đánh giá |
|---|---|---|
| Với vào lệnh ngẫu nhiên (2.000 lần) | S06B, S06B lọc USD, S06B+bồi: p < 0,001. S04: p ≈ 0,05–0,06 | S06B vững. **S04 chỉ ở biên**, chưa phải bằng chứng mạnh |
| Độ nhạy tham số | Chỉ 36% (S06B) và 44% (S04) bộ láng giềng dương cả 3 giai đoạn; trung vị láng giềng S06B ≈ +0,03..0,08R so với +0,30R của bộ đang dùng | **Có yếu tố khớp tham số**: lợi thế tập trung quanh hộp 24 |
| Walk-forward chọn hộp (2014–2025) | Hộp được chọn 23–26 mọi năm, kết quả +0,259R (n=110) so với cố định 24 là +0,396R và trung bình mọi hộp +0,135R | Lợi thế có thật nhưng **kỳ vọng nên lấy ≈ +0,15..0,26R**, không phải +0,34R |
| Bỏ từng symbol | Mọi trường hợp dương (+1,0..+1,5%/năm), 12–15/16 năm dương | Không phụ thuộc một symbol; XAUUSD đóng góp nhiều nhất |
| Bỏ 5 / 10 lệnh lời nhất | +1,13% / +0,78%/năm; xác suất lỗ cả kỳ 1% / 2% | Phụ thuộc vừa phải vào lệnh lớn |
| Phí ×2, trượt 0,1R/lệnh, cả hai | +1,42% / +1,04% / +0,97%; p10 bootstrap vẫn > 0 (+0,36%) | Chịu được chi phí xấu hơn |
| Bootstrap theo tháng | p10 +0,95%/năm, DD p90 4,2%, xác suất lỗ cả kỳ 0% | Đạt |
| Phần mềm | 58 file test Python đạt (thêm `edge_monitor_tests.py`), compile MetaEditor 0/0, terminal khớp byte với nhánh | Đạt |

## Điểm yếu cần theo dõi

1. S04 gần như không tách khỏi ngẫu nhiên; S04 một mình chỉ +0,34%/năm và 7% khả năng lỗ cả kỳ. Nó có giá trị chủ yếu như đa dạng hóa trong M5.
2. Tham số S06B nhạy (hộp 24). Không chỉnh thêm theo dữ liệu: walk-forward đã cho thấy chọn hộp động chỉ kém cố định, không cần.
3. Bồi lệnh vẫn mặc định TẮT (`InpS06BPyramidLive=false`); bật hay không là quyết định của người dùng.

## Giám sát sau khi chạy thật

`edge_monitor.py` (CUSUM giảm với k = TB/2, ARL0 ≥ 250 lệnh cho báo động, ≥ 60 cho cảnh báo; sụt vốn so p95/p99 nghiên cứu; cận trên 90% của R TB < 0 từ 20 lệnh) so lệnh thật và candidate ảo với tham số trong `edge_params.json`. Chỉ báo cáo; chuyển về SHADOW là quyết định của người vận hành.

## Bổ sung: lưới hộp mịn (`box_fine.py`, hộp 18–30 từng nến)

Lưới thô (bước 4 nến) rơi vào hộp 20 và 28, nằm ngoài vùng tốt, nên trông như một đỉnh đơn lẻ. Lưới mịn:
hộp 23 và 24 đều dương ở cả 3 giai đoạn (23: +0,33 / +0,32 / +0,26R; 24: +0,32 / +0,30 / +0,39R); vùng 21–26 dương
ở 2010–2016 và 2021–2025; riêng 2017–2020 chỉ dương ở 18–24. Đây là một vùng hẹp nhưng không phải một con số
đơn lẻ, và walk-forward luôn tự chọn 23–24 (một lần 26). Kết luận giữ nguyên: dùng hộp 24, kỳ vọng thận trọng
khoảng +0,15..0,26R mỗi lệnh.

## Cảnh báo qua Telegram (`bridge/telegram_gateway.py`)

- `/edge`: chạy `edge_monitor.py` (giới hạn 1 lần mỗi 10 phút) và trả kết quả từng dòng theo dõi.
- Kiểm tra hằng ngày lúc `edge_local` (mặc định 08:05 giờ máy, tắt bằng `notify.edge=false`): chỉ nhắn khi một
  dòng chuyển xấu hơn (OK → CẢNH BÁO/BÁO ĐỘNG, CẢNH BÁO → BÁO ĐỘNG), kèm đề xuất chuyển về SHADOW. Mỗi ngày một lần.
- Monitor chỉ báo; không tự đổi chế độ setup.

## Audit phần mềm (bổ sung)

- 640 test Python đạt (thêm test /edge, kiểm tra hằng ngày chỉ nhắn khi xấu hơn, báo động hiếm khi lợi thế còn
  nguyên: ≤ 10% sau 40 lệnh với trung bình và độ lệch như nghiên cứu, và bắt được phần lớn chuỗi 80 lệnh lỗ).
- Các bộ test gateway không còn chạy `edge_monitor.py` thật (không còn ResourceWarning).
- Chạy thật trên dữ liệu EA 06/10: monitor đọc sổ candidate và lệnh thật, ghi `current/edge_monitor.json` (chưa có
  lệnh nào từ 06/10).

## Kiểm tra rò rỉ dữ liệu tương lai (06/10, `research/long/leak_check.py`)

Cắt dữ liệu H1/H4/D1 tại 2015-06-01, 2019-03-01, 2023-09-01, 2025-06-01 (chỉ giữ nến đã đóng trước mốc), chạy lại code
nghiên cứu trong tiến trình mới, so tín hiệu với dữ liệu đầy đủ trước mốc: S04 (thời điểm, chiều, mốc dừng lỗ), S06B (và cờ
USD), T2 (thời điểm, chiều, dừng lỗ theo ATR). **0 tín hiệu thay đổi** trên 12 lần so (95–3.968 tín hiệu mỗi lần): tín hiệu
không dùng dữ liệu tương lai. Kết quả lệnh dùng nến sau điểm vào theo định nghĩa (dừng lỗ chạm trước TP trong cùng nến,
gap khớp ở giá mở).

Rò rỉ ở mức lựa chọn (không phải code), cần biết:
- Sàn spread lấy trung vị spread 2024+ (`convert_raw.py`): giả định chi phí dùng dữ liệu gần đây, thận trọng hơn là lạc quan.
- Bộ lọc `VOL_MID` (G27, không dùng) chia ngưỡng ATR theo toàn bộ lịch sử.
- Một số quyết định cấp phương pháp đã nhìn kết quả cả giai đoạn: chọn bồi +1R (G28), chọn M5 trong 6 phương án (G37), ý
  tưởng thử bám xu hướng sau khi thấy lãi gần đây đến từ xu hướng lớn (G36). Vì vậy kỳ vọng thực tế nên lấy mức thận trọng
  (walk-forward, bootstrap p10) và cần forward (shadow) trước khi tăng rủi ro.
