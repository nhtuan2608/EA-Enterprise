# G83: Phân biệt "mở biên một chiều" và "sideway" ở tín hiệu S07 — làm nền cho rủi ro 3% (kế hoạch đăng ký trước, 10/10/2026)

## Vì sao

Người dùng muốn đặt **3%/lệnh** cho các lệnh S07 mở biên lớn. Điều kiện là phải phát hiện sớm khi nào cú bung sẽ **đi một chiều**, và khi nào sẽ **đi ngang (sideway) rồi quét SL**:
- cả mua và bán;
- khung M15 / M30 / H1 / H4; M5 dùng để vào lệnh.

**Bối cảnh rủi ro:** lệnh gốc S07 M30 ở 1,5% có DD p90 1 năm 16% (G82, 2018–2026). Ở 3% cho mọi lệnh, DD sẽ gần gấp đôi, sát giới hạn lỗ tổng 30%. Vì vậy 3% chỉ khả thi cho một **nhóm con chất lượng cao**, và nhóm này **không bồi lệnh**.

## Dữ liệu và lệnh

- Tín hiệu S07 chuẩn (G68) ở M15 (W = 16), M30 (8), H1 (4), H4 (8).
- Mua có lọc H4 trên EMA200 (G79 đã xác nhận). Bán không lọc khung lớn (G79: lọc không có tác dụng).
- Thoát E2X, TP 8R, chi phí khắt khe G68, một lệnh mỗi lúc trên mỗi khung.
- M5 chỉ có từ 05/2024. Trong backtest, vào ở giá mở nến kế tiếp tương đương vào ở nến M5 đầu tiên sau khi nến tín hiệu đóng. Phần dùng M5 để vào sớm đã thử ở G73 (S07E đang ghi SHADOW).

## Đặc trưng tại nến tín hiệu (chỉ dùng dữ liệu đã đóng)

Tất cả tính theo chiều lệnh d.

| Nhóm | Đặc trưng |
|---|---|
| Nén | f1 số nến ADX < 20 trong 48 nến trước · f2 ADX đáy trong cửa sổ · f3 ATR hiện tại ÷ ATR trung bình 48–96 nến trước · f4 bề rộng vùng nén (đỉnh − đáy cửa sổ) ÷ ATR |
| Nến bung | f5 biên độ nến ÷ ATR · f6 thân ÷ biên độ · f7 vị trí giá đóng trong nến (theo chiều lệnh) · f8 bước nhảy khoảng cách DI so với nến trước |
| Dải EMA | f9 dải EMA xếp thứ tự (EMA21/55/100) · f10 (EMA21 − EMA100) ÷ ATR · f11 độ dốc EMA200 trong W nến ÷ ATR · f12 khoảng cách giá tới EMA200 ÷ ATR |
| Khung lớn | f13 dải EMA H4 xếp thứ tự cùng chiều · f14 ADX H4 · f15 D1 cùng phía EMA200 D1 |
| Volume | f16 tick volume tương đối ở nến bung · f17 tick volume tương đối trung bình trong vùng nén |
| **Các lần mở biên trước** | f18 số nến trong 2W nến trước đóng vượt dải EMA theo chiều lệnh rồi bị kéo về (lần bung hụt) · f19 số tín hiệu S07 cùng chiều trong 4W nến trước · f20 giá đóng vượt đỉnh/đáy 96 nến trước (phá biên lớn) |

Báo cáo thêm, không đưa vào điểm số: giờ UTC của tín hiệu.

## Cách làm (chống tự lừa)

1. **Đơn biến:** tương quan hạng (Spearman) của từng đặc trưng với R/lệnh trên **train** (gộp 4 khung, từng chiều). Báo cáo cùng dấu ở validate và test.
2. **Điểm số:**
   - Chỉ lấy các đặc trưng có tương quan train với p < 0,05.
   - Chuẩn hóa z theo trung bình / độ lệch của train từng khung. Điểm = Σ dấu × z.
   - Ngưỡng = **tam phân vị trên của train** từng khung, giữ cố định khi áp dụng cho validate / test.
3. **Nhóm "mở biên"** = lệnh có điểm ≥ ngưỡng.

## Tiêu chí (chốt trước, từng chiều)

**Nhóm mở biên đạt** khi, ở **validate và test, từng kỳ** (gộp 4 khung):
- R/lệnh ≥ 1,5 × R/lệnh của toàn bộ lệnh và ≥ +0,5R;
- tỉ lệ chạm SL thấp hơn toàn bộ lệnh.

**Rủi ro 3%** (chỉ khi nhóm mở biên đạt; sổ lệnh gốc M30, không bồi; hai giai đoạn 09/2018–06/2026 và 07/2021–06/2026):

| Phương án | Nhóm mở biên | Lệnh còn lại |
|---|---|---|
| P0 | 1,5% | 1,5% |
| P1 | 3% | 1,5% |
| P2 | 3% | bỏ |
| P3 | 3% | 3% (để thấy rủi ro) |

3% được chấp nhận (P1 hoặc P2) khi, ở **cả hai giai đoạn**:
- xác suất chạm 30% trong cửa sổ 1 năm ≤ 5%;
- DD p90 1 năm ≤ 25%;
- tỉ số %/năm ÷ DD p90 cao hơn P0.

Không đạt → giữ 1,5%, báo cáo trung thực.

## Đầu ra

`research/long/g83_expansion.py`, báo cáo `reports/2026-10-10-g83-expansion-vs-sideway.md`.
