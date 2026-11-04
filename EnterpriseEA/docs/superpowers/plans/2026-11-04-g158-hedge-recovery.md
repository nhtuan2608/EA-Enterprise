# G158: hedge / bồi lệnh không SL, entry theo price action — kế hoạch đăng ký trước (04/11/2026)

## Yêu cầu của người dùng (04/11)

- Phương pháp hedging mới, không dựa vào setup đang có.
- **Không SL**, không quản lý rủi ro kiểu cắt lỗ.
- Phải tìm **đúng entry** bằng price action, indicator, mô hình chart, phương pháp nổi tiếng:
  - OB khung lớn, OB khung nhỏ;
  - hợp lưu, vùng giá tròn;
  - volume các nến trước xác nhận pullback để vào theo trend.

  Thêm giả thuyết để thử.
- Lệnh lỗ không cắt: **bồi thêm lệnh** để cover, hoặc **nâng lot** cho lệnh bồi sau.
- **Khi có lời**: cắt giảm cặp lệnh dương / âm để thu nhỏ vị thế, phần còn lại **gồng**, áp các cách chốt TP đã có.
- Sau đó tìm điểm hedging và lặp lại quy trình.

## Cảnh báo đã nói với người dùng

Bồi lệnh / nâng lot không SL là kiểu "thắng thường xuyên, thua một lần mất nhiều". Backtest dễ đẹp cho tới khi gặp một đợt giá chạy một
chiều dài. Vì vậy G158 mô phỏng **tài khoản thật**: ký quỹ, đòn bẩy, stop-out, swap. G158 cũng **so mỗi kiểu entry với entry ngẫu nhiên**
chạy cùng cơ chế bồi lệnh.

## Dữ liệu

| Phần | Dữ liệu | Ghi chú |
|---|---|---|
| **Chính** | XAUUSD **H1 thật** 19/03/2018 → 10/2026 | ghép `data/h1v` (export của EA); H4, D1 dựng từ H1 |
| **Stress dài** | XAUUSD **D1** 2010 → 03/2018 (`raw/XAUUSD_D1`) | nến trong ngày trước 2018 không có; mỗi nến giả định cực trị **bất lợi** chạm trước (bi quan); gồm đợt giảm 2011–2015 |

Chia kỳ phần chính:
- **chọn**: 03/2018–2022;
- **kiểm**: 2023 → 10/2026.

## Mô hình tài khoản

- **Vốn và lot:**
  - vốn 10.000 USD, lot gốc cố định 0,10 (0,01 / 1.000 USD), không lãi kép;
  - hợp đồng 100 oz / lot.
- **Đòn bẩy và ký quỹ:**
  - đòn bẩy 1:500, kiểm thêm 1:100;
  - ký quỹ hedge tính theo chân lớn hơn.
- **Stop-out và cháy tài khoản:**
  - tính tại giá **bất lợi nhất trong nến**; mức ký quỹ < 50 % thì stop-out, đóng hết;
  - ghi **một lần cháy**, rồi nạp lại 10.000 ở nến sau;
  - đếm số lần cháy.
- **Chi phí:**
  - spread của từng nến (mua theo ask);
  - commission 6 USD / lot khứ hồi;
  - trượt 0,5 × spread trung vị mỗi chiều.
- **Swap:**
  - −30 USD / lot / đêm cho **cả hai chiều**, thứ Tư × 3;
  - kiểm thêm 0 và −60.

## Entry (7 họ, đối xứng mua / bán, tín hiệu ở nến H1 đóng)

| Mã | Họ | Định nghĩa |
|---|---|---|
| E0 | **Ngẫu nhiên** (đối chứng) | nến ngẫu nhiên, chiều ngẫu nhiên, cùng tần suất với họ đang so |
| E1 | **OB khung lớn** | OB tăng H4 = nến H4 giảm cuối cùng trước cú bung ≥ 2 ATR H4 trong ≤ 3 nến, đóng trên đỉnh của nó và phá đỉnh swing H4 gần nhất. Vùng = biên nến OB, hiệu lực 30 nến H4 hoặc tới khi đóng dưới vùng. Vào khi nến H1 **đóng quay lại trong vùng** lần đầu. Đối xứng cho OB giảm |
| E2 | **OB lớn + xác nhận khung nhỏ** | như E1, nhưng vào ở nến H1 trong vùng có nến nhấn chìm cùng chiều, hoặc cú bung H1 ≥ 1,5 ATR H1 phá swing H1 |
| E3 | **OB + hợp lưu** | vùng E1 chứa số tròn 25 USD, hoặc đỉnh / đáy ngày trước, trong ± 0,25 ATR H4 |
| E4 | **Pullback theo trend có volume xác nhận** | chế độ D1 R1 = d; pullback H1 ≥ 3 nến ngược chiều, sâu ≥ 1 ATR H1, về dải EMA21–EMA50 H1, volume pullback < 0,8 × TB 10 nến trước; nến tiếp diễn đóng vượt đỉnh (đáy) nến trước, volume > 1,2 × TB pullback |
| E5 | **Fibonacci OTE** | theo chế độ D1 R1; chân swing H1 (pivot 5 / 5) ≥ 3 ATR H1; giá về vùng 61,8–78,6 %; vào ở nến đóng đầu tiên trong vùng |
| E6 | **Quét thanh khoản rồi lấy lại** (ICT) | theo chế độ D1 R1; nến H1 xuyên đáy ngày trước hoặc đáy phiên Á rồi đóng lại trên mức (đối xứng) |

