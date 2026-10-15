# G112: mua đuổi / bán đuổi, bồi lệnh tới khi nào, dừng và chốt ở đâu — kế hoạch đăng ký trước

Ngày 13/10/2026. Chỉ dùng dữ liệu MT5 (raw M5 có tick volume; EURUSD/GBPUSD đã đổi sang giờ server). Nối tiếp G108–G111.

**Ý của người dùng:**
- Mua đuổi, bán đuổi.
- Bồi lệnh tới khi nào; khi nào dừng bồi, khi nào chốt.
- Kết hợp các yếu tố đang có, xem phân phối, so với ngẫu nhiên.
- Tìm plan và sự lặp lại; kiểm tra để chọn lọc rồi thêm vào những gì đã có.

**Kế thừa:**
- G110: phân kỳ giá–delta → cú phá dễ thất bại hơn. Volume nến phá cao và phá cấu trúc H1 → giữ nhiều hơn. FVG ngay phía trước → giữ ít hơn.
- G110: "theo" ở vàng dương ở validate nhưng không ở cuối train.
- G111: test đáy/đỉnh, sau khi sửa lỗi khớp lệnh mua, không còn lợi thế theo chiều. Mô hình có cạn volume (CV) là ứng viên ở vàng.

## 1. Tín hiệu đuổi (vào market ở giá mở nến M5 kế tiếp, theo chiều đà)

| Mã | Điều kiện tại nến M5 vừa đóng |
|---|---|
| **C1 xung lực** | 6 nến M5 gần nhất đi ≥ 1,0 ATR M30 theo một chiều, và giá đóng tạo đỉnh (hoặc đáy) mới của 24 nến |
| **C2 phá cực trị ngày** | giá đóng vượt đỉnh (hoặc đáy) của ngày tính đến nến trước, sau 10:00 server |
| **C3 phá giữ** | sự kiện phá G110 (2 nến đóng bên kia mức) và nến kế tiếp tiếp tục đóng xa hơn; vào market, không chờ retest |

- Mỗi tín hiệu chỉ lấy lần đầu trong mỗi khung 30 phút, mỗi chiều.
- Không vào 23:00–01:00.
- **Stop ban đầu:** swing M5 gần nhất ở phía ngược lại (± spread), nhưng không nhỏ hơn 0,5 ATR M30. Spread luôn được trừ.
- Bộ lọc chi phí: báo cả hai bản, **không lọc** (theo yêu cầu người dùng) và có lọc (stop ≥ 8 spread).

## 2. Phân phối: một cú đuổi thường đi được bao xa

Với mỗi tín hiệu, đo trong 4 giờ:
- **MFE:** giá đi được xa nhất theo chiều lệnh. **MAE:** giá đi ngược xa nhất trước khi đạt MFE. Đơn vị R và ATR M30.
- Xác suất chạm +1R / +2R / +3R trước −1R.
- Thời gian tới MFE.

Chia theo phiên, chế độ D1/H1, volume nến tín hiệu, phân kỳ, phá cấu trúc H1, khoảng tới vùng/FVG phía trước.

**"Sự lặp lại"** = nhóm nào có phân phối MFE lệch hẳn về phía dương **ở cả train và validate**, so với **vào ngẫu nhiên** cùng giờ, cùng chiều, cùng khoảng stop.

## 3. Bồi lệnh, dừng bồi, chốt (mỗi biến thể là quy tắc cố định, chọn trên train, kiểm tra trên validate)

**Bồi (A):**
- Thêm 1 phần (cùng rủi ro ban đầu) khi lệnh đang lãi ≥ +1R **và** giá vừa hồi rồi tạo đỉnh (hoặc đáy) M5 mới theo chiều lệnh.
- Tối đa 2 lần bồi, cách nhau ít nhất 6 nến.
- Khi bồi, dời stop của toàn bộ vị thế về hòa vốn của lệnh đầu.

**Dừng bồi (S), dừng ngay khi gặp điều kiện đầu tiên:**
- S1: giá tới vùng thật kế tiếp hoặc FVG phía trước (bản đồ G109);
- S2: xuất hiện phân kỳ giá–delta 12 nến (G110);
- S3: ADX H1 quay đầu giảm;
- S4: hết 2 lần bồi.

**Chốt / thoát (X), so sánh 5 cách:**
- X1: TP cố định 2R;
- X2: trailing theo swing M5 (stop dời về dưới đáy gần nhất khi giá lập đỉnh mới);
- X3: trailing 1,5 ATR M30 tính từ giá tốt nhất;
- X4: chốt tại vùng thật kế tiếp hoặc FVG phía trước;
- X5: chốt ở mức MFE trung vị của nhóm tương ứng (lấy từ phân phối train).

Mọi cách đều có giới hạn 4 giờ cho lệnh đầu (lệnh bồi thoát cùng lúc).

**So sánh:**
- không bồi;
- bồi theo A + S;
- **bồi ngẫu nhiên** (cùng số lần bồi, thời điểm ngẫu nhiên khi đang lãi).

Kết quả báo theo R của rủi ro ban đầu, cả tổng và DD.

## 4. Lọc bằng mô hình (học cuốn chiếu hàng tháng như G110/G111)

Dự báo xác suất cú đuổi đạt +2R trước −1R. Các biến thể:
- **C:** bối cảnh;
- **+V:** volume, phân kỳ, cạn volume;
- **+P:** price action: phá cấu trúc H1, FVG/vùng phía trước, nén/bung;
- **+VP:** cả hai.

Vào lệnh ở nhóm 20% cao nhất (ngưỡng từ các tháng trước). Đối chứng là chọn ngẫu nhiên cùng số lệnh. Chỉ giữ nhóm yếu tố nào **hơn C và hơn ngẫu nhiên ở cả hai kỳ**.

## 5. Kỳ, tiêu chí, kiểm tra

- **Kỳ:** train 07/2024–03/2025, validate 04–12/2025 (FX tới 10/2025). **Test 2026 niêm phong.** Vàng và EURUSD/GBPUSD/USDJPY.
- **Tiêu chí:** ít nhất 100 lệnh; R/lệnh và cận dưới 90% > 0 ở cả hai kỳ; hơn ngẫu nhiên; báo riêng từng chiều và từng mã; với bồi lệnh thì phải **giảm DD hoặc tăng R mà không làm tăng DD quá 25%**.
- **Test:**
  - tín hiệu C1–C3 chỉ dùng nến đã đóng;
  - stop ban đầu;
  - bồi chỉ xảy ra khi đúng điều kiện, có dời hòa vốn;
  - các cách thoát X1–X5 trên dữ liệu giả lập;
  - không nhìn trước (dữ liệu đầy đủ so với dữ liệu cắt ngắn).
- **Audit độc lập:** tính lại tín hiệu, lệnh, bồi và thoát bằng vòng lặp thô.
