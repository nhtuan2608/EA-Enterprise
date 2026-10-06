# G38: dây chuyền tìm setup mới và danh mục cho FTMO / CUSTOM (06/10/2026)

Yêu cầu người dùng (06/10): dựng và tìm ra một hoặc nhiều bộ setup hiệu quả, dùng được cho FTMO hoặc mode CUSTOM;
quan trọng nhất là quản lý được vốn, lời tốt và ổn định. Chỉ dữ liệu MT5 (đã có: 5 symbol H1/H4/D1 2010–2025,
8 cặp mới H1/H4 2024–2026).

## Bối cảnh từ G23–G37

- Lợi thế hiện có: S06B (co hẹp → bung, lọc USD; p < 0,001 so với ngẫu nhiên), S04 (biên, p ≈ 0,05).
- Không thêm được lợi thế bằng bộ lọc, điểm dự đoán, SL/TP, khung H4, hay cặp tiền khác (G27, G33, G35, G36).
- Lãi gần đây đến từ các xu hướng lớn (BTC, XAU, JPY); kiểu phá vỡ ngắn hạn trên EURUSD/GBPUSD đã mờ từ 2021.
  ⇒ Ứng viên có cơ sở nhất: **bám xu hướng dài hơn** (D1/H4, trailing) và **đảo về trung bình trong vùng đi ngang**,
  hai kiểu bù nhau.

## Họ setup ứng viên (mỗi họ ≤ ~40 bộ tham số)

| Mã | Ý tưởng | Vào lệnh | Thoát |
|---|---|---|---|
| T1 | Phá kênh Donchian D1 (kiểu turtle) | đóng nến D1 vượt đỉnh/đáy N ngày | dừng k·ATR, trailing ATR, không TP |
| T2 | Phá kênh H4 cùng xu hướng D1 | đóng H4 vượt đỉnh/đáy N nến, D1 cùng phía EMA | dừng k·ATR, trailing |
| T3 | Hồi trong xu hướng (H1) | D1 xu hướng + RSI(2) H1 quá bán/quá mua | dừng ATR, TP R cố định, hết giờ |
| T4 | Đảo về trung bình khi đi ngang (H1) | ADX thấp + đóng ngoài dải Bollinger | dừng ATR, TP R nhỏ, hết giờ |
| T5 | Phá vùng phiên Á (London) | đóng H1 vượt vùng 00–07 UTC sau 07 UTC | dừng phía kia vùng, TP R, hết ngày |
| T6 | Bám xu hướng theo đà (D1) | đà N ngày dương/âm, đổi chiều theo tuần | trailing ATR |

## Bộ lọc chống khớp quá mức (mọi họ, giống nhau)

1. Chọn tham số **chỉ trên 2010–2016**; 2017–2020 và 2021–2025 chỉ kiểm chứng (phải dương cả hai).
2. Thắng **vào lệnh ngẫu nhiên** cùng dừng lỗ/thoát lệnh: p < 0,05 (điều chỉnh theo số họ đã thử).
3. **Láng giềng tham số**: ≥ 60% bộ quanh bộ chọn dương cả 3 giai đoạn.
4. **Ngoài mẫu theo symbol**: không âm có ý nghĩa trên 8 cặp mới (2024–2026).
5. **Chi phí xấu hơn**: phí ×2 và trượt 0,1R vẫn dương.
6. Không phụ thuộc một symbol (bỏ từng symbol vẫn dương).

## Danh mục và quản lý vốn

- Ghép S06B + S04 + các setup đạt; tương quan lợi nhuận theo tháng giữa setup.
- Phân bổ rủi ro: bằng nhau theo setup, và theo nghịch đảo độ biến động; trần rủi ro mở, chốt lỗ ngày/tuần như EA.
- Mô phỏng: FTMO 1-Step, 2-Step (theo vòng), CUSTOM (tài khoản cá nhân, ngưỡng dừng −10% từ đỉnh), có kiểm tra dư địa,
  gap, bootstrap theo tháng. Chọn mức rủi ro theo: xác suất vượt / thời gian, năm tệ nhất, DD p90.

## Bước triển khai sau nghiên cứu

Setup đạt → engine trong EA ở SHADOW (cùng sổ candidate, `edge_monitor`) → demo LIVE → chỉ nâng rủi ro khi forward khớp.