**Một rổ lệnh mỗi lúc:** có rổ đang mở thì bỏ qua tín hiệu mới.

## Cơ chế bồi lệnh (không SL)

Bước S = s × ATR14 D1, tính lúc mở rổ. s ∈ {0,5; 1,0}.

| Mã | Cơ chế |
|---|---|
| R1-1 / R1-1,5 / R1-2 | **Lưới trung bình cùng chiều**: giá đi ngược S tính từ lệnh gần nhất thì bồi một lệnh cùng chiều, lot = gốc × m^(n−1) với m = 1 / 1,5 / 2. Tối đa L lệnh, L ∈ {6; 10}; đủ L thì chỉ giữ |
| R2-1,5 / R2-2 | **Zone recovery (hedge xen kẽ)**: giá ra khỏi vùng rộng S thì mở lệnh **ngược chiều** với lot = lot trước × k (k = 1,5 / 2), xen kẽ hai mép vùng. Tối đa L lệnh |

## Khi rổ có lời: cắt giảm rồi gồng

Kích hoạt khi lãi ròng của rổ (đã gồm chi phí và swap) ≥ mục tiêu = 0,5 × S × lot gốc × 100 USD:

1. **Cắt giảm:** đóng mọi lệnh trừ **một lệnh chạy** = lệnh gần nhất cùng chiều đang có lời. Đóng cả lệnh âm lẫn lệnh dương, sao cho phần chốt
   ≥ 0.
2. **Gồng lệnh chạy** theo một trong các cách chốt TP đã có:

| Mã | Cách thoát lệnh chạy | Nguồn |
|---|---|---|
| X0 | không giữ lệnh chạy: đóng hết khi đạt mục tiêu | lưới cổ điển |
| X1 | TP cố định 3 × S | kiểu TP 3R |
| X2 | trail 3 ATR H1 theo đỉnh / đáy tốt nhất | XRT |
| X3 | E2X: đóng khi nến H1 đóng qua EMA55; khi đã lời ≥ 3 × S thì dùng EMA100 | S07 |
| X4 | hòa vốn: dời mức thoát về giá vào của lệnh chạy, rồi trail 3 ATR H1 | gồng không lỗ |

Nếu lệnh chạy bị giá đi ngược S trước khi thoát, nó trở thành lệnh đầu của **một vòng bồi mới** (không SL).

**Lưới cấu hình:** 5 cơ chế × 2 bước × 2 giới hạn lệnh × 5 cách thoát = 100 cấu hình cho mỗi họ entry.

## Đạt khi

**(A) Entry có giá trị.** Mỗi họ E1–E6 lấy cấu hình tốt nhất trên kỳ chọn (lãi ròng cao nhất, không cháy), so với **50 lần E0** chạy cùng cấu
hình và cùng tần suất. Đạt khi:
- lãi ròng của họ > phân vị 95 % của E0;
- số lần cháy ≤ trung vị của E0.

**(B) Cấu hình dùng được.** Một cấu hình (họ + cơ chế + tham số) đạt khi cùng đúng:
1. kỳ chọn và kỳ kiểm đều **0 lần cháy** và lãi ròng > 0;
2. **xác suất cháy trong 12 tháng = 0**: mở tài khoản mới vào đầu mỗi tháng 2018–2025, chạy 12 tháng;
3. sụt vốn lớn nhất (theo giá bất lợi trong nến) < 50 %;
4. lãi ròng > 0 khi swap −60 và chi phí × 1,5;
5. stress D1 2010–2018 (bi quan): 0 lần cháy;
6. ≥ 2 / 3 cấu hình láng giềng (đổi s, L hoặc m / k một nấc) cũng thỏa 1 và 2.

**Báo thêm:**
- phần lãi đến từ lệnh đầu so với từ các lệnh bồi;
- tổng swap;
- số lệnh mở tối đa, lot tối đa;
- rổ tệ nhất (sâu nhất, dài nhất).

## Bước tiếp theo (người dùng yêu cầu)

Sau G158: tìm **điểm hedge** (lúc nào mở lệnh ngược) theo price action / indicator, rồi lặp lại quy trình test (G159). Định nghĩa của G159 viết
sau, dựa trên kết quả G158.

Script `research/long/g158_hedge_recovery.py`, kết quả `research/long/results/g158/`. Không chỉnh luật sau khi chạy.
