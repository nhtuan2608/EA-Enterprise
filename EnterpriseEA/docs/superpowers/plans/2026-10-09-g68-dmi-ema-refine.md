# G68: Chau chuốt setup nén → bung DMI + EMA (XAUUSD M30) — kế hoạch đăng ký trước (09/10/2026)

## Vì sao

G67 (mục 7) cho thấy cùng quy tắc chạy trên **M30, cửa sổ nén 4 giờ (8 nến)** tốt nhất: dương ở 09/2018–07/2021 (chưa từng dùng), 2021–2023, 2024–06/2025, 07/2025–06/2026 và cả 07/2026–nay. Bản này được chọn sau khi xem 6 biến thể, nên cần kiểm tra độ bền trước, rồi mới chau chuốt. Người dùng muốn: thử từng thay đổi một, không gộp tất cả; giữ lệnh theo dải EMA mở rộng càng lâu càng tốt; rủi ro 1,5%/lệnh.

## Bản gốc C0 (không đổi)

XAUUSD M30. Nén: trong 8 nến trước ADX thấp nhất ≤ 20 và |+DI − −DI| ≤ 6 tại đó. ADX tăng và cách đáy ≤ 10. DI theo chiều và đang tách. Giá đóng hẳn về một phía 4 EMA 21/55/100/200. Cùng chiều EMA200 H4. Vào ở giá mở nến sau. SL đáy/đỉnh 8 nến − 0,1 ATR (1–4 ATR). Thoát khi nến đóng ngược EMA55, TP 8R, tối đa 240 nến. Nghỉ 4 nến sau mỗi lệnh. Chi phí: spread nến (sàn trung vị 2024–2025) + USD 6/lot.

## Kỳ

| Kỳ | Thời gian | Vai trò |
|---|---|---|
| Train | 20/07/2021 – 31/12/2023 | **quyết định** |
| Validate | 01/01/2024 – 30/06/2025 | **quyết định** |
| Trước | 01/09/2018 – 19/07/2021 | kiểm tra ngoài mẫu |
| Test | 01/07/2025 – 30/06/2026 | kiểm tra ngoài mẫu |
| Gần đây | 01/07/2026 – nay | chỉ báo cáo |

## Bước 1 — độ bền (cửa chặn: không đạt thì dừng, không chau chuốt)

1. **Lân cận:** ADX đáy {18, 20, 22} × độ chụm DI {4, 6, 8} × ADX tăng tối đa {8, 10, 12} × cửa sổ nén {6, 8, 10 nến} = 81 bộ. Đạt khi ≥ 60% bộ dương ở cả train và validate, và ≥ 60% bộ dương ở cả "trước" và test.
2. **Khớp lệnh khắt khe:** trượt thêm 0,5 × spread trung vị mỗi chiều vào/ra; spread ×3 khi vào hoặc ra trong 23:30–01:00 giờ server (chuyển ngày); commission ×2. Đạt khi R/lệnh > 0 ở toàn kỳ 2018–2026 và ở test.

## Bước 2 — chau chuốt, mỗi thay đổi thử riêng so với C0

| # | Thay đổi |
|---|---|
| R1 | Chỉ lệnh mua |
| R2 | Lệnh bán chỉ khi giá D1 dưới EMA200 D1 (mua giữ nguyên) |
| R3 | SL bỏ qua các nến trước khoảng trống > 6 giờ (cuối tuần/nghỉ) trong cửa sổ nén |
| R4 | Thoát khi cạn đà: EMA21 không còn dốc theo chiều lệnh (so 2 nến) **và** ADX ≤ đỉnh − 5 (thay cho EMA55) |
| R5 | Sau khi lãi ≥ 3R, chuyển thoát từ EMA55 sang EMA100 |
| R6 | Chặn ngày: sau 2 lệnh thua trong cùng ngày (UTC) thì nghỉ hết ngày |
| R7 | Chặn tuần: lỗ tuần ≥ 4R (6% ở 1,5%) thì nghỉ hết tuần |

Luật giữ: R1–R5 được giữ khi R/lệnh tăng ở **cả train và validate** và còn ≥ 50% số lệnh. R6–R7 (chặn rủi ro) được giữ khi DD p90 trong 1 năm ở 1,5% giảm ở train+validate gộp **và** tổng R không giảm quá 10%.

Gộp: xếp các thay đổi được giữ theo mức cải thiện trên train+validate; thêm lần lượt, mỗi lần chỉ giữ nếu train+validate vẫn tốt hơn bản trước đó. Không thử tổ hợp khác.

## Bước 3 — phương án tốt nhất

Báo cáo C0 và bản cuối ở mọi kỳ; thắng ngẫu nhiên (cùng số lệnh, chiều, khoảng dừng ATR, cách thoát) p < 0,01; khớp lệnh khắt khe; lân cận của bản cuối; rủi ro 1% / 1,5% (lợi nhuận/năm, DD, DD p90 1 năm, khả năng sụt 10% và 20%).

Danh mục: ghép bản cuối (1,5%) với S04 + S06B như G58 (0,5% × trọng số 0,65 / 1,00) trên 09/2018–10/2025: tương quan R theo ngày, DD và %/năm của danh mục có và không có setup này.

Không làm trong G68 (để sau, dễ khớp quá sát 4 ví dụ): thoát theo nến volume đột biến, rủi ro theo độ sâu nén, bản nới ngưỡng.

## Đầu ra

`research/long/g68_refine.py`, báo cáo `reports/2026-10-09-g68-dmi-ema-refine.md`.
