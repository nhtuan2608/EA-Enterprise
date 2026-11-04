# G160: thư viện manh mối, phục kích trước và bồi lệnh thông minh — khung kế hoạch (04/11/2026)

## Yêu cầu của người dùng (04/11)

- Ngoài OB, tìm thêm nhiều phương pháp giao dịch: đoán đáy đoán đỉnh, quét thanh khoản, giao phiên...
- **Phát hiện và phục kích trước.**
- Bồi lệnh phải **thông minh**: nghiên cứu để tìm nhiều manh mối và phối hợp chúng.

Bổ sung cho [G158](2026-11-04-g158-hedge-recovery.md) (bồi lệnh không SL; entry price action chỉ hơn ngẫu nhiên sát ngưỡng) và
[khung G159](2026-11-04-g159-hedge-refine-framework.md) (điểm hedge, cắt cặp, gồng, bộ lọc).

## Điều đã biết, và góc chưa test

| Đã đo khi dùng để **đoán hướng** | Kết quả | Nguồn |
|---|---|---|
| quét thanh khoản rồi lấy lại | không hơn ngẫu nhiên; cùng chiều D1 còn hơi kém | G85, G156c, G157 |
| chuỗi giao phiên Á–Âu–Mỹ | không vững | G126 |
| đỉnh / đáy cạn đà, RSI quá mua / bán | âm ở validate | G130, G131 |
| vùng, mức, Fibonacci, hợp lưu | mức giả bằng mức thật | G45, G47, G109, G111 |
| phá giả / đi tiếp (± 1 ATR) | khoảng 51 / 49 | G156a2, G157 |

**Góc chưa test** (lý do có G160): trong hệ thống bồi lệnh, câu hỏi không chỉ là "đoán đúng hướng" mà còn là:
- (1) **bồi ở đâu**: mức thanh khoản thay cho bước cố định;
- (2) **phục kích ở đâu**: lệnh chờ đặt sẵn ở chỗ stop của đám đông nằm;
- (3) **khi nào ngừng bồi / chuyển sang hedge**.

Một manh mối không đoán được hướng **vẫn có thể** giảm sụt vốn, nếu nó cho biết chỗ giá hay dừng. G160 đo đúng điều đó, bằng thước của G158:
- tài khoản thật;
- số lần cháy;
- xác suất cháy 12 tháng;
- stress 2010–2018;
- so với ngẫu nhiên.

## 1. Thư viện manh mối (định nghĩa bằng luật, đối xứng mua / bán)

### A. Đoán đỉnh / đáy (đảo chiều)

| Mã | Manh mối |
|---|---|
| A1 | **Phân kỳ RSI** H1 / H4: giá tạo đỉnh cao hơn, RSI14 đỉnh thấp hơn (pivot 5 / 5) |
| A2 | **Ba nhịp đẩy** (three drives): 3 đỉnh (đáy) liên tiếp cao (thấp) dần, khoảng cách các nhịp giảm dần |
| A3 | **Nến cao trào**: biên ≥ 2 ATR, tick volume ≥ 2 × TB 20 nến, râu ngược ≥ 50 % biên |
| A4 | **Căng xa**: giá cách VWAP ngày hoặc giá mở ngày ≥ 2 ADR20 |
| A5 | **Đóng quay lại trong Bollinger 3σ** sau khi đóng ngoài dải |
| A6 | **Cạn biến động**: ATR H1 bung > 2 × TB rồi co lại < 1 × trong 3 nến |

### B. Thanh khoản (chỗ stop của đám đông nằm)

| Mã | Manh mối |
|---|---|
| B1 | **Đỉnh / đáy bằng nhau**: ≥ 2 swing H1 cách nhau ≤ 0,1 ATR H1 (vũng thanh khoản) |
| B2 | Đỉnh / đáy ngày trước, tuần trước |
| B3 | Đỉnh / đáy phiên Á |
| B4 | **Số tròn** 25 / 50 / 100 USD |
| B5 | **Cú quét** (stop hunt): râu xuyên mức B1–B4 ≥ 0,2 ATR rồi đóng lại vào trong |

### C. Giao phiên

| Mã | Manh mối |
|---|---|
| C1 | **Judas swing**: 07–10 giờ server (mở phiên London), giá quét đỉnh / đáy phiên Á rồi đóng ngược lại |
| C2 | **Mở cửa New York** (16:30 server) đảo chiều nhịp của phiên London: London đi ≥ 1 ADR × 0,5, rồi nến NY đầu tiên nhấn chìm ngược |
| C3 | **Giá mở ngày / tuần làm nam châm**: giá cách giá mở ngày ≥ 1 ADR20 trong phiên NY |
| C4 | **Phá biên giờ đầu** của phiên London / NY |

### D. Cấu trúc (kiểu ICT / SMC)

| Mã | Manh mối |
|---|---|
| D1 | **CHoCH khung nhỏ sau cú quét**: sau B5, M30 / H1 phá swing ngược chiều gần nhất |
| D2 | **FVG** (khoảng trống giá trị): khoảng hở 3 nến H1; giá quay lại lấp FVG lần đầu |
| D3 | **Breaker**: OB bị phá xuyên, giá quay lại test từ phía bên kia |
| D4 | **Premium / discount**: giá ở nửa trên / dưới của biên swing H4 gần nhất (theo Fibonacci 50 %) |
| D5 | **OB khung lớn** (E1 của G158), để phối hợp |

### E. Volume (tick volume MT5)

