# G135: TP / SL, điểm chốt lời và tiếp diễn hay đảo chiều sau khi vào lệnh — S07 ở M5 / M15 / M30 / H1 — kế hoạch đăng ký trước (21/10/2026)

## Vì sao

Người dùng muốn rà lại các setup ở mọi khung, **khung càng nhỏ càng tốt**. Lần này không chỉ tìm điểm vào, mà **train / validate cả cách thoát**:
- đặt TP và SL ở đâu;
- chốt lời ở đâu;
- khi lệnh đang **ngược sóng lớn** thì sóng sẽ **đảo chiều hay tiếp diễn**.

Mục tiêu là nâng cấp setup đang có hoặc tìm ra setup mới.

Tổng hợp G67–G134 cho thấy chỉ các họ setup vào theo đà sau nén có lợi thế, với S07 là lõi. Vì vậy G135 **giữ nguyên điểm vào S07** (luật G67 cuối: tín hiệu + B6) và chỉ thay **cách thoát**.

## Điểm vào (giống nhau cho mọi cách thoát)

Luật S07 theo G67 (`g67_timeframes.run`): tín hiệu nén → bung DMI + EMA, khối B6, SL ban đầu ở cực trị vùng nén ± 0,1 ATR, khoảng SL trong 1–4 ATR.

| Khung | Cửa sổ nén | Nghỉ sau lệnh | Giữ tối đa |
|---|---|---|---|
| M5 | 16 nến | 8 nến | 1.440 nến |
| M15 | 16 nến | 8 nến | 480 nến |
| M30 | 8 nến | 4 nến | 240 nến |
| H1 | 4 nến | 2 nến | 120 nến |

- Danh sách lệnh lấy từ cách thoát hiện tại (E2X + TP 8R). **Mọi cách thoát chạy trên cùng danh sách lệnh** đó, nên so sánh công bằng.
- **Chi phí**: spread khi vào/ra (lệnh bán đóng ở giá ask) + trượt 0,5 × spread trung vị mỗi chiều + phí như G67/G68.

**Nhãn sóng lớn** (tại nến tín hiệu):
- **cùng sóng**: trạng thái SMA50 / SMA200 của D1 đã đóng cùng chiều lệnh;
- **ngược sóng**: trạng thái D1 ngược chiều lệnh;
- trạng thái chưa rõ (SMA50 = SMA200 hoặc thiếu dữ liệu) để riêng.

## Các cách thoát (đăng ký trước)

| Mã | Cách thoát |
|---|---|
| CUR | hiện tại: E2X (đóng ngược EMA55, sang EMA100 sau 3R) + TP 8R |
| TP1 / TP1.5 / TP2 / TP3 / TP5 | TP cố định, không quản lý gì khác |
| BE3 / BE5 | dời SL về hòa vốn khi đạt +1R, TP 3R / 5R |
| TR1.5 / TR2.5 | từ +1R, trail theo ATR, giá tốt nhất − k × ATR, không TP |
| EMA21 | đóng khi nến đóng ngược EMA21, TP 8R |
| PART | chốt 50% ở 1,5R, phần còn lại như CUR |
| TIME | như CUR, nhưng đóng nếu sau 8 nến chưa từng đạt +0,5R |
| CTX | cùng sóng: CUR; **ngược sóng: TP 1,5R** (chốt nhanh) |
| LRN | **mô hình tiếp diễn / đảo chiều**, xem dưới |

**LRN** hoạt động như sau:
- Ở **nến đầu tiên đóng ≥ +1R**, mô hình LightGBM dự báo xác suất lệnh đạt **+3R trước khi quay về giá vào**.
- Dự báo ≥ 0,5 thì giữ như CUR; dưới 0,5 thì đóng ngay ở giá mở nến kế.
- Đặc trưng tại nến đó:
  - ADX và độ dốc ADX 3 nến, khoảng cách DI;
  - RSI14;
  - khoảng cách giá tới EMA21 và EMA55 (theo ATR), dải EMA có xếp thứ tự không;
  - cùng / ngược sóng D1, cùng / ngược phía EMA200 H4;
  - số nến từ lúc vào, khoảng SL theo ATR;
  - giờ UTC;
  - volume tương đối.
- Mô hình học **cuốn chiếu theo quý**: chỉ dùng các điểm kiểm tra của lệnh đã đóng trước đầu quý.

## Kỳ

| Khung | Train | Validate | Test |
|---|---|---|---|
| M30, H1 | 09/2018–2023 | 2024–06/2025 | 07/2025–10/2026 |
| M15 | 07/2021–2023 | 2024–06/2025 | 07/2025–10/2026 |
| M5 | 05/2024–02/2025 | 03–09/2025 | 10/2025–10/2026 |

- Kỳ test đã từng được xem cho **điểm vào** S07 (G67/G89) nhưng chưa từng dùng cho các **cách thoát** này. Đây là kiểm tra bán-sạch, sẽ ghi rõ trong báo cáo.

## Chọn và tiêu chí

- **Chỉ số mỗi cách thoát**: R/lệnh, tổng R, DD theo R (cộng dồn), **R-MAR** = tổng R ÷ DD.
- **Chọn** (riêng từng khung, và riêng cùng sóng / ngược sóng):
  - cách thoát có min(R-MAR train, R-MAR validate) cao nhất;
  - chỉ được chọn nếu **hơn CUR ở cả train và validate**.
- **Test**: cách thoát được chọn phải hơn CUR về R-MAR trên kỳ test, và tổng R test > 0.
- **Mô tả thêm**: ở mỗi khung và mỗi nhóm sóng:
  - tỷ lệ lệnh đạt +1R thì đi tiếp tới +3R;
  - tỷ lệ quay về giá vào;
  - MFE trung vị.

  Đây là câu trả lời trực tiếp cho câu hỏi tiếp diễn hay đảo chiều.
- Báo cáo **mua và bán riêng** cho cách thoát được chọn.

## Đầu ra

`research/long/g135_exits.py`, báo cáo `reports/2026-10-21-g135-exits-continuation.md`.
