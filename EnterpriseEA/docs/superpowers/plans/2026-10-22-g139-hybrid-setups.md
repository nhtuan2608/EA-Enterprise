# G139: setup "hybrid" nhiều lớp theo bản tư vấn, các lớp làm trọng số cho S07, và squeeze breakout — kế hoạch đăng ký trước (22/10/2026)

## Vì sao

Người dùng gửi lại một bản tư vấn (22/10/2026) đề xuất xây setup theo 5 lớp: bối cảnh → cấu trúc → mẫu hình → xác nhận → rủi ro.
Bản tư vấn kèm 4 setup cụ thể và thang điểm 0–100 (≥ 70 là vào). Đối chiếu với lịch sử:

| Ý trong bản tư vấn | Đã thử | Phần **chưa** thử |
|---|---|---|
| Hồi về EMA, nến xác nhận | G74, G75, G86, G133 (từng mảnh) | đủ 5 lớp cùng lúc: EMA20>50>200, ADX ≥ 25, RSI 45–60, volume ≥ 1,1×, nến kích hoạt |
| Wyckoff | G136 P4 (nhãn spring trên S07), G85 (quét đáy) | setup đứng riêng: vùng tích lũy → spring → phá đỉnh vùng có volume |
| Morning / evening star | G86, G136 P3 (trong bối cảnh nến V) | ở vùng hỗ trợ / kháng cự (EMA50, đáy/đỉnh xoay) với RSI và volume |
| Wedge, kênh song song | G56 (wedge), G137 G5 (kênh) | wedge có phân kỳ RSI + volume; kênh có lọc xu hướng + volume |
| Chấm điểm đa yếu tố | G33, G83, G108, G114 (điểm từ mô hình học máy / xác suất) | đúng thang điểm cộng tay của bản tư vấn (25/20/20/15/10/10, ≥ 70) |
| SMC/ICT, VSA, volume profile, mean reversion, harmonic, Elliott | G45, G47, G110, G121, G130, G131, G137 | — (không thử lại) |

Lợi thế đã chứng minh vẫn chỉ là **đà sau nén có bối cảnh khung lớn** (S07, T2, S06B) và **nến V quay về EMA200 khi nén**
(VHedge). Vì vậy G139 có ba phần:

