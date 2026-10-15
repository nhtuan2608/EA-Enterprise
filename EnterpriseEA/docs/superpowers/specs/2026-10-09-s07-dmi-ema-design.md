# S07 — Nén → bung DMI + EMA (XAUUSD): thiết kế đưa vào EA (G72) — 09/10/2026

Trạng thái: **bản thiết kế, chờ người dùng chốt các quyết định ở mục 11.** Chưa sửa code EA.

## 1. Nguồn và phạm vi

Setup của người dùng (4 ví dụ XAUUSD M15, 09/2026) đã được nghiên cứu ở G67–G71 (kế hoạch đăng ký trước, chỉ dữ liệu MT5):

| Phần | Nghiên cứu | Kết quả dùng cho thiết kế |
|---|---|---|
| Quy tắc lõi, chọn thoát, bộ chặn | G67 | Lọc EMA200 H4; thoát EMA55, TP 8R |
| Khung + chau chuốt | G67 §7, G68, G69 | Mua: M30 nén 4 giờ + SL bỏ khoảng trống + EMA100 sau 3R |
| Bồi lệnh | G70 | Phương án B: bồi khi khung khác ra tín hiệu, tối đa 3 lệnh mở, không BE |
| Lệnh bán | G69, G71 | Không đạt; theo dõi H1 + chạm cản EMA200 H4 ở SHADOW |

Phạm vi: **chỉ XAUUSD** (G67: không có lợi thế ở XAG, BTC, ETH, FX). Hai sổ độc lập: **S07 (mua)** và **S07S (bán)**.

## 2. Quy tắc tín hiệu chung (mọi khung)

Chỉ báo trên khung của engine: EMA 21/55/100/200 (giá đóng), DMI 14/14 (Wilder, như TradingView), ATR 14 (Wilder).

Tại lúc nến *i* đóng, chiều *d*:
1. **Nén:** trong W nến trước, ADX thấp nhất ≤ 20 và |+DI − −DI| ≤ 6 tại nến đó.
2. **ADX quay lên:** ADX[i] > ADX[i−1] và ADX[i] − ADX đáy ≤ 10.
3. **DI theo chiều và đang tách:** mua: +DI > −DI và (+DI − −DI) tăng so với nến trước; bán ngược lại.
4. **Giá ở hẳn một phía 4 EMA:** mua: giá đóng trên cả 4; bán: dưới cả 4.
5. **Xu hướng H4:** mua: giá đóng H4 hoàn tất gần nhất trên EMA200 H4; bán: dưới.

Vào lệnh MARKET ở nến kế tiếp. SL: đáy thấp nhất (mua) / đỉnh cao nhất (bán) của W nến trước + nến tín hiệu ∓ 0,1 ATR, **bỏ qua các nến trước một khoảng trống > 6 giờ** trong cửa sổ (cuối tuần, nghỉ). Khoảng dừng < 1 ATR thì nới 1 ATR; > 4 ATR thì bỏ tín hiệu. Mỗi engine nghỉ C nến sau khi lệnh của nó đóng.

| Khung | W (cửa sổ nén) | C (nghỉ) | Giữ tối đa |
|---|---|---|---|
| M15 | 16 nến | 8 | 480 nến |
| M30 | 8 nến (4 giờ) | 4 | 240 nến |
| H1 | 4 nến (4 giờ) | 2 | 120 nến |
| H4 | 8 nến | 4 | 240 nến |

## 3. Sổ MUA — S07

- **Lệnh gốc:** engine M30, chỉ mua.
- **Thoát (Trade Manager, profile mới `S07`):** không chốt một phần, không dời hòa vốn, không thoát theo cấu trúc vùng. Nến M30 đóng dưới EMA55 → đóng lệnh ở giá mở nến sau; khi lãi tối đa kể từ lúc vào ≥ 3R thì thay EMA55 bằng EMA100. TP 8R đặt sẵn ở broker. Giữ tối đa 240 nến M30.
- **Bồi lệnh (phương án B, G70):** khi một lệnh S07 gốc đang mở và đang dương (giá đóng nến tín hiệu bồi > giá vào lệnh gốc), một tín hiệu mua của engine **M15, H1 hoặc H4** (cùng quy tắc mục 2) mở thêm một lệnh đầy đủ:
  - rủi ro bằng lệnh gốc (1R = 1,5%); SL, thoát (EMA55 → EMA100 sau 3R của chính khung đó) và TP 8R riêng;
  - tối đa 2 lệnh bồi cho mỗi lệnh gốc; cách lệnh trước ≥ 1 giờ;
  - **tối đa 3 lệnh S07 mở cùng lúc** trên XAUUSD (4,5% rủi ro mở), tính cả lệnh bồi còn sống sau khi lệnh gốc đã đóng;
  - không dời SL các lệnh trước về hòa vốn (G70: BE làm kém đi ở mọi bản).
  - Engine M15/H1/H4 của S07 **chỉ sinh tín hiệu bồi**; tự nó không mở lệnh gốc.

