# G131: đỉnh/đáy cạn đà sau nhiều lần RSI quá mua/quá bán — kế hoạch đăng ký trước (20/10/2026)

## Mô hình của người dùng (chart H4 vàng, 01–03/2026), viết cho chiều bán

1. RSI H4 quá mua **nhiều lần**, có khi cả RSI-MA cũng vượt 70, nhưng giá vẫn lên.
2. Ở đỉnh xuất hiện **nến đóng đảo chiều**, rồi **doji**.
3. Một nến **biên độ lớn** giảm về **chạm EMA21**, RSI cũng đảo chiều.
4. Vài nến sau giá **test lại**, rồi **đóng nến nhấn chìm giảm** hoặc **cạn volume** thì vào lệnh.
5. **Swing** tới khi chạm **EMA200 H4** hoặc RSI **quá bán**.
6. Không dùng DMI.

Chiều mua là đối xứng: quá bán nhiều lần → đáy → nến tăng mạnh về EMA21 → test xuống → nhấn chìm tăng / cạn volume → mua, giữ tới EMA200 hoặc RSI quá mua. Cả hai chiều được báo cáo riêng.

## Dữ liệu và kỳ

- XAUUSD H4 dựng từ M30 theo giờ server (giờ thật từ 03/2018), gồm tick volume.
- Chỉ báo: RSI14 (Wilder), RSI-MA = SMA14 của RSI, EMA21 và EMA200, ATR14.

| Kỳ | Thời gian |
|---|---|
| Train | 03/2018–2021 |
| Validate | 2022–2025 |
| 2026 | **không phải test sạch**: các ví dụ dùng để thiết kế nằm trong 01–03/2026 |

- 2026 chỉ dùng sau khi chọn, để xem luật có bắt được các ví dụ của người dùng không, và báo số liệu kèm cảnh báo.
- **Chi phí khắt khe**: spread nến vào/ra + trượt 0,5 × spread trung vị mỗi chiều + $6/lot.

## Định nghĩa (chiều bán; mua đối xứng)

**Bối cảnh cạn đà**, xét trong 40 nến H4 gần nhất:

| Mã | Điều kiện |
|---|---|
| X1 | ≥ 2 lần quá mua: số đợt RSI ≥ 70, mỗi đợt là chuỗi nến liên tiếp RSI ≥ 70 |
| X2 | ≥ 3 lần quá mua |
| X3 | RSI-MA đã ≥ 70 ít nhất một nến |

**Hình thành đỉnh** (trong 12 nến sau nến quá mua cuối cùng):

| Mã | Điều kiện |
|---|---|
| T1 | một **nến đóng đảo chiều**: nến giảm đóng dưới đáy nến trước, hoặc nhấn chìm giảm (thân nến giảm bao thân nến tăng trước nó) |
| T2 | như T1, **và** có thêm một **doji** (thân ≤ 25% biên độ) trong 4 nến quanh nến đảo chiều |

**Nến biên độ lớn**, trong 10 nến sau khi hình thành đỉnh:
- biên độ ≥ 1,5 ATR14;
- nến giảm, thân ≥ 50%;
- đáy chạm EMA21 (đáy ≤ EMA21);
- RSI đã cắt xuống RSI-MA ở nến này hoặc 2 nến trước.

**Test lại và vào lệnh**, trong 6 nến sau nến biên độ lớn:
- Phải có test lại: một nến có đỉnh ≥ giữa thân nến biên độ lớn.
- Kích hoạt (ở nến test hoặc sau đó):

| Mã | Kích hoạt |
|---|---|
| E1 | **nhấn chìm giảm**: nến giảm, thân bao thân nến tăng trước nó, đóng dưới đáy nến trước |
| E2 | **cạn volume**: nến giảm có tick volume ≤ 0,7 × trung bình 20 nến trước |
| E3 | E1 hoặc E2, cái nào đến trước |

- Vào ở giá mở nến H4 kế.

**Quản lý lệnh:**
- SL = đỉnh cao nhất từ nến biên độ lớn tới lúc vào + 0,1 ATR.
- **Thoát**:
  - khi giá chạm **EMA200 H4**: chốt ở mức EMA200 của nến đó;
  - hoặc khi RSI H4 đóng ≤ 30 (quá bán): chốt ở giá mở nến kế;
  - hoặc chạm SL;
  - tối đa 120 nến H4 (20 ngày).
- **Bỏ lệnh** nếu khoảng tới EMA200 nhỏ hơn 1 lần rủi ro (không đủ chỗ swing).
- Mỗi chiều một lệnh mỗi lúc.

