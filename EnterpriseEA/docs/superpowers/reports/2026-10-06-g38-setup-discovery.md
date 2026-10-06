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

## 4. Dựng T2 trong EA (SHADOW) — audit

- Engine `Setups/DonchianTrend.mqh` (cùng bản ghi engine với S02/S04/S06: checkpoint `_t2`, sổ candidate, log
  `logs/t2_shadow.jsonl`), quét `EEA_StrategyRuntimeScanT2Engine` (H4 đóng, kênh 60 nến trước, ATR14, phía EMA200 trên
  1.000 nến D1, bù 30 nến H4 sau khi khởi động lại). Input `InpT2Mode` chỉ có OFF/SHADOW (mặc định SHADOW).
- Không thể vào lệnh thật: input không có LIVE, runtime giới hạn ở SHADOW, vòng vào lệnh bỏ qua engine không LIVE (có test).
- Kế hoạch lệnh shadow: dừng lỗ đúng 2 ATR từ giá đóng tín hiệu; chốt lời 10R chỉ để các kiểm tra rủi ro chạy (research
  thoát bằng trail ATR 3, không có TP).
- Khớp research: mirror Python (`Tests/t2_oracle.py`) cho cùng tín hiệu với `discovery.sig_t2` 99,8–100% trên 5 symbol
  (EURUSD 609/610, các symbol khác 100%).
- Kết quả ảo: `candidates_eval` đi T2 trên nến H4 EA xuất, thoát như research, mỗi symbol một lệnh; `edge_monitor` có dòng
  `T2_POSITION ảo` (ARL0 256 lệnh, phát hiện mất lợi thế sau trung vị 84 lệnh); `/week` so với kỳ vọng +0,17R.
- 657 test đạt, compile MetaEditor 0/0. Cần nạp lại EA trên chart để T2 bắt đầu chạy ngầm.

## 5. Đường vào lệnh thật của T2 (G40, mặc định TẮT) — audit

- `InpT2Mode` có thêm `T2_LIVE`; mặc định vẫn `T2_SHADOW`. Chỉ bật khi shadow khớp nghiên cứu.
- Trade Manager profile `POSITION`: không hòa vốn, không chốt một phần, trail 3 ATR trên nến H4 ngay từ nến đầu (chỉ siết,
  chỉ khi qua hòa vốn), không thoát theo cấu trúc (đăng ký vùng = 0) — cùng quy tắc với nghiên cứu và kết quả ảo.
- POSITION theo luật SWING cho chặn tin, sentiment, hạn mức lệnh của phiên, tỷ lệ RR tối thiểu và swap (ước 10 đêm).
- Một lệnh mỗi symbol + chiều + profile (luật EA): T2 có thể cùng chiều với S04/S06B trên một symbol, như trong mô phỏng danh mục G38;
  trần rủi ro mở và trần phơi nhiễm theo đồng tiền vẫn áp chung.
- TP đặt ở sàn = 20R chỉ để các kiểm tra kinh tế chạy (lệnh lớn nhất trong 1.037 lệnh nghiên cứu là 17,7R); ban đầu đặt 10R
  sẽ làm R trung bình giảm 0,187 → 0,17, nên đã nâng lên 20R.
- Thời gian giữ: nghiên cứu trung vị 18 nến H4, p90 58, lớn nhất 141; Trade Manager không có trần 540 nến như nghiên cứu nhưng
  không lệnh nào chạm tới.
- Khác biệt còn lại, cần người dùng quyết: News Guard dời hòa vốn cho lệnh đang lãi ≥ 0,3R trước tin HIGH (áp cho mọi lệnh,
  kể cả T2); nghiên cứu không có luật này, có thể cắt một phần lệnh xu hướng lớn.
- `current/live_status.json` (EA ghi mỗi 30 giây): bật thực thi, đã cho phép lệnh thật, phiên, tạm dừng, chế độ từng setup;
  Telegram `/status` hiện "Lệnh thật: SẴN SÀNG / KHÔNG vào được (lý do)".
- 669 test đạt, compile MetaEditor 0/0.
