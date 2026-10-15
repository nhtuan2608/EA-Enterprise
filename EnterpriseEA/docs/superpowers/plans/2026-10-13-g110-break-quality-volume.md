# G110: phá thật hay phá giả — volume từng nến, volume cộng dồn so với giá ("đẩy láo"), kết hợp tín hiệu đã có — kế hoạch đăng ký trước

Ngày 13/10/2026. Chỉ dùng dữ liệu MT5 (raw M5 có tick volume; EURUSD/GBPUSD đã đổi sang giờ server). Đây là bước 4 của G109, mở rộng theo đề xuất của người dùng.

**Ý của người dùng:**
- Tính volume của từng nến và volume cộng dồn, so với việc giá tăng hay giảm, để phát hiện **"đẩy láo"** (giá chạy mà volume không xác nhận).
- Kết hợp với các tín hiệu đã tính trước để biết một lần phá mức là **phá giả** hay **phá thật**.
- Vẫn so với plan ngẫu nhiên và các ứng viên đang có.

**Kế thừa:**
- G109 bước 3: S2 (phá rồi retest bằng limit) dương nhẹ ở vàng, nhưng vùng giả cũng vậy. Lợi thế nằm ở cơ chế phá theo đà, rõ nhất khi ADX H1 ≥ 25.
- S1 (quét rồi rút râu) âm.
- G108: bối cảnh khung lớn có ích, đường đi M5 thì không.

**Câu hỏi:**
1. Tại thời điểm phá (nến M5 đóng thứ hai bên kia mức), các đặc trưng volume–giá có phân biệt được **phá giữ được** với **phá thất bại** tốt hơn ngẫu nhiên, và tốt hơn khi chỉ dùng bối cảnh không có volume không?
2. Dùng phân loại đó để chọn **đi theo** (S2 limit retest) hay **đánh ngược** (F, chờ giá đóng quay lại rồi vào ngược) thì có lợi nhuận sau chi phí không, và có hơn các đối chứng không?

## 1. Sự kiện phá mức (bước 1)

**Ba loại mức, tất cả đã biết trước khi phá:**
- **(Z)** vùng thật của bản đồ G109 (đầu ngày và trong ngày);
- **(G)** mức bất kỳ: swing high/low M5 gần nhất đã xác nhận (fractal 2/2);
- **(F)** vùng giả của G109 (đối chứng).

Mỗi mức có bề rộng w như G109 (0,15 ATR M30, tối thiểu 2 spread).

**Sự kiện phá:** lần đầu có 2 nến M5 liên tiếp đóng bên kia mép xa của mức, trong ngày server, không trong 23:00–01:00. Thời điểm quyết định là lúc nến thứ hai đóng.

**Nhãn:**
- **giữ** = trong 6 nến M5 sau đó không có nến nào đóng quay lại bên trong mức;
- **thất bại** = ngược lại.

**Lệnh của mỗi sự kiện:** mục tiêu 2R, giữ tối đa 4 giờ, có spread, 3 cách thoát như G109.
- **Theo (S2):** limit tại mép mức, chờ 12 nến; stop ở phía bên kia mức ± spread.
- **Ngược (F):** nếu có nến đóng quay lại bên trong trong vòng 6 nến thì vào ngược ở giá mở nến kế tiếp; stop sau cực trị của cú phá ± spread.

**Lọc chi phí:** stop ≥ 8 spread, ATR M5 ≥ 3 spread.

## 2. Đặc trưng volume–giá (chỉ dùng nến ≤ thời điểm quyết định, tính theo chiều phá)

- **Volume tương đối:** tick volume của nến chia cho trung vị cùng phút trong ngày của 20 ngày trước. Tính cho 2 nến phá và cho 6 nến tiếp cận trước đó.
- **Công sức và kết quả:** thân nến / ATR M5 chia cho volume tương đối. **"Đẩy láo"** = giá đi xa (kết quả lớn) mà volume thấp.
- **Delta giả:** vị trí giá đóng trong biên nến, từ −1 tới 1, nhân volume. Cộng dồn 6 và 12 nến, chuẩn hóa. **Phân kỳ:** giá đi một hướng nhưng delta cộng dồn đi hướng ngược lại.
- **Xu hướng volume:** độ dốc của volume tương đối trong 6 nến trước khi phá (volume tăng dần vào điểm phá hay cạn dần).
- **Râu nến phá theo chiều phá** (dấu hiệu bị từ chối); khoảng giá đóng vượt qua mép, tính theo w.
- **Bối cảnh (không phải volume):**
  - ADX H1, chiều so với chế độ D1, phía EMA200 H4;
  - độ nén của 12 nến trước khi phá;
  - giờ/phiên;
  - loại mức (Z/G, loại vùng, hợp lưu).

## 3. Đánh giá