| Mã | Manh mối |
|---|---|
| E1 | Pullback volume thấp, nến tiếp diễn volume cao (E4 của G158, hơn ngẫu nhiên sát ngưỡng) |
| E2 | **Nến từ chối có volume đột biến** ở mức B1–B4 |
| E3 | **Cạn volume ở đỉnh / đáy**: 3 nến cuối của nhịp đẩy volume giảm dần |

### F. Liên thị trường

| Mã | Manh mối |
|---|---|
| F1 | **DXY phân kỳ**: vàng tạo đáy mới mà DXY không tạo đỉnh mới (G77 F3: nhãn chất lượng tốt cho S07) |
| F2 | US10Y đổi chiều cùng lúc (dữ liệu H1 có từ 2024) |

## 2. Phục kích trước (đặt lệnh chờ ở chỗ thanh khoản)

Mỗi đầu phiên (01:00, 08:00, 15:00 server), dựng **bản đồ thanh khoản** từ B1–B4. Với mỗi mức trong ± 1,5 ADR20 quanh giá:
- **Lệnh chờ đón cú quét:** limit đặt **sau** mức, cách mức 0,2–0,3 ATR H1, ngược chiều với cú quét (đón stop hunt), hết hạn cuối phiên.
- **Bộ lọc ngữ cảnh**, phải khai trước 1 trong 3:
  - chiều D1 (R1);
  - premium / discount (D4);
  - DXY (F1).
- **Lệnh đã khớp** đi vào cơ chế bồi lệnh nền (E4 + lưới × 1,5 của G158), có thể kèm module G159.

**Đối chứng:** cùng số lệnh chờ ở **mức giả** (cùng khoảng cách tới giá, không phải mức thanh khoản), như G109 / G111 đã làm.

## 3. Bồi lệnh thông minh (thay bước ATR cố định)

| Mã | Quy tắc bồi |
|---|---|
| S0 | bước 0,5 ATR D1 cố định (nền G158) |
| S1 | **Bồi ở mức thanh khoản kế tiếp** (B1–B4) theo chiều bất lợi; không có mức trong 1,5 bước thì dùng S0 |
| S2 | Như S1 nhưng **chờ xác nhận**: nến từ chối (E2), hoặc CHoCH khung nhỏ (D1) tại mức rồi mới bồi |
| S3 | **Lot theo khoảng cách**: lệnh bồi càng xa giá trung bình thì lot càng lớn, nhưng tổng lot ≤ trần (F6 G159) |
| S4 | **Ngừng bồi khi có tín hiệu tiếp diễn ngược** (D1 chế độ ngược, hoặc phá cấu trúc H4 ngược): chuyển sang hedge (H2 G159) |

## 4. Phối hợp nhiều manh mối (tránh tự lừa)

G147 / G148 cho thấy chấm điểm nhiều yếu tố hay đổi dấu theo năm. Vì vậy:
- **Không dùng hệ thống điểm cộng dồn.** Chỉ phối hợp theo luật VÀ, tối đa **3 manh mối** một tổ hợp.
- **Thứ tự bắt buộc:**
  1. từng manh mối riêng lẻ;
  2. chỉ những manh mối qua vòng 1 mới được ghép đôi;
  3. chỉ cặp qua vòng 2 mới được ghép ba.
- **Ngưỡng siết theo số phép thử** (Bonferroni trong mỗi vòng). Mọi phép thử ghi vào sổ cái của phòng nghiên cứu.

## 5. Các vòng test

| Vòng | Nội dung | Thước đo | Đạt để đi tiếp |
|---|---|---|---|
| **G160a — sàng nhanh** | 25 manh mối mục 1, mỗi cái làm **entry** riêng | (i) hướng: ± 1 ATR H1 trong 4 giờ so với đối chứng (đường ống G156c / G157); (ii) **chỗ dừng**: tỷ lệ giá đảo lại ≥ 0,5 ATR trong 2 giờ sau khi chạm mức, so với mức giả cùng khoảng cách | (i) hoặc (ii) vượt đối chứng với CI Bonferroni, cùng dấu ≥ 2 / 3 kỳ |
| **G160b — phục kích** | lệnh chờ ở bản đồ thanh khoản (mục 2), chỉ dùng manh mối qua G160a | mô hình tài khoản G158; so với lệnh chờ ở mức giả | (A) và (B) của G158 |
| **G160c — bồi thông minh** | S1–S4 trên nền tốt nhất (E4 hoặc G160b) | như G158; thêm DD và stress 2010–2018 | DD < 50 %, stress không cháy, láng giềng ≥ 2 / 3 |
| **G160d — phối hợp** | ghép đôi / ghép ba manh mối qua các vòng trước | như G158 | như G158, cộng Bonferroni theo số tổ hợp |

**Kỳ dữ liệu:**
- H1 thật 2018–10/2026: chọn 2018–2022, kiểm 2023–2026;
- stress D1 2010–2018: chỉ cho cơ chế, vì các manh mối trong ngày không đo được trước 2018.

**Dữ liệu:** chỉ MT5:
- XAUUSD H1 / M30;
- DXY M30 từ 09/2021, nên F1 chỉ đo được từ đó;
- US10Y H1 từ 2024.

## 6. Liên kết với G159

- G159a (F1 + H1 / H2, F5 / F6 + P1 trên nền E4) chạy được song song: nó sửa cơ chế, còn G160 tìm chỗ vào / chỗ bồi.
- Khi cả hai có kết quả, vòng tổ hợp dùng **cơ chế tốt nhất của G159** với **entry / bồi tốt nhất của G160**.

Mỗi vòng viết kế hoạch chi tiết (định nghĩa chính xác, tham số, đối chứng, tiêu chí) trước khi chạy. Không chỉnh định nghĩa sau khi chạy.
