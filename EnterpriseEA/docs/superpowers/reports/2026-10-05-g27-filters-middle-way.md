# G27: bộ lọc liên thị trường và chế độ thị trường, tìm "trung đạo" (05/10/2026)

Mục tiêu (người dùng, 05/10): ăn ít nhưng đều, ít rủi ro. Tiêu chí chọn: kỳ vọng dương, nhiều năm dương,
sụt giảm thấp, rồi mới tới lợi nhuận.

## Cách làm

- Tín hiệu gốc: SWING H1, 5 symbol, 2010–2025 (cùng mô hình G23: spread, phí ước tính, Trade Manager).
  S04, S06 (cấu hình cũ), S06B (hộp 24, vào ngay, 3R), S02 (MARKET), S02INV (đánh ngược cú phá, dừng 1,5 ATR, 2R).
- Bộ lọc chỉ dùng thông tin có trước lúc vào lệnh:
  - `ADX_LOW` ADX14 H1 < 20; `ADX_HIGH` > 25
  - `D1_TREND` cùng phía EMA200 của nến ngày đã đóng
  - `USD_FLOW` cùng chiều dòng USD: chỉ số USD tự dựng từ EURUSD, GBPUSD, USDJPY so với EMA50 H1
    (DXY thật chỉ có từ 09/2021 nên dùng để đối chiếu 2021–2025)
  - `VOL_MID` ATR không nằm ở 1/3 thấp nhất hay cao nhất
  - US10Y chỉ có từ 2024: quá ngắn, không dùng.
- Mỗi bộ lọc đơn và mọi cặp, áp cho cả 5 symbol và từng symbol. Chọn chỉ trên 2010–2016;
  2017–2020 và 2021–2025 chỉ để kiểm chứng. So với việc bỏ ngẫu nhiên cùng số lệnh (phân vị 90).
- Script: `research/long/filters.py`, `research/long/middle_way.py`.

## Kết quả bộ lọc (R trung bình mỗi lệnh)

| Setup | Không lọc: train / validate / test | Bộ lọc đáng chú ý | Nhận xét |
|---|---|---|---|
| S04 | +0,13 / +0,04 / +0,14 | ADX_HIGH: +0,22 / +0,26 / +0,06 | Không bộ lọc nào ổn định cả 3 giai đoạn; giữ nguyên S04 |
| S06B | +0,24 / +0,31 / +0,29 | **USD_FLOW: +0,32 / +0,30 / +0,39**, 88% số năm dương | Duy nhất cải thiện đều cả 3 giai đoạn; DXY thật 2021–2025 xác nhận (+0,37) |
| S06 | −0,05 / −0,04 / +0,06 | GBPUSD ADX_LOW+VOL_MID: +0,50 / −0,45 / +0,18 | Bộ lọc nào thắng ở train cũng thua ở validate: khớp quá mức |
| S02 | −0,12 / −0,24 / −0,12 | VOL_MID: +0,20 / −0,16 / −0,01 | Không cứu được |
| S02INV | −0,11 / −0,07 / −0,03 | — | Đánh ngược cũng không có lợi thế sau phí |

Lưu ý trung thực: `USD_FLOW` trên S06B không vượt mốc ngẫu nhiên phân vị 90 ở giai đoạn train (mẫu nhỏ,
55 lệnh). Điểm mạnh của nó là nhất quán qua cả ba giai đoạn và được DXY thật xác nhận, chứ không phải
là bằng chứng thống kê mạnh.

## Mô phỏng tài khoản FTMO 1-Step (10.000 USD, rủi ro 0,3%/lệnh, giới hạn như G25)

| Phương án | Lệnh | %/năm | DD tối đa | Tháng dương | Tháng tệ nhất | Chuỗi tháng âm dài nhất | Năm dương | Vi phạm FTMO |
|---|---|---|---|---|---|---|---|---|
| S02+S04+S06 (cấu hình cũ) | 2893 | −5,31% | 61,4% | 36% | −3,05% | 18 | 3/16 | 12/2011 |
| Chỉ S04 (đang live) | 157 | +0,34% | 2,8% | 43% | −0,58% | 7 | 11/16 | không |
| S04 + S06B | 321 | +1,10% | 3,2% | 53% | −0,89% | 6 | 10/16 | không |
| **S04 + S06B lọc USD** | 283 | +1,08% | **2,5%** | 52% | −0,89% | 7 | 11/16 | không |
| Chỉ S06B lọc USD | 128 | +0,78% | 2,2% | 59% | −0,60% | 4 | 14/16 | không |

(Tháng dương tính trên các tháng có lệnh đóng.)

## Kết luận

1. "Trung đạo" rõ nhất: **S04 + S06B có lọc USD**. Lợi nhuận bằng S04 + S06B nhưng DD thấp hơn
   (2,5% so với 3,2%), 11/16 năm dương, không ngày nào lỗ quá 0,6%, không chạm giới hạn FTMO.
   S06B lọc USD đứng riêng là đều nhất (14/16 năm dương, chuỗi tháng âm dài nhất 4).
2. Bộ lọc không biến setup thua thành setup thắng: S02 và S06 cấu hình cũ vẫn âm sau mọi tổ hợp.
   Lọc chỉ có ích khi setup đã có lợi thế (S06B).
3. Mức sinh lời thật thấp: khoảng 1%/năm ở 0,3% rủi ro. Mục tiêu 10% của FTMO không đạt được ở mức
   rủi ro này; đây là phương pháp "an nhiên", không phải để vượt challenge nhanh.

## Đề xuất (chờ người dùng quyết)

- Thêm cờ `USD_FLOW` vào log shadow của S06B (chưa chặn lệnh), theo dõi forward 2–4 tuần cùng S04 live.
- Nếu forward khớp, chuyển S06B sang LIVE với bộ lọc USD.
- S02, S06 cũ: giữ SHADOW hoặc tắt hẳn; không đầu tư thêm bộ lọc cho hai setup này.
