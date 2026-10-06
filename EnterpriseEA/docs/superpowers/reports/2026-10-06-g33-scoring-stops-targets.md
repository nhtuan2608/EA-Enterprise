# G33: tăng xác suất vào lệnh và đặt SL/TP cho RR tốt hơn (06/10/2026)

Câu hỏi (06/10): có cách phối hợp hay dự đoán nào làm quyết định vào lệnh tốt hơn, hoặc đặt TP/SL hợp lý để
tăng RR? Chỉ dữ liệu MT5, SWING H1 2010–2025, chọn trên 2010–2016, kiểm chứng 2017–2020 và 2021–2025.
Script: `research/long/scoring.py`, `research/long/stops_targets.py`.

## 1. Điểm chất lượng lệnh (hồi quy logistic)

4.211 lệnh của S04, S06B, S06, S02; 14 đặc trưng có trước lúc vào lệnh (ADX, độ biến động, xu hướng D1, dòng
USD, cấu trúc H4, độ xa EMA50, RSI, phiên London/New York, thân nến, độ lớn nến, tick volume, khoảng trống tới
mức giá kế tiếp, độ rộng dừng lỗ). Học trên 2010–2016, chia ba mức điểm theo ngưỡng của 2010–2016.

| Setup | Điểm cao tốt hơn điểm thấp ở cả 3 giai đoạn | Bỏ 1/3 điểm thấp có thắng việc bỏ ngẫu nhiên không |
|---|---|---|
| S04 | Không (validate: điểm cao −0,52R, điểm thấp +0,43R) | Không |
| **S06B** | **Có** (1/3 thấp: −0,03 / +0,16 / +0,08R; 2/3 còn lại: +0,37 / +0,40 / +0,43R) | **Không** (ngẫu nhiên p90: +0,41 / +0,49 / +0,47R) |
| S06 | Không | Không |
| S02 | Không (validate, test: điểm cao còn tệ hơn) | Không |

Các đặc trưng chỉ có sức dự đoán yếu (hệ số lớn nhất: dừng lỗ rộng theo ATR → dễ thắng hơn nhưng RR thấp hơn;
nến vào lệnh quá lớn → thắng ít hơn). Với S06B, nhóm điểm thấp yếu hơn đều đặn nhưng chưa vượt mức nhiễu.
Kết luận: **chưa dùng để lọc**; có thể ghi điểm này vào log shadow của S06B để theo dõi.

## 2. Đặt SL/TP

**Lệnh tốt đi ngược bao xa (MAE)**: lệnh về sau chạm +2R thường chỉ đi ngược 0,33–0,35R (trung vị); 78–82%
không quá 0,75R. Nhìn qua thì nên siết dừng lỗ, nhưng thử trực tiếp thì không:

| Dừng lỗ (× hiện tại) | S04: train / validate / test | S06B lọc USD: train / validate / test |
|---|---|---|
| 0,6 | −0,03 / +0,06 / +0,11 | +0,19 / +0,12 / +0,49 |
| 0,75 | −0,06 / +0,05 / +0,12 | +0,10 / +0,12 / +0,47 |
| **1,0 (hiện tại)** | **+0,13 / +0,04 / +0,14** | **+0,32 / +0,30 / +0,39** |
| 1,25 | +0,01 / +0,06 / +0,13 | +0,16 / +0,11 / +0,39 |
| S06B dừng lỗ giữa hộp | – | +0,11 / +0,13 / +0,36 |

Siết dừng lỗ biến nhiều lệnh tốt thành lệnh thua (và dời hòa vốn quá sớm); nới dừng lỗ làm RR giảm. Dừng lỗ
theo cấu trúc hiện tại đã ở gần điểm tốt nhất. Tài khoản 0,3%: hiện tại +1,08%/năm, DD 2,5%; siết S06B ×0,9:
+0,99%, DD 3,1%; dừng giữa hộp: +0,76%, DD 2,9%.

**Chốt lời theo chế độ thị trường (ADX)**: chọn R mục tiêu riêng cho ADX thấp/giữa/cao trên 2010–2016 làm
train đẹp hơn (S04 +0,19, S06B +0,39) nhưng validate/test kém hơn chốt hiện tại: khớp quá mức, không dùng.

## Kết luận

Sau G27 (bộ lọc), G28 (gồng/bồi lệnh, đám đông), G33 (điểm dự đoán, SL/TP), chỉ hai thay đổi bền vững: **lọc
dòng USD** và **bồi lệnh +1R** cho S06B. Lợi thế của S04/S06B đã gần trần với dữ liệu giá MT5; dự đoán thêm hay
chỉnh SL/TP không tăng được một cách ổn định. Muốn lãi nhiều hơn mà vẫn đều, hướng có cơ sở hơn là **thêm lệnh
độc lập** (cùng setup trên nhiều symbol/khung hơn) thay vì cố chọn lệnh giỏi hơn:
- S06B và S04 trên khung H4 (dữ liệu H4 2010–2025 đã có);
- S06B trên thêm cặp tiền nếu xuất thêm dữ liệu từ MT5.
