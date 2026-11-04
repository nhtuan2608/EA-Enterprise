# G163: vào lệnh theo vùng, trigger dễ thở + bồi thuận trend khi đang lời — kế hoạch đăng ký trước (04/11/2026)

## Yêu cầu và lý do

Người dùng (04/11):
- bồi đúng: **bồi thuận trend khi pullback**;
- cách vào lệnh và quản lý **thoáng hơn** các setup đang có (vào theo **vùng**, điều kiện trigger dễ hơn), vì các setup hiện tại an toàn
  nhưng quá cứng, ít lệnh.

**Cơ sở từ các vòng trước:**
- G162B: các lệnh thắng tốt nhất chạy thẳng, không hồi về. Bồi khi đang lỗ dồn vốn vào lệnh xấu. **Bồi khi đang lời** thì đi cùng lệnh thắng.
- G162A: mức cấu trúc có nến xác nhận tốt hơn bồi ở nến ngẫu nhiên (phân vị 96 %), nhưng chưa giữ được ở kỳ kiểm. Ở G163, nó được dùng làm
  **điểm bồi thuận chiều**.
- G154 / G156: đoán chiều ngắn hạn không được. Thứ duy nhất ổn định là **trôi theo chế độ D1**. Vì vậy chiều do D1 quyết định; vùng chỉ quyết định
  **chỗ vào**.

Rủi ro mỗi lệnh gốc để thấp (**0,5 %**), đổi lại có nhiều lệnh hơn.

**Dữ liệu:**
- XAUUSD H1 thật 05/2018–10/2026 (M30 cho nhánh S07);
- kỳ chọn 05/2018–2022, kỳ kiểm 2023–10/2026;
- chi phí như G161 (spread, trượt giá 0,5 × spread trung vị, phí, swap −30 / lot / đêm).

Cả hai chiều đều được tính. Mua và bán báo cáo riêng.

## Nhánh G163a — entry vùng dễ thở (độc lập với setup đang có)

### Chiều

Chế độ D1 (R1, như XauRegime) của ngày đã đóng:
- **mua** khi D1 tăng;
- **bán** khi D1 giảm;
- trung tính thì không vào.

### Ba họ entry vùng (mô tả chiều mua)

Mỗi họ: tối đa 1 lệnh gốc mở cùng lúc; sau khi đóng, chờ ít nhất 3 nến H1.

| Mã | Vùng | Trigger (dễ) |
|---|---|---|
| Z1 | **Vùng EMA:** đáy nến H1 chạm dải EMA21–EMA55 H1 | nến H1 đóng trên EMA21 (bất kỳ màu nến) |
| Z2 | **Vùng thanh khoản:** đáy nến chạm ± 0,3 ATR H1 quanh một mức: đáy ngày trước, đáy phiên Á, đáy swing H1 5 / 5 (≤ 10 ngày) | nến đóng trên mức |
| Z3 | **Vùng Fib 38,2–61,8 %** của nhịp H4 gần nhất (ZigZag 2 ATR H4, đỉnh / đáy đã xác nhận) | nến H1 đóng tăng (C > O) |

**SL lệnh gốc:** dưới đáy thấp nhất của 3 nến H1 gần nhất trừ 0,3 ATR H1. Khoảng SL tối thiểu 0,5 ATR H1, tối đa 3 ATR H1 (ngoài khoảng thì bỏ
lệnh). Lot tính để lỗ tại SL = **0,5 %** vốn.

### Quản lý lệnh gốc (chung cho mọi biến thể)

- Lời +1R thì dời SL về hòa vốn (cộng phí).
- **Thoát theo trend:**
  - giá đóng H1 dưới EMA55 H1 sau khi đã lời ≥ 1R;
  - hoặc trail dưới đáy swing H1 5 / 5 gần nhất, khi đã lời ≥ 2R.
- **Hết giờ:** 120 nến H1.
- Không có TP cố định, để lệnh thắng được chạy.

### Bồi thuận trend (pyramid)

| Mã | Quy tắc bồi |
|---|---|
| P0 | không bồi |
| P1 | **Bồi theo nấc:** mỗi lần lời thêm +1R (tính từ lệnh gốc) thì bồi một lệnh, tối đa 3 |
| P2 | **Bồi ở pullback có xác nhận** (điều kiện bên dưới) |
| P-rand | **Đối chứng của P2:** bồi ở nến H1 ngẫu nhiên trong lúc đủ điều kiện về lời / hòa vốn, cùng số lần bồi như P2, 50 lần chạy |

**Điều kiện bồi P2:**
- lệnh gốc đã lời ≥ +1R **và** SL đã ở hòa vốn;
- giá hồi về một mức cấu trúc **thuận chiều**: EMA21 H1, hoặc đỉnh swing H1 vừa bị phá (nay thành hỗ trợ), hoặc vùng Z2;
- có **nến xác nhận**: râu dưới ≥ 50 % biên nến, đóng tăng, đóng trên mức;
- tối đa 3 lần bồi.

