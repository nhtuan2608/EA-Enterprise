# G155: âm lịch và tiết khí có ảnh hưởng tới vàng / S07 không — kế hoạch đăng ký trước (24/10/2026)

## Vì sao

Người dùng hỏi (24/10): app Kinh Dịch Ching-Oracle có dùng được cho trading không?
- Quẻ gieo ngẫu nhiên không chứa thông tin giá, nên tương đương lệnh vào ngẫu nhiên. **Không test**, vì kết quả đã biết.
- Phần **âm lịch / tiết khí** thì xác định trước theo ngày, nên kiểm được đúng cách như một hiệu ứng lịch.

G147 đã thấy các hiệu ứng lịch dương (đầu/cuối tháng, thứ trong tuần) không có lợi thế. Khả năng đạt được đánh giá trước là thấp.

## Dữ liệu

- **Vàng theo ngày server**: 04/01/2010 → 09/10/2026, gộp từ `data/m30v/XAUUSD.csv` (trước 19/03/2018 file này là nến D1). ATR20 tính bằng
  trung bình 20 range ngày trước đó (không gồm hôm nay).
- **Sổ S07 M30** (bản Python G89 = `g136_p1p4.m30_book`), 05/2018 → 06/2026, R mỗi chân.
- **Âm lịch**: `lunar_python` (bản Python của `lunar-javascript` mà Ching-Oracle dùng), tính theo **ngày dương của ngày server**.

## Biến đo (3 mục tiêu)

| Mã | Mục tiêu | Ý nghĩa |
|---|---|---|
| T1 | (đóng − mở) / ATR20 của ngày | hướng giá trong ngày |
| T2 | (cao − thấp) / ATR20 | biến động trong ngày |
| T3 | R của chân S07 vào lệnh trong ngày đó | S07 có tốt/xấu hơn theo âm lịch không |

## Ô âm lịch (42 ô, cố định)

- **Pha trăng (4)**: ngày âm 1–7, 8–15, 16–22, 23–30.
- **Quanh sóc / vọng (2)**: ngày 29, 30, 1, 2 (trăng non); ngày 14, 15, 16 (trăng tròn).
- **24 tiết khí**: tiết khí gần nhất đã bắt đầu tính tới ngày đó.
- **12 tháng âm** (tháng nhuận gộp vào tháng cùng số).

## Phép thử

- Mỗi ô: Welch t, so trung bình trong ô với ngoài ô.
- **Đối chứng cả họ**: dịch vòng nhãn âm lịch theo k ngày giao dịch (k ngẫu nhiên, cách ít nhất 30 ngày), 2.000 lần. Mỗi lần ghi |t| lớn nhất
  trong 42 ô. Cách này giữ nguyên cấu trúc lịch nhưng cắt quan hệ với giá, và tự tính luôn việc thử nhiều ô.
- **p cả họ** = tỷ lệ lần dịch có |t| lớn nhất ≥ |t| lớn nhất thật.

## Đạt khi (từng mục tiêu)

1. p cả họ ≤ 0,0167 (0,05 / 3 mục tiêu);
2. ô mạnh nhất cùng dấu ở cả 3 kỳ: vàng 2010–2015 / 2016–2020 / 2021–06/2026; S07 05/2018–2021 / 2022–2023 / 2024–06/2026;
3. riêng T3, nếu dùng ô đó làm bộ lọc (bỏ ô âm, hoặc chỉ giữ ô dương) thì R/lệnh S07 tốt hơn không lọc ở cả 3 kỳ.

Kỳ sau (07–10/2026) chỉ báo cáo.

## Nếu đạt

Đề xuất SHADOW forward như một nhãn trong nhật ký bot, không đổi rủi ro. Người dùng đồng ý mới làm.

Script `research/long/g155_lunar.py`. Không chỉnh luật sau khi chạy.
