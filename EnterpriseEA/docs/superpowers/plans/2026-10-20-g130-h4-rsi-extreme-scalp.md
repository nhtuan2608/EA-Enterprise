# G130: RSI H4 quá bán / quá mua + RSI cắt MA + DMI, vào lệnh ở khung nhỏ — kế hoạch đăng ký trước (20/10/2026)

## Ý tưởng của người dùng (từ chart H4 vàng)

Một phương pháp **mới, không dùng setup cũ** (S07, VHedge, CtxLimit…), cũng không dùng TP/SL/limit cũ:

- **Khung lớn H4**: giá vào vùng quá bán (RSI ≤ 30 hoặc dưới), rồi **RSI cắt lên đường MA của RSI**, phối hợp DMI.
- **Khung nhỏ**: canh điểm vào kiểu scalp.
- **Giữ / chốt lệnh**: khi RSI H4 về đường cân bằng 50 **và** giá chạm hoặc gần chạm một EMA, thì một trong ba cách:
  - chốt;
  - dời SL sang dương rồi gồng tiếp;
  - gồng tới quá mua.
- **Đối xứng** cho quá mua (bán).

## Chỉ báo (giống chart)

**H4** (dựng từ M30 theo giờ server, chỉ dùng nến đã đóng):
- RSI14 (Wilder) và **RSI-MA** = SMA14 của RSI;
- DMI14: ADX, +DI, −DI;
- EMA 21 / 55 / 100 / 200;
- ATR14.

**Khung vào lệnh M15** (có từ 07/2021): RSI14 + SMA14 của RSI, EMA21, ATR14.

## Tín hiệu H4 (mua; bán đối xứng: 70 thay 30, cắt xuống, DI đổi vai)

Tại một nến H4 đóng k:
1. RSI cắt lên RSI-MA: RSI[k] > MA[k] và RSI[k−1] ≤ MA[k−1];
2. trong 6 nến H4 gần nhất (k−5..k) RSI đã chạm ≤ 30.

**DMI** (biến thể):

| Mã | Điều kiện DMI |
|---|---|
| D0 | không dùng DMI |
| D1 | ADX ≥ 25 và đang quay đầu giảm (ADX[k] < ADX[k−1]): đà giảm cạn |
| D2 | −DI đang giảm (−DI[k] < −DI[k−1]) và +DI đang tăng (+DI[k] > +DI[k−1]) |

**Cửa sổ chờ vào lệnh**: từ lúc nến H4 k đóng, tối đa 12 nến H4 (48 giờ), và dừng sớm nếu RSI H4 đã ≥ 50. Mỗi tín hiệu H4 chỉ vào tối đa một lệnh.

## Vào lệnh (khung nhỏ)

| Mã | Cách vào |
|---|---|
| E0 | (đối chứng khung nhỏ) vào ngay ở giá mở nến H4 kế, không chờ khung nhỏ |
| E1 | M15: RSI cắt lên RSI-MA của M15, khi RSI M15 < 50 lúc cắt; vào ở giá mở nến M15 kế |
| E2 | M15: giá đóng cắt lên EMA21 M15 (nến trước đóng dưới); vào ở giá mở nến kế |

## Điểm dừng ban đầu (chỉ để giới hạn rủi ro và tính R)

- SL = đáy thấp nhất 12 nến M15 trước khi vào (3 giờ) − 0,1 ATR M15.
- Khoảng SL tối thiểu 1 ATR M15.
- Không dùng TP cố định.

## Giữ / chốt lệnh (đánh giá ở mỗi nến H4 đóng; SL kiểm tra trên từng nến M15)

**Sự kiện X** (mua) xảy ra ở nến H4 đóng đầu tiên mà:
- RSI ≥ 50;
- **và** nến H4 đó chạm hoặc gần chạm một trong 4 EMA: EMA nằm trong [đáy − 0,25 ATR H4; đỉnh + 0,25 ATR H4].

| Mã | Quản lý lệnh |
|---|---|
| M1 | **chốt** toàn bộ ở giá mở nến kế sau X |
| M2 | tại X, **dời SL sang dương**: entry + 50% lời đang có (nếu đang lời; nếu không thì giữ SL cũ). Sau đó giữ tới khi RSI H4 ≥ 70 (đóng ở giá mở nến kế) hoặc chạm SL |
| M3 | **gồng tới quá mua**: giữ SL ban đầu, đóng khi RSI H4 ≥ 70 hoặc chạm SL |

- Với mọi M: nếu RSI H4 ≥ 70 trước X thì đóng.
- Giữ tối đa 60 nến H4 (10 ngày).

**Tổng biến thể**: 3 DMI × 3 cách vào × 3 quản lý = **27**. Mua và bán dùng cùng luật đối xứng.

## Dữ liệu, chi phí, kỳ

- XAUUSD M15 (07/2021+), H4 dựng từ M30 (2018+, để đủ khởi động EMA200).
- **Chi phí khắt khe**: spread nến vào/ra + trượt 0,5 × spread trung vị mỗi chiều + $6/lot.
- Mỗi chiều một lệnh mỗi lúc.

| Kỳ | Thời gian |
|---|---|
| Train | 08/2021–2023 |
| Validate | 2024–2025 |
| Test | **2026, niêm phong**, mở một lần |

## Đối chứng

**Vào ngẫu nhiên công bằng**: mỗi lệnh thật được thay bằng một lệnh cùng chiều, cùng giờ trong ngày, ở một ngày khác cùng kỳ.
- Cùng luật SL ban đầu và **cùng cách quản lý M1/M2/M3**, tức cũng chờ RSI H4 về 50, chạm EMA, chạm 70.
- Lặp 200 lần. p = tỷ lệ lần ngẫu nhiên ≥ thật.
- Đối chứng này trả lời: *tín hiệu quá bán + cắt MA + DMI có thêm gì so với cùng cách quản lý lệnh?*

## Chọn

Biến thể đạt khi đủ cả ba:
1. R/lệnh (mua + bán gộp) > 0 ở cả train và validate;
2. ≥ 20 lệnh mỗi kỳ;
3. p validate < 0,10.

- Tín hiệu quá bán / quá mua H4 hiếm, nên ngưỡng số lệnh và p thấp hơn thường lệ. Kết quả vì thế yếu hơn và phải đọc thận trọng.
- Lấy biến thể đạt có min(train, validate) cao nhất.
- Báo cáo **mua và bán riêng**. Không để biến thể chỉ sống nhờ một chiều mà không ghi rõ.

**Báo cáo thêm (mô tả):**
- E0 so với E1/E2: vào ở khung nhỏ có lợi hơn vào ngay không;
- M1 so với M2 so với M3: chốt, dời SL hay gồng.

## Test 2026

- Biến thể được chọn chạy một lần.
- **Đạt** khi R/lệnh > 0, cận dưới bootstrap 90% > 0, và hơn đối chứng ngẫu nhiên (p < 0,10).

## Đầu ra

`research/long/g130_rsi_extreme.py`, báo cáo `reports/2026-10-20-g130-h4-rsi-extreme-scalp.md`.