- **Bước 2 (mô tả):** tỉ lệ giữ, và R của lệnh theo / lệnh ngược, chia theo 3 nhóm của từng đặc trưng volume (ngưỡng lấy từ train); cờ "đẩy láo"; cờ phân kỳ. So giữa các loại mức Z, G, F. Kiểm định xáo trộn: chênh lệch tỉ lệ giữ giữa nhóm volume cao và nhóm volume thấp có vượt ngẫu nhiên không.
- **Bước 3 (học cuốn chiếu hàng tháng, LightGBM):**
  - **V** = bối cảnh + volume;
  - **C** = chỉ bối cảnh (đối chứng: volume có thêm gì không);
  - **R** = chọn ngẫu nhiên cùng số lệnh mỗi tháng;
  - **mốc so sánh:** luật đơn giản S2 + ADX H1 ≥ 25 của G109.

  Quy tắc: nhóm 10% xác suất giữ cao nhất thì đi theo (S2); nhóm 10% thấp nhất thì đánh ngược (F). Ngưỡng lấy từ các tháng trước. Lệnh không chồng.
- **Kỳ:** train 07/2024–03/2025, validate 04–12/2025 (FX tới 10/2025). **Test 2026 niêm phong.**
- **Tiêu chí:** V hơn C và hơn R ở cả train lẫn validate; ít nhất 100 lệnh; cận dưới 90% > 0; báo riêng từng chiều và từng mã.
- **Mã:** vàng là chính; EURUSD/GBPUSD/USDJPY để kiểm tra.

## 4. Kiểm tra

- **Test:**
  - volume tương đối chỉ dùng các ngày trước;
  - delta giả và cờ "đẩy láo" trên dữ liệu giả lập;
  - nhãn giữ / thất bại;
  - lệnh theo và lệnh ngược;
  - không nhìn trước (dữ liệu đầy đủ so với dữ liệu cắt ngắn).
- **Audit độc lập:** tính lại sự kiện, nhãn, lệnh và các đặc trưng volume bằng vòng lặp thô.

## 5. Bổ sung: nhóm price action (đăng ký trước, 13/10/2026, trước khi xem kết quả bước 2)

Theo đề xuất của người dùng: nén rồi bung, vùng thiếu thanh khoản, vùng swing, phá swing, cờ tăng/giảm, nêm tăng/giảm. Mọi đặc trưng tính tại nến quyết định j, chỉ dùng nến ≤ j, đơn vị là ATR M30, theo chiều phá s.

| Nhóm | Đặc trưng |
|---|---|
| Nén rồi bung | `compress` (biên 12 nến trước phá), `nr7` (nến trước phá có biên hẹp nhất trong 7 nến), `expand` (biên trung bình 2 nến phá / biên trung bình 12 nến trước) |
| Vùng thiếu thanh khoản | FVG M5 (3 nến) trong 1 ngày trước, **chưa lấp**, nằm **phía trước** theo chiều phá: `void_ahead` (khoảng cách tới mép gần), `void_size`; `zone_ahead` = khoảng cách tới vùng thật G109 kế tiếp phía trước (lực cản) |
| Swing và cấu trúc | `bos_h1` = cú phá vượt luôn swing H1 gần nhất đã xác nhận (phá cấu trúc); `bos_dist`; `struct_m5` = HH/HL hay LH/LL của 2 swing M5 gần nhất theo chiều phá; loại mức G (swing M5) đã có |
| Cờ | `pole` = di chuyển theo chiều phá từ j−36 tới j−12; `cons_slope` = độ dốc giá đóng j−13..j−2 theo chiều phá; `flag_pat` = 1 khi pole ≥ 1,5, biên vùng tích lũy ≤ 1,0 và cons_slope ≤ 0 (cờ, phá theo chiều cột cờ) |
| Nêm | độ dốc đỉnh và đáy của 24 nến j−25..j−2: `wedge_type` = +1 nêm tăng (cả hai dương, hội tụ), −1 nêm giảm (cả hai âm, hội tụ); `wedge_with` = +1 khi phá đúng chiều kinh điển (nêm tăng phá xuống, nêm giảm phá lên), −1 khi ngược lại |
| Nến phá | `pa_close` = vị trí giá đóng trung bình của 2 nến phá trong biên nến, theo chiều phá |

**Đánh giá:**
- **Bước 2:** cùng bảng nhóm 3 phần / cờ và kiểm định xáo trộn như nhóm volume.
- **Bước 3:** thêm các biến thể mô hình:
  - **P** = bối cảnh + price action;
  - **VP** = bối cảnh + volume + price action;

  so với C (chỉ bối cảnh), V (bối cảnh + volume) và R (ngẫu nhiên). Chỉ giữ nhóm nào **hơn C ở cả train lẫn validate**.

Ghi chú khi viết test, trước khi có kết quả: "hội tụ" của nêm = độ dốc đáy − độ dốc đỉnh > 25% của độ dốc lớn hơn, để kênh song song không bị tính là nêm.