## 4. Sổ BÁN — S07S (chỉ SHADOW)

- Engine H1, chỉ bán, thêm điều kiện vị trí **L2**: đỉnh cao nhất trong cửa sổ nén ≥ EMA200 H4 − 0,5 ATR (nén sát cản EMA200 H4 rồi bán).
- Thoát: nến H1 đóng trên EMA55, TP 8R, giữ tối đa 120 nến. Không bồi lệnh.
- Chế độ SHADOW cố định trong bản này: ghi tín hiệu, lệnh ảo và kết quả vào sổ ứng viên; **không gửi lệnh**. Lý do: G71 không đạt (khoảng 6 lệnh/năm, chưa đủ bằng chứng).

## 5. Thay đổi trong EA

| Thành phần | Thay đổi |
|---|---|
| `Setups/DmiEmaCompression.mqh` (mới) | Engine thuần theo nến đóng: DMI/EMA/ATR, nén → kích hoạt, SL bỏ khoảng trống, điều kiện L2; tham số theo khung (bảng mục 2) |
| `Runtime/StrategyCandidateRuntime.mqh` | Thêm khe engine: S07 M30 (gốc), S07 M15/H1/H4 (nguồn bồi), S07S H1. **Thêm hỗ trợ khung M30** (hiện có M5/H1/H4) ở runtime, Trade Manager, pending và xuất dữ liệu |
| `Integration/S07PyramidRuntime.mqh` (mới, theo mẫu `S06BPyramidRuntime.mqh`) | Ghép tín hiệu bồi với lệnh S07 gốc đang dương; giới hạn 3 lệnh mở; mỗi lệnh bồi đi qua đủ kiểm tra như lệnh thường (ủy quyền phiên, headroom, ngân sách, volume, kinh tế lệnh, cửa sổ tin) |
| `Runtime/TradeManagerRuntime.mqh` | Profile `S07`: thoát EMA55 → EMA100 sau 3R theo khung của lệnh, giữ tối đa theo khung, không BE/partial/structure exit |
| `Integration/SetupArbitration.mqh` | Thứ hạng S07 ngang SWING; S07S chỉ SHADOW nên không tranh lệnh |
| `Risk/RiskLimitsProfile.mqh` | Trọng số rủi ro theo setup có thêm S07 (mục 6) |
| Inputs | `InpS07Mode` (OFF/SHADOW/LIVE, mặc định SHADOW), `InpS07PyramidMode` (OFF/SHADOW/LIVE, mặc định SHADOW), `InpS07SellMode` (OFF/SHADOW, mặc định SHADOW), `InpRiskWeightS07` (mặc định 1,00) |
| Dashboard | Tab Market: trạng thái S07 theo khung (nén/kích hoạt/lệnh mở, số lệnh bồi); tab Trades: đánh dấu lệnh bồi |
| Kiểm tra parity tín hiệu (G48, `research/g10/signal_parity.py`) | Thêm S07 M15/M30/H1/H4 và S07S: tín hiệu EA phải khớp bộ sinh tín hiệu nghiên cứu (`g67_dmi_ema.py` + G68/G70/G71) |

## 6. Rủi ro (lỗ tổng 30%)

Dùng chính sách **CUSTOM** đã có (G34) cho tài khoản cá nhân, không theo luật FTMO:

| Thông số | Giá trị đề xuất | Ghi chú |
|---|---|---|
| Lỗ tổng (`InpCustomOverallLossPercent`) | **30%** | Người dùng chốt |
| Mốc lỗ tổng | Cố định theo vốn ban đầu (`InpCustomTrailingFloor = false`) | Đề xuất, xem D2 |
| Lỗ ngày (`InpCustomDailyLossPercent`) | **7,5%** | Đề xuất, xem D1. Hạn nội bộ = 0,8 × 7,5% = 6% ≥ 4,5% rủi ro mở tối đa |
| Rủi ro mỗi lệnh (`InpEvalRiskPercent`) | **1,5%** | Đúng trần hiện có `EEA_RISK_OVERRIDE_CAP` = 1,5% |
| Rủi ro mở tối đa | min(4 × 1,5%, 6%) = 6% | Đủ cho 3 lệnh S07 (4,5%) |
| Chặn tuần nội bộ | min(2 × 6%, 0,8 × 30%) = 12% | Từ công thức hiện có |

Hệ quả cần xử lý:
- **Setup đang LIVE (S04, S06B) không được tăng rủi ro theo.** Khi rủi ro mỗi lệnh lên 1,5%, giữ nguyên số tiền rủi ro của chúng bằng trọng số: S04 0,65 × 0,5/1,5 ≈ **0,22**, S06B 1,00 × 0,5/1,5 ≈ **0,33**, T2 0,34 × 0,5/1,5 ≈ **0,11** (xem D4).
- **Giới hạn phơi nhiễm tiền tệ** hiện = 2,5 × rủi ro mỗi lệnh = 3,75% < 4,5% của 3 lệnh S07 → lệnh S07 thứ 3 sẽ bị chặn. Cần nâng riêng cho XAU khi S07 bật, hoặc chấp nhận tối đa 2 lệnh (xem D3).
- **`max_correlated_trades` = 2** cũng có thể chặn lệnh thứ 3 cùng symbol (xem D3).
- **Ủy quyền phiên** phải ký với `max_risk_per_trade_fraction` ≥ 1,5% và giới hạn lệnh SWING/ngày đủ cho lệnh gốc + bồi.