**Mỗi lệnh bồi:**
- SL riêng dưới đáy pullback trừ 0,3 ATR H1;
- lot sao cho lỗ tại SL = 0,5 % vốn, nhưng **tổng rủi ro mở ≤ 0,5 %**. Tổng rủi ro mở = tổng lỗ nếu mọi SL bị chạm, trừ phần lời đã khóa bằng SL
  hòa vốn / trail. Không đủ chỗ thì giảm lot; dưới 0,01 lot thì bỏ.

**Mọi lệnh bồi thoát cùng lệnh gốc** (theo luật thoát trend / hết giờ), hoặc sớm hơn nếu SL riêng bị chạm.

### Đối chứng entry

**Z-rand:** entry ở nến H1 ngẫu nhiên trong cùng chế độ D1, cùng tần suất, cùng SL và quản lý. Chạy 50 lần. Đối chứng này trả lời câu hỏi: vùng có
tốt hơn **trôi theo D1 thuần** không.

### Chọn và đạt

**Chọn:** 9 tổ hợp (Z1–Z3 × P0–P2). Lấy tổ hợp có MAR (R / DD R) kỳ chọn cao nhất **trong các tổ hợp có ≥ 2 lệnh gốc / tuần**. Chỉ tổ hợp này được
xét đạt.

**Đạt khi thỏa cả 9:**

1. Kỳ kiểm: tổng R > 0, PF ≥ 1,2.
2. Tần suất ≥ 2 lệnh gốc / tuần ở cả hai kỳ. Đây là yêu cầu "thoáng" của người dùng.
3. DD ≤ 15 % vốn ở rủi ro 0,5 % (cả kỳ); xác suất DD ≥ 15 % trong 12 tháng ≤ 5 %.
4. **Entry hơn Z-rand:** tổng R cả kỳ > p95 của Z-rand (cùng P).
5. **Bồi có ích** (chỉ khi P ≠ P0):
   - chênh tổng R so với cùng Z, P0 có CI bootstrap khối tuần > 0 (α = 0,05);
   - với P2: hơn p95 của P-rand.
6. **Cả hai chiều:** mua và bán đều có tổng R ≥ 0 ở cả kỳ.
7. Chi phí × 1,5, swap −60: tổng R cả kỳ > 0.
8. **Láng giềng:** ≥ 2 / 3 thỏa 1 và 3. Láng giềng gồm:
   - đệm vùng 0,2 / 0,4 ATR;
   - đệm SL 0,2 / 0,5 ATR;
   - ngưỡng bồi +0,75R / +1,5R.
9. **Stress D1 2010–02/2018**, cùng luật trên nến D1 (chỉ Z1 / Z3 tính được; với Z2 dùng đáy ngày trước): tổng R ≥ 0, DD ≤ 25 %.

## Nhánh G163b — bồi P2 trên S07

**Nền:** sổ S07 của G89 (như G162B), từ 05/2018.

| Mã | Lệnh ADD |
|---|---|
| B0 | ADD của S07 như hiện tại |
| B-P2 | **thay** ADD của S07 bằng lệnh bồi P2 (mục trên), dựng trên nến M30; lệnh bồi thoát cùng lúc, cùng giá với lệnh gốc S07, hoặc sớm hơn nếu SL riêng bị chạm |
| B-P2+ | **giữ** ADD của S07 **và** thêm P2, với tổng rủi ro mở ≤ 1R gốc |

Rủi ro tính theo R có trọng số như G136.

**Đạt (từng biến thể; α = 0,05 / 2):**
1. Chênh tổng R so với B0, theo khối tuần: CI > 0.
2. Hơn B0 ở cả kỳ chọn và kỳ kiểm.
3. DD R không tệ hơn B0 quá 10 %.
4. Hơn p95 của bồi ngẫu nhiên (P-rand trên S07).
5. Cả mua và bán: chênh ≥ 0.

## Output

- **Mỗi tổ hợp:**
  - số lệnh gốc / tuần;
  - tỷ lệ thắng, R trung bình, PF, tổng R, DD R, MAR;
  - phần R đến từ lệnh gốc và từ lệnh bồi;
  - số lần bồi, tỷ lệ lệnh bồi thắng;
  - lý do thoát;
  - mua / bán riêng.
- **Nếu đạt:** viết kế hoạch đưa vào EA ở chế độ SHADOW (chỉ ghi nhật ký), như SQZ / W1.

## Tệp

- `research/long/g163a_zone_pyramid.py` → `results/g163a/`.
- `research/long/g163b_s07_pyramid.py` → `results/g163b/`. Kiểm code trước: B0 tái tạo đúng R harsh của sổ S07.

Không chỉnh luật sau khi chạy. Sổ cái: 9 + 2 phép thử.