- **A**: kiểm đúng nguyên văn 4 setup và thang điểm của bản tư vấn, để có câu trả lời dứt khoát.
- **B**: dùng các lớp xác nhận của bản tư vấn làm **trọng số rủi ro cho chân S07 M30**. Đây đúng là ý của bản tư vấn ("indicator,
  pattern là phụ kiện xác nhận, không phải setup chính"), áp lên setup duy nhất đã có lợi thế.
- **C**: một setup mới bám lợi thế đã có: nén đo bằng độ rộng Bollinger (không phải DMI như S07), phá vỡ theo trạng thái D1.

**Kỳ vọng trước**: thấp cho A (các mảnh đều đã thua), vừa phải cho B và C.

## Quy ước chung (như G137)

- **Dữ liệu**: `research/long/data/{m30v,h1v,m15v}/XAUUSD.csv` (XAUUSD-VIP, giờ server, 5 ngày/tuần). Volume = tick volume (vàng
  spot không có volume thật).
- **Kỳ**: sớm 01/2018–06/2021 (chỉ báo cáo), train 07/2021–12/2023, validate 01/2024–06/2025, test 07/2025–06/2026 (không còn
  kín), sau 07/2026 chỉ xem.
- **Chỉ báo**: EMA20/50/200 đóng cửa; ATR14, ADX14 Wilder (G67); RSI14 Wilder; volume trung bình = SMA20 tick volume của 20 nến
  trước nến i (không gồm nến i); điểm xoay 3 nến mỗi bên, chỉ biết ở nến k + 3 (như G137).
- **Vào lệnh**: giá mở nến sau nến tín hiệu (mua ở giá ask). Không vào khi nến tín hiệu có giờ server 23 hoặc 0 (rollover). Một lệnh
  mỗi setup mỗi khung tại một thời điểm.
- **Thoát**: SL, TP, hết số nến giữ tối đa thì đóng giá đóng cửa; SL và TP cùng nến thì tính SL (engine `g137_patterns.run_trade`).
- **Chi phí**: harsh G68 và bản × 1,5.
- **Đối chứng ngẫu nhiên**: 200 lần như G137 (cùng số lệnh, chiều, giờ server, kỳ, khoảng SL theo ATR, TP theo R, số nến giữ);
  p gộp train + validate.
- **Không tránh tin**: không có lịch tin lịch sử đủ tin cậy cho mọi nến; ghi rõ là thiếu.
- **Không chỉnh luật sau khi chạy.** Lỗi dữ liệu hay nhìn trước thì sửa, chạy lại toàn bộ và ghi rõ.

## Phần A — 4 setup và thang điểm của bản tư vấn (ô quyết định: 12, M30 và H1 cho mỗi mục)

### A1. Trend continuation + pullback

**Mua** tại nến i, tất cả cùng đúng:
1. EMA20 > EMA50 > EMA200 và close > EMA50;
2. EMA200[i] > EMA200[i−10] (dốc dương);
3. ADX ≥ 25;
4. hồi về EMA20: low[i] hoặc low[i−1] ≤ EMA20 + 0,1 ATR;
5. nến i tăng (close > open) và close > EMA20;
6. RSI ∈ [45, 60];
7. volume[i] ≥ 1,1 × volume trung bình;
8. kích hoạt là một trong: **nhấn chìm tăng** (nến i−1 giảm, thân nến i bao thân nến i−1), **pin bar** (râu dưới ≥ 2 × thân và
   ≥ 50% biên độ nến), **morning star** (định nghĩa G136 P3, kết thúc ở nến i).

**SL**: min(low[i−2..i]) − 0,1 ATR, khoảng cách 0,5–3 ATR (ngoài khoảng thì bỏ). **TP** 2R. Giữ tối đa 48 nến.
**Bán** đối xứng: EMA20 < EMA50 < EMA200, close < EMA50, dốc âm, RSI ∈ [40, 55], nến giảm đóng dưới EMA20, nhấn chìm giảm / pin
bar ngược / evening star.

### A2. Wyckoff tích lũy → spring → phá vùng (đứng riêng)

Vùng = 40 nến i−40 … i−1: RH = high cao nhất, RL = low thấp nhất; 2 ATR ≤ RH − RL ≤ 6 ATR.
**Mua** tại nến i:
1. trước đó giảm hoặc đi ngang: EMA200[i] − EMA200[i−40] ≤ 0,5 ATR;
2. **spring** ở nến j trong i−30 … i−1: low[j] < hỗ trợ và close[j] > hỗ trợ, với hỗ trợ = low thấp nhất của i−40 … j−1; volume[j]
   ≤ 1,5 × trung bình (không bùng volume);
3. **phá vùng**: close[i] > RH, nến i tăng, volume[i] ≥ 1,2 × trung bình;
4. RSI[i] ∈ [50, 70].

**SL**: low[j] − 0,1 ATR (spring gần nhất), khoảng cách 0,5–4 ATR. **TP** 2R. Giữ tối đa 96 nến. Nghỉ 10 nến sau một tín hiệu.
**Bán** (phân phối → upthrust → phá đáy vùng) đối xứng, RSI ∈ [30, 50].

### A3. Morning / evening star ở vùng hỗ trợ / kháng cự

**Mua** tại nến i (mẫu là nến i−2, i−1, i):
1. morning star theo G136 P3: thân nến 1 ≥ 0,6 ATR và giảm; |thân nến 2| ≤ 0,3 ATR; thân nến 3 ≥ 0,5 ATR, tăng, đóng trên giữa thân
   nến 1;
2. xu hướng trước yếu đi: ADX[i−3] < 25 hoặc ADX[i−3] < ADX[i−8];
3. vùng hỗ trợ: low[i−1] cách EMA50[i−1] hoặc một đáy xoay đã xác nhận trong i−60 … i−4 không quá 0,5 ATR;
4. volume[i] ≥ volume trung bình;
5. RSI[i] ∈ [35, 55] và RSI[i] > RSI[i−2].

**SL**: low[i−1] − 0,1 ATR (0,5–3 ATR). **TP** 2R. Giữ tối đa 48 nến.
**Bán**: evening star ở kháng cự (EMA50 hoặc đỉnh xoay), RSI ∈ [45, 65] và đang giảm.

### A4a. Rising wedge (bán) / falling wedge (mua), phá vỡ

Trong 60 nến i−60 … i−1, các điểm xoay đã xác nhận trước i:
- ≥ 2 đỉnh và ≥ 2 đáy xoay; đường trên và đường dưới là hồi quy tuyến tính qua chúng;
- **rising wedge**: cả hai dốc > 0, dốc đường trên < dốc đường dưới (hội tụ);
- độ rộng ở nến i ≤ 0,7 × độ rộng ở nến i−60, và ≥ 1 ATR.

**Bán** tại nến i:
1. close[i] < đường dưới − 0,1 ATR, nến giảm;
2. volume[i] ≥ 1,2 × trung bình;
3. **phân kỳ RSI giảm**: ở hai đỉnh xoay cuối, high sau > high trước nhưng RSI sau < RSI trước.

**SL**: high cao nhất 10 nến gần nhất + 0,1 ATR (0,5–4 ATR). **TP** 2R. Giữ tối đa 60 nến. Nghỉ 10 nến.
**Falling wedge (mua)** đối xứng: cả hai dốc < 0, hội tụ, phá đường trên, phân kỳ RSI tăng ở hai đáy cuối.

### A4b. Kênh song song có lọc xu hướng và volume

Như G137 G5 (hồi quy 60 nến, dốc ≥ 0,02 ATR/nến, R² ≥ 0,6, biên = đường hồi quy ± 2σ, low chạm biên dưới, đóng trên biên và trên
EMA20), **thêm**: EMA50 > EMA200 và close > EMA200 (mua); volume[i] ≥ 1,1 × trung bình. SL low[i] − 0,1 ATR (0,5–3 ATR), TP 2R, giữ
60 nến, nghỉ 10 nến. Bán đối xứng.

### A5. Thang điểm của bản tư vấn

Điểm cho chiều mua tại nến i (bán đối xứng):

| Nhóm | Điều kiện | Điểm |
|---|---|---|
| Bối cảnh (25) | EMA20 > EMA50 > EMA200 | 15 |
| | close > EMA20 và > EMA50 | 5 |
| | EMA200[i] > EMA200[i−10] | 5 |
| Cấu trúc (20) | low[i] hoặc low[i−1] ≤ EMA20 + 0,5 ATR, hoặc cách một đáy xoay đã xác nhận (60 nến) ≤ 0,5 ATR | 10 |
| | hai đáy xoay cuối đi lên **và** hai đỉnh xoay cuối đi lên (HH/HL) | 10 |
| Mẫu hình (20) | nhấn chìm / pin bar / morning star như A1 | 20 |
| Volume (15) | volume ≥ 1,1 × trung bình | 10 |
| | volume ≥ 1,5 × trung bình | thêm 5 |
| Động lượng (10) | RSI ∈ [45, 60] | 5 |
| | ADX ≥ 25 | 5 |
| Rủi ro (10) | SL (min low 3 nến − 0,1 ATR) cách 0,5–3 ATR | 10 |

**Vào** khi điểm ≥ 70 ở nến i và < 70 ở nến i−1 (vừa vượt ngưỡng); SL như dòng "Rủi ro", TP 2R, giữ 48 nến. Báo thêm nhóm 50–69
(không quyết định).

### Đạt (từng ô A1–A5)

- R/lệnh > 0 ở train, validate và test;
- ≥ 40 lệnh mỗi kỳ (M30) hoặc ≥ 30 (H1);
- p ≤ 0,003 (A và C có 14 ô: 0,05 / 14 ≈ 0,0036, làm tròn xuống);
- R/lệnh gộp train + validate vẫn > 0 khi chi phí × 1,5.

**Cổng thứ hai** (chỉ khi đạt): tỷ lệ lệnh trùng thời gian và cùng chiều với một chân S07 M30; danh mục S07 M30 + setup mới, MAR
≥ M30 một mình ở cả ba kỳ, DD p90 một năm không vượt quá 3 điểm %.

## Phần B — các lớp xác nhận làm trọng số rủi ro cho S07 M30 (1 ô quyết định)

**Sổ**: S07 M30 bản Python G89 (mặc định, cả hai chiều), rủi ro như EA hiện tại: 1,5% × trọng số EA × 0,5 nếu ngược D1 (G134).
Đây là **mốc so sánh**.

**Điểm xác nhận** của chân gốc, tại nến M30 cuối cùng đã đóng trước lúc vào, theo chiều chân: các nhóm Bối cảnh, Cấu trúc, Volume,
Động lượng của bảng A5 (tối đa 70; không tính Mẫu hình và Rủi ro).

**Ngưỡng**: trung vị điểm của các chân gốc trong kỳ **train** (tính một lần, dùng nguyên cho validate và test).

**Biến thể**: chân gốc có điểm < ngưỡng thì rủi ro × 0,5; các lệnh bồi của chân đó theo nhãn của chân gốc. Không bỏ lệnh nào.

**Đạt khi** cùng đúng:
- R của chân gốc điểm cao > điểm thấp ở train, validate và test;
- p hoán vị nhãn (2.000 lần, train + validate) ≤ 0,01;
- MAR danh mục ≥ mốc ở cả ba kỳ;
- DD p90 một năm (07/2021–06/2026) không cao hơn mốc.

## Phần C — Bollinger squeeze breakout theo D1 (ô quyết định: 2, M30 và H1)

**Mua** tại nến i:
1. **nén**: độ rộng dải Bollinger (4 × độ lệch chuẩn 20 nến) ở nến i−1 nằm trong 20% thấp nhất của 120 nến i−120 … i−1;
2. **phá vỡ**: close[i] > high cao nhất của 20 nến i−20 … i−1, nến i tăng;
3. **bối cảnh**: close[i] > EMA200 và trạng thái D1 (SMA50 − SMA200 của ngày server đã đóng, như EA) là golden.

**SL**: SMA20[i] − 0,1 ATR, khoảng cách 0,5–3 ATR. **TP** 3R. Giữ tối đa 96 nến. Nghỉ 10 nến.
**Bán** đối xứng (dưới EMA200, D1 death).
**Đạt**: như phần A (p ≤ 0,003). Báo thêm (không quyết định) tỷ lệ trùng chân S07 M30 cùng chiều.

## Thứ tự và đầu ra

1. Commit kế hoạch này trước khi chạy.
2. Script `research/long/g139_hybrid.py` (A, C) và `research/long/g139_s07_weight.py` (B).
3. Báo cáo `docs/superpowers/reports/2026-10-xx-g139-hybrid-setups.md`, mỗi ô có:
   - bảng theo kỳ;
   - đối chứng ngẫu nhiên;
   - chi phí × 1,5;
   - dòng **KẾT LUẬN THEO LUẬT: ĐẠT / KHÔNG ĐẠT**.
4. Ô nào đạt chỉ được ghi đề xuất: vào EA mặc định tắt hoặc SHADOW, cần người dùng đồng ý và forward ≥ 30 lệnh. Phần còn lại là
   ghi chú cho agent khác code.