**Tổng biến thể**: 3 × 2 × 3 = **18**.

## Đối chứng

**Vào ngẫu nhiên công bằng**: mỗi lệnh thật được thay bằng một lệnh cùng chiều, cùng giờ H4 trong ngày, ở một ngày khác cùng kỳ.
- SL cùng khoảng tính theo ATR.
- Cùng cách thoát (EMA200 hoặc RSI cực trị hoặc SL).
- Lặp 200 lần. p = tỷ lệ lần ngẫu nhiên ≥ thật.

## Chọn

Biến thể đạt khi đủ cả ba:
1. R/lệnh (mua + bán gộp) > 0 ở **cả** train và validate;
2. ≥ 10 lệnh mỗi kỳ (mô hình hiếm);
3. p validate < 0,10.

Lấy biến thể có min(train, validate) cao nhất. Báo cáo mua và bán riêng.

**2026**: chạy biến thể được chọn (hoặc X1/T1/E3 nếu không chọn được). Liệt kê lệnh tìm được và đánh dấu những lệnh trùng ví dụ của người dùng:
- đỉnh cuối 01/2026;
- đỉnh đầu 03/2026.

## Đầu ra

`research/long/g131_rsi_exhaustion.py`, báo cáo `reports/2026-10-20-g131-rsi-exhaustion-top.md`.

## G131b — nới luật cho đúng mô tả (20/10/2026, sau khi chạy bản đầu)

**Vì sao nới:** bản đầu chỉ cho 0–7 lệnh mỗi kỳ, và không bắt được hai ví dụ của người dùng (29/01/2026 và 02–05/03/2026). Kiểm tra từng nến H4 của hai ví dụ (năm 2026, ngoài kỳ chọn) cho thấy 5 chỗ chặt hơn mô tả. Sửa đúng 5 chỗ, mọi thứ khác giữ nguyên:

1. **Nến đảo chiều** được phép xuất hiện khi RSI **vẫn còn** ≥ 70, hoặc tới 12 nến sau nến quá mua cuối.
2. **Nhấn chìm** = nến giảm có **thân** bao thân nến tăng trước nó; không bắt buộc đóng dưới đáy nến trước. Áp cho cả nến đảo chiều lẫn kích hoạt E1.
3. **RSI đảo chiều** ở nến biên độ lớn = RSI **đang nằm dưới** RSI-MA ở nến đó (mua: trên); không cần cắt mới.
4. **Test lại** = có nến hồi ≥ 38,2% biên độ nến biên độ lớn, tính từ đáy của nó (mua: từ đỉnh).
5. **Chờ kích hoạt** tối đa 12 nến sau nến biên độ lớn (thay vì 6).

Kỳ, chi phí, đối chứng, tiêu chí chọn, 18 biến thể: **không đổi**. Kết quả bản đầu vẫn để nguyên trong báo cáo.

Năm 2026 vẫn chỉ để xem luật có bắt được ví dụ không. Kết quả 2018–2025 của bản đầu đã được nhìn thấy trước khi nới, nên kết quả của G131b phải đọc thận trọng.

## G131c — chỉnh lần cuối (20/10/2026, sau G131b)

G131b vẫn bỏ sót ví dụ 29/01/2026. Nến 29/01 16:00 có biên độ 6 ATR nhưng thân chỉ 39% (râu dưới dài). Điều kiện "thân ≥ 50%" là tác giả tự thêm; người dùng chỉ nói "range tăng rõ rệt".

**Sửa duy nhất:** nến biên độ lớn = nến giảm (đóng < mở; mua: đóng > mở) có biên độ ≥ 1,5 ATR, chạm EMA21, RSI dưới RSI-MA. Không xét tỷ lệ thân.

Mọi thứ khác như G131b. **Đây là lần chỉnh cuối**: kết quả G131c được báo cáo nguyên trạng, không chỉnh thêm.

## G131c trên H1 (người dùng hỏi, 20/10/2026, trước khi chạy)

Luật G131c **không đổi**, chỉ đổi khung sang H1 (dựng từ M30):
- mọi số nến giữ nguyên (40 nến bối cảnh, 12 nến chờ…);
- RSI, EMA21, EMA200, ATR tính trên H1;
- thoát ở EMA200 H1 hoặc RSI cực trị bên kia;
- kỳ, chi phí, đối chứng, tiêu chí chọn như trên.

Chạy một lần, không chỉnh.
