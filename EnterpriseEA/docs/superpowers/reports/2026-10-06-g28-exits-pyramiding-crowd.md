# G28: gồng lệnh, bồi lệnh, hành vi đám đông và chuỗi thua (06/10/2026)

Câu hỏi của người dùng (06/10): ngoài đường giá và setup, có nên dùng xác suất thống kê cho việc
gồng lệnh dương, bồi lệnh theo trend, cung/cầu, FOMO/tham lam, cay cú gỡ lệnh? Ràng buộc: **chỉ dữ liệu MT5**,
không tải nguồn ngoài.

Dữ liệu: SWING H1 2010–2025, 5 symbol, cùng mô hình G23/G27 (spread, phí, Trade Manager). Chọn chỉ trên
2010–2016; 2017–2020 và 2021–2025 để kiểm chứng. Script: `research/long/exits.py`, `research/long/crowd.py`;
tick volume lấy từ cột `<TICKVOL>` của file MT5 (`convert_raw.py --tickvol`).

## 1. Lệnh chạy được bao xa (chỉ dừng lỗ ban đầu, 240 nến)

| Setup | Lệnh | ≥1R | ≥2R | ≥3R | ≥5R | ≥8R | ≥3R khi đã ≥1R |
|---|---|---|---|---|---|---|---|
| S04 | 157 | 55% | 36% | 25% | 13% | 6% | 47% |
| S06B | 171 | 56% | 39% | 30% | 15% | 5% | 55% |
| S06B lọc USD | 131 | 59% | 42% | 32% | 15% | 5% | 55% |

Có "đuôi dày" vừa phải: khoảng 1/7 số lệnh chạy quá 5R, nhưng hiếm khi quá 8R. Gồng vô hạn không đáng;
chốt 3–4R hợp lý.

## 2. Quy tắc thoát lệnh (667 quy tắc × không bồi / bồi ở +1R / bồi ở +2R)

Bộ mô phỏng thoát lệnh khớp tuyệt đối với replay hiện tại (sai lệch 0 R) trước khi thử biến thể.

- **S04**: TM hiện tại (hòa vốn 1R, chốt 33% ở 1,5R, trail cấu trúc từ 2R) đã là lựa chọn tốt; không
  quy tắc nào tốt hơn đều ở cả 3 giai đoạn. Giữ nguyên.
- **S06B**: chốt 4R thay vì 3R và bỏ hòa vốn làm R tăng nhưng DD theo R cũng tăng; không "trung đạo".
- **Bồi lệnh** (thêm 1 phần rủi ro khi lệnh đã lãi, cả hai lệnh dời dừng lỗ về điểm vào đầu tiên, nên
  rủi ro đang mở không bao giờ vượt 1 phần):

| Setup | TM hiện tại (train / validate / test) | + bồi ở +2R | + bồi ở +1R |
|---|---|---|---|
| S04 | +0,125 / +0,041 / +0,142 | +0,070 / +0,041 / +0,109 | +0,096 / +0,174 / +0,008 |
| S06B lọc USD | +0,318 / +0,303 / +0,390 | +0,350 / +0,355 / +0,455 | **+0,444 / +0,437 / +0,696** |

Bồi lệnh chỉ có ích cho S06B (setup phá vỡ có quán tính), không có ích cho S04 (setup đảo chiều). Với
S06B nó cải thiện đều cả 3 giai đoạn.

## 3. Tài khoản FTMO 1-Step (10.000 USD, 0,3%/lệnh)

| Phương án | %/năm | DD tối đa | Ngày tệ nhất | Năm dương | Vi phạm FTMO |
|---|---|---|---|---|---|
| S04 + S06B lọc USD, TM hiện tại (G27) | +1,08% | 2,5% | −0,58% | 11/16 | không |
| + bồi lệnh S06B ở +2R | +1,18% | 2,5% | −0,58% | 12/16 | không |
| S06B chốt 4R + trail, bồi +2R | +1,36% | 2,6% | −0,58% | 11/16 | không |
| **+ bồi lệnh S06B ở +1R** | **+1,49%** | **2,7%** | −0,58% | **14/16** | không |
| Quy tắc xếp hạng cao nhất trên train (tham khảo) | +1,51% | 4,6% | −0,79% | 12/16 | không |

## 4. Hành vi đám đông từ dữ liệu MT5

Đặc điểm lúc vào lệnh: tick volume tăng vọt / thấp, giá đã chạy xa EMA50 > 2 ATR (đuổi giá),
chuỗi ≥4 nến cùng chiều / ngược chiều, RSI quá nóng, nến lớn > 2 ATR.

- **S04, S06B, S06B lọc USD**: không đặc điểm nào tốt hơn đều ở cả 3 giai đoạn. Có những đặc điểm đẹp ở
  một giai đoạn (ví dụ S06B "đuổi giá" +0,64R ở test) nhưng âm ở giai đoạn khác: là nhiễu, không dùng.
- **S06 cũ**: "volume tăng + không đuổi giá" tốt hơn đều nhưng chỉ +0,06 đến +0,13R/lệnh, quá mỏng.
- **S02**: không đặc điểm nào làm S02 dương bền vững.
- Ý nghĩa: với dữ liệu MT5 (tick volume chỉ là số lần giá nhảy, không phải khối lượng thật), các thước đo
  FOMO/tham lam không thêm được lợi thế ổn định cho các setup đang có lợi thế.

## 5. Chuỗi thua và "cay cú gỡ lệnh"

| Chuỗi lệnh | Tỷ lệ thắng | Sau 0 thua | Sau 1 thua | Sau 2 thua | Sau 3+ thua | Runs z |
|---|---|---|---|---|---|---|
| S04 | 46% | +0,041 | +0,155 | +0,310 | +0,093 | +0,49 |
| S06B lọc USD | 57% | +0,415 | +0,253 | +0,549 | −0,160 (n=12) | −0,38 |
| Danh mục S04 + S06B lọc USD | 51% | +0,242 | +0,176 | +0,180 | +0,230 | +0,13 |

Thứ tự thắng/thua không khác ngẫu nhiên (|z| < 2): các lệnh độc lập. Vì vậy tăng lot để gỡ sau chuỗi thua
chỉ là martingale (tăng rủi ro cháy, không tăng kỳ vọng); giảm lot sau chuỗi thua cũng không có cơ sở.
Giữ rủi ro cố định và các chốt chặn ngày 1,2% / tuần 2,4% hiện có là đúng.

## Kết luận và đề xuất (chờ người dùng quyết)

1. Thay đổi đáng làm duy nhất: **bồi lệnh cho S06B** khi lệnh đã lãi +1R (bản an toàn hơn: +2R), cả hai lệnh
   dừng lỗ ở điểm vào đầu tiên. Tài khoản: +1,08% → +1,49%/năm, DD 2,5% → 2,7%, năm dương 11 → 14/16.
2. Giữ TM hiện tại cho S04 và S06B; không thêm bộ lọc đám đông; không thay đổi khối lượng theo chuỗi thắng/thua.
3. Lưu ý: mẫu nhỏ (S06B lọc USD 131 lệnh/16 năm). Bồi lệnh cần sửa EA: hiện EA chặn lệnh thứ hai cùng
   symbol/cùng chiều (`DUPLICATE_SAME_SIDE`). Nên đưa vào SHADOW trước (ghi "lệnh bồi ảo" vào log S06B),
   forward cùng cờ USD rồi mới cho LIVE.
