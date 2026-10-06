# G38: dây chuyền tìm setup mới — kết quả (06/10/2026)

Kế hoạch: `docs/superpowers/plans/2026-10-06-g38-setup-discovery.md`. Chỉ dữ liệu MT5. Script: `research/long/discovery.py`
(6 họ, 121 bộ tham số, cùng bộ kiểm chứng), `research/long/portfolio_g38.py` (danh mục, FTMO, CUSTOM).

## 1. Quét 6 họ (chọn trên 2010–2016, kiểm chứng 2017–2020 và 2021–2025)

| Họ | Bộ dương cả 3 giai đoạn | Bộ chọn: train / validate / test (R/lệnh) | Ngẫu nhiên p | Láng giềng | Kết luận |
|---|---|---|---|---|---|
| T1 Donchian D1 (40, dừng 3 ATR, trail 4) | 17/24 | +0,23 / +0,19 / +0,44 | 0,028 | 4/4 | Biên (chưa qua ngưỡng đa kiểm định) |
| **T2 Donchian H4 60 + phía EMA200 D1 (dừng 2 ATR, trail 3)** | 12/24 | **+0,17 / +0,24 / +0,17** | **0,001** | 3/4 | **Ứng viên mạnh nhất**; âm trên cặp mới |
| T3 Hồi trong xu hướng RSI(2) H1 | 0/27 | −0,05 / −0,15 / −0,05 | 0,19 | 0/4 | Loại |
| T4 Đảo về trung bình Bollinger + ADX thấp H1 | 0/16 | −0,12 / −0,23 / −0,13 | 1,00 | 0/4 | Loại |
| T5 Phá vùng phiên Á (London) H1 | 0/18 | −0,01 / −0,04 / −0,03 | 0,02 | 0/3 | Loại (âm sau phí) |
| T6 Đà 120 ngày D1 (dừng 3, trail 3) | 3/10 | +0,39 / +0,23 / +0,16 | 0,038 | 3/3 | Biên |

Kiểu **bám xu hướng dài (T1, T2, T6) đều dương ở cả 3 giai đoạn**; kiểu đảo chiều và phá vùng ngắn hạn (T3–T5) đều âm.

T2 thêm: phí ×2 + trượt 0,1R vẫn +0,08R; bỏ symbol tệ nhất (BTCUSD) vẫn +0,10R; theo symbol: EURUSD −0,04, GBPUSD +0,06,
XAUUSD +0,44, BTCUSD +0,84, USDJPY +0,13. Trên 8 cặp mới 2024–2026: −0,27R (278 lệnh). Kiểm tra cùng giai đoạn: 5 symbol cũ
2024-02..2025-10 vẫn +0,21R, nhưng EURUSD/GBPUSD/USDJPY âm năm 2025 trong khi XAUUSD +15R; cặp mới gần như không có lệnh
năm 2024 (EMA200 D1 cần ~200 ngày). ⇒ T2 mạnh trên tài sản có xu hướng (vàng, BTC), yếu trên các cặp tiền gần đây.

## 2. Danh mục (FTMO 1-Step, 0,3%/lệnh, 2010–2025; setup xu hướng chạy nhóm riêng POSITION)

| Danh mục | %/năm | DD | Năm dương | Bootstrap %/năm p10 | DD p90 |
|---|---|---|---|---|---|
| M5 = S04 + S06B lọc USD + bồi (đang dùng) | +1,49% | 2,7% | 14/16 | +0,96% | 4,3% |
| **M5 + T2** | **+3,95%** | 5,6% | 14/16 | **+3,54%** | 12,3% |
| M5 + T1 | +2,38% | 4,9% | 13/16 | +1,76% | 8,4% |
| M5 + T6 | +1,77% | 3,5% | 14/16 | +1,25% | 5,2% |
| M5 + T1 + T2 + T6 | +2,53% | 8,3% | 11/16 | +1,44% | 11,8% |

Tương quan tháng của T2 với M5: +0,03 (gần độc lập) ⇒ thêm T2 là đa dạng hóa thật.

## 3. FTMO / CUSTOM (lịch sử mỗi thứ Hai / xáo tháng)

| Danh mục | Kiểu | Rủi ro | Qua ≤ 12 tháng | ≤ 24 tháng | Trung vị |
|---|---|---|---|---|---|
| M5 | 1-Step | 1% | 26% / 39% | 64% / 69% | 1,1–1,5 năm |
| **M5 + T2** | **1-Step** | **0,5%** | **40% / 46%** | **74% / 77%** | **0,9–1,1 năm** |
| M5 + T2 | 1-Step | 0,75% | 52% / 59% | 71% / 72% | 0,5–0,7 năm |
| M5 + T2 | 2-Step | 0,75% / 0,56% | 27% / 31% | 61% / 67% | 1,2–1,3 năm |
| M5 + T2 | CUSTOM 12 tháng | 0,5% | lãi trung vị +6,4%, năm tệ nhất −9,2%, năm lỗ 19% | | |
| M5 + T2 | CUSTOM 12 tháng | 1% | lãi trung vị +4,6%, năm lỗ 43% (quá rủi ro) | | |

Thêm T2 giúp qua FTMO nhanh hơn ở **rủi ro thấp hơn** (0,5% thay vì 1%). Ở CUSTOM, 0,5% là mức hợp lý; 1% làm kết quả xấu đi.

## Kết luận và bước tiếp

1. **T2 là setup mới đáng dựng**: bằng chứng mạnh trên 5 symbol (p = 0,001, ổn định 3 giai đoạn, chịu phí, không phụ thuộc
   một symbol, gần độc lập với S04/S06B), nhưng **chưa vượt kiểm tra ngoài mẫu theo symbol** (cặp tiền 2025–2026).
   ⇒ Dựng trong EA ở **SHADOW** trước, theo dõi bằng `edge_monitor`, chưa vào lệnh thật.
2. Kiểm chứng giả thuyết "T2 hợp tài sản có xu hướng": xuất thêm XAGUSD, ETHUSD, dầu (USOIL/XTIUSD), chỉ số (US500/NAS100)
   từ MT5 để kiểm tra ngoài mẫu.
3. T1, T6: giữ làm ứng viên phụ (p 0,03–0,04, chưa qua ngưỡng đa kiểm định); không dựng lúc này.
4. Mức rủi ro đề xuất khi T2 đã khớp forward: FTMO 1-Step 0,5%; CUSTOM 0,5%.
