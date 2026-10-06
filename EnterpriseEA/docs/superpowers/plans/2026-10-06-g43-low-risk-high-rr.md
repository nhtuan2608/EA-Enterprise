# G43: rủi ro thấp, RR cao — kế hoạch nghiên cứu và đối chứng (06/10/2026)

Yêu cầu người dùng (06/10): được tự do thêm setup, cách quản lý lệnh/vốn và tham số, không bó vào FTMO (giới hạn tài khoản do policy CUSTOM, G34); tìm phương pháp **ít rủi ro nhất mà RR tốt/cao**, có plan và đối chứng. Chỉ dữ liệu MT5.

## Điểm xuất phát (G37–G41)

- Lợi thế đã kiểm chứng: S06B lọc USD + bồi (p < 0,001), T2 Donchian H4 (p = 0,001, mạnh trên XAU/BTC), S04 (biên).
- Đã thử và **không** thêm được lợi thế: bộ lọc liên thị trường (trừ USD flow), điểm dự đoán/ML, SL/TP khác, khung H4 cho S04/S06B, cặp tiền mới, đảo chiều/phá vùng ngắn hạn (T3–T5).
- Chưa đào: **quản lý rủi ro cấp danh mục** (phân bổ, giảm rủi ro khi sụt), **thoát lệnh/bồi lệnh cho lệnh xu hướng** (nơi RR cao thật sự đến), cân bằng các nhóm setup.

## Thước đo (giống nhau cho mọi phương án)

- Rủi ro: DD lớn nhất, DD p90 bootstrap theo tháng, năm tệ nhất, Ulcer index, chuỗi thua dài nhất.
- Hiệu quả: %/năm, **MAR = %/năm ÷ DD**, p10 %/năm bootstrap.
- RR: lãi TB ÷ lỗ TB, tỷ lệ thắng, R kỳ vọng.
- **Điểm chọn = p10 %/năm ÷ DD p90** (như G37). Chọn trên 2010–2016, báo cáo 2017–2020 và 2021–2025 riêng.

## Giai đoạn

| # | Hướng | Phương án | Đối chứng |
|---|---|---|---|
| A | Mốc | P0 = M5 + T2 (5 symbol), P0b = M5 + T2 chỉ XAU/BTC (danh sách LIVE của G41) | — |
| B1 | Phân bổ rủi ro theo setup | bằng nhau / nghịch đảo độ lệch chuẩn R / tỷ lệ với kỳ vọng ÷ phương sai (có trần) — ước trên 2010–2016 | so với bằng nhau; ngoài mẫu |
| B2 | Giảm rủi ro khi sụt (DD throttle) | rủi ro × 0,5 khi DD từ đỉnh > d (d = 2/3/4/6%), trả lại khi lập đỉnh mới | **throttle ngẫu nhiên** cùng tỷ lệ thời gian giảm rủi ro (500 lần): lợi ích phải vượt p95 |
| B3 | Lọc theo đường vốn của từng setup | bỏ lệnh thật khi tổng R N lệnh gần nhất của setup < 0 (N = 10/20/30), vẫn theo dõi ảo | bỏ ngẫu nhiên cùng số lệnh (500 lần) |
| B4 | Trần rủi ro mở / theo symbol | trần mở 3/4/6 lệnh; 1 hay 2 lệnh mỗi symbol | — |
| C1 | Thoát lệnh T2 | trail 2 / 2,5 / 3 / 4 / 5 ATR, dừng đầu 1,5 / 2 / 3 ATR | láng giềng, 3 giai đoạn, ngẫu nhiên vào lệnh |
| C2 | Bồi lệnh T2 | thêm 1 lệnh cùng rủi ro ở +1R / +2R, dừng lệnh đầu về hòa vốn | so với không bồi theo giai đoạn |
| C3 | **Thoát khi phát hiện đảo chiều** (yêu cầu thêm 06/10) | đóng sớm khi: phá kênh ngược chiều N/2, đóng nến qua EMA20 ngược, nến nhấn chìm ngược khi lệnh đã ≥ +1R; áp cho T2, S06B, S04 | so với thoát gốc theo giai đoạn; thoát ngẫu nhiên cùng số lệnh/độ dài |
| F | **Mô hình nến** (pin bar, nhấn chìm, inside bar) | (F1) bộ lọc vào lệnh: chỉ nhận tín hiệu khi nến tín hiệu/nến trước có mô hình cùng chiều; (F2) thoát như C3 | bỏ ngẫu nhiên cùng tỷ lệ tín hiệu (300 lần) |
| D | Tài sản xu hướng (XAG, ETH, dầu) | chỉ kiểm chứng ngoài mẫu (2024–2026), không chọn tham số trên đó | — |

| E | **SCALP / trong ngày** (yêu cầu thêm 06/10: lợi nhuận đều hơn theo tuần/tháng) | M15: (E1) hồi về EMA M15 theo xu hướng H4/D1 — dùng lợi thế xu hướng đã kiểm chứng làm bộ lọc; (E2) co hẹp → bung trên M15 (bản M15 của S06B); (E3) phá đỉnh/đáy phiên trước theo xu hướng D1. Chi phí: spread thật từ dữ liệu + phí | Chọn trên 2021-10..2023-06, kiểm chứng 2023-07..2024-06 và 2024-07..2025-10; ngẫu nhiên vào lệnh; **ngoài mẫu trên 14 symbol khác** (M15 2024–2026); phí ×2 |

G23 đã cho thấy mọi setup SCALP cũ đều âm sau phí: SCALP mới chỉ được giữ nếu qua đủ đối chứng; nếu không, báo cáo trung thực và không đưa vào.

**Thước đo thêm (theo yêu cầu):** tỷ lệ tuần / tháng / năm dương, lợi nhuận trung vị và p10 theo tuần và tháng, tuần/tháng tệ nhất.

Mỗi giai đoạn chỉ giữ lại phương án vượt đối chứng **và** không xấu đi ở cả 2017–2020 lẫn 2021–2025. Thêm kiểm tra cuối cho tổ hợp chọn: phí ×2 + trượt 0,1R, bỏ từng symbol, bỏ 10 lệnh lời nhất, bootstrap.

## Chặn khớp quá mức

Số phương án đã thử được ghi lại; mỗi tầng quản lý chỉ có ≤ 4 mức; không chọn trên 2017–2025; ưu tiên phương án đơn giản khi chênh lệch nằm trong nhiễu bootstrap.

## Lưu ý nhìn trước (phát hiện khi chạy A)

Danh sách T2 LIVE XAU/BTC (G41) được chọn sau khi thấy kết quả 2018–2025 của từng symbol, và XAU/BTC không có dữ liệu trước 2018 nên train không có lệnh T2 của chúng. Số liệu danh mục "M5 + T2 XAU/BTC" vì vậy lạc quan; mốc trung thực là T2 trên cả 5 symbol. Quy tắc theo **loại tài sản** (T2 cho kim loại/crypto/dầu/chỉ số, không cho FX) chỉ được dùng nếu qua kiểm tra ngoài mẫu trên 16 symbol khác.

## Đầu ra

Báo cáo `reports/2026-10-06-g43-low-risk-high-rr.md`, script `research/long/g43_low_risk.py`; nếu có phương án đạt: thiết kế đưa vào EA ở SHADOW/cấu hình (người dùng chốt trước khi LIVE).