Số liệu nghiên cứu ở 1,5%/lệnh (2018–06/2026, lãi kép):

| Sổ | %/năm | DD lớn nhất | DD p90 1 năm | Chạm 20% / 30% trong 1 năm |
|---|---|---|---|---|
| S07 không bồi | +49% | 18% | 14% | 0% / 0% |
| **S07 + bồi (B, tối đa 3 lệnh)** | **+89%** | **32%** | 24% | 26% / 6% |

Với mốc lỗ tổng 30%, khả năng chạm mốc trong một năm theo lịch sử khoảng 6%; trong lịch sử 2018–2026 có một lần sụt 32% (vượt 30%) → EA sẽ dừng ở mốc. Đây là rủi ro người dùng chấp nhận khi chọn B.

## 7. Chế độ và triển khai

1. **SHADOW 2–4 tuần** cho cả S07 (gốc), bồi lệnh và S07S: chỉ ghi lệnh ảo, không gửi lệnh.
2. **Điều kiện lên LIVE** (S07 gốc trước, bồi sau):
   - parity tín hiệu EA ↔ nghiên cứu ≥ 95% (mọi khung S07);
   - không lỗi thực thi / khôi phục trong SHADOW;
   - kết quả lệnh ảo không lệch xa phân phối nghiên cứu (đánh giá trong review tuần);
   - người dùng ký phiên với giới hạn mới.
3. S07S giữ SHADOW tới khi có đủ lệnh để làm lại đánh giá (đề xuất ≥ 30 lệnh ảo).

## 8. Kiểm thử

- Oracle Python cho engine (dùng lại `g67_dmi_ema.signals`/`walk`): nén, ADX quay lên, DI tách, 4 EMA, H4 EMA200, SL bỏ khoảng trống, L2.
- Test DMI/EMA/ATR khớp TradingView (Wilder RMA) trên dữ liệu mẫu cố định.
- Test bồi lệnh: chỉ khi lệnh gốc dương; tối đa 2 bồi; cách ≥ 1 giờ; tối đa 3 lệnh mở; không bồi từ cùng khung M30; lệnh bồi qua đủ cổng kiểm tra.
- Test Trade Manager profile `S07`: EMA55 → EMA100 sau 3R; không BE/partial; TP 8R; giữ tối đa theo khung.
- Test rủi ro: CUSTOM 30% / 7,5%; trọng số S04/S06B/T2 giữ nguyên tiền rủi ro; giới hạn tiền tệ/tương quan theo D3.
- Compile MetaEditor 0 lỗi 0 cảnh báo; toàn bộ test hiện có vẫn đạt.

## 9. Rủi ro đã biết

- Lợi thế mua gắn với xu hướng tăng dài hạn của vàng; năm vàng đi ngang/giảm (2018, 2021) âm.
- 07/2026–nay mẫu nhỏ (10 lệnh, −0,05R).
- Bồi lệnh tương đương tăng đòn bẩy: cùng mức sụt giảm, tăng rủi ro lệnh gốc lên 2,5–3% cho kết quả tương tự (G70).
- Nghiên cứu dùng spread nến; thực tế có thể trượt giá lúc mở cửa thứ Hai và lúc tin.

## 10. Kế hoạch code (sau khi chốt)

1. Engine + oracle + test (mục 8) → 2. hỗ trợ khung M30 → 3. khe engine S07/S07S + SHADOW → 4. profile Trade Manager → 5. bồi lệnh (SHADOW) → 6. rủi ro CUSTOM + trọng số → 7. dashboard + parity → 8. compile, test, deploy (người dùng gắn lại EA).

## 11. Quyết định cần người dùng chốt

| # | Câu hỏi | Đề xuất |
|---|---|---|
| D1 | Lỗ ngày tối đa | **7,5%** (EA tự dừng vào lệnh ở 6%) |
| D2 | Mốc lỗ tổng 30% cố định theo vốn ban đầu hay trượt theo đỉnh số dư | **Cố định** |
| D3 | Cho phép 3 lệnh S07 cùng lúc trên XAU (nâng giới hạn tiền tệ/tương quan cho S07) | **Có**, chỉ cho S07 trên XAUUSD |
| D4 | Giữ nguyên số tiền rủi ro của S04/S06B/T2 bằng trọng số mới | **Có** (0,22 / 0,33 / 0,11) |
| D5 | Thời gian SHADOW trước khi LIVE | **2 tuần** cho lệnh gốc, **4 tuần** cho bồi lệnh |
| D6 | S07S (bán) | **SHADOW**, đánh giá lại khi có ≥ 30 lệnh ảo |
