# G113: lợi thế thô (không chi phí), setup trên khung lớn hơn, phân loại kiểu ngày — kế hoạch đăng ký trước

Ngày 14/10/2026. Theo yêu cầu người dùng: chưa cần quan tâm chi phí, làm cả 3 hướng. Chỉ dùng dữ liệu MT5 (raw; EURUSD/GBPUSD đổi sang giờ server). Kỳ như cũ: train 07/2024–03/2025, validate 04–12/2025 (FX tới 10/2025). **Test 2026 niêm phong.**

## 1. Lợi thế thô: spread = 0 (`G109_NOCOST=1`, hậu tố `_nc`)

Chạy lại các setup G109–G112 với spread bằng 0, nên bộ lọc chi phí cũng không còn tác dụng. Mức và vùng giữ nguyên, lấy từ các lần chạy có spread.

**Câu hỏi:** setup nào có R/lệnh > 0 **trước chi phí**, ở cả train lẫn validate, và hơn đối chứng?
- Không có ⇒ loại hẳn, vì giảm chi phí cũng không cứu được.
- Có ⇒ đưa sang hướng 2 (khung lớn) hoặc tìm cách giảm chi phí.

## 2. Khung lớn hơn (`G113_TF=15` hoặc `30`, hậu tố `_m15` / `_m30`)

- Gộp nến M5 thành M15/M30, spread lấy trung bình của các nến M5 bên trong.
- Dựng lại bản đồ vùng G109, sự kiện phá G110, test vùng G111, tín hiệu đuổi G112 trên khung đó. Các tham số đếm theo số nến giữ nguyên (ví dụ giữ tối đa 48 nến = 12 giờ ở M15, 24 giờ ở M30).
- Chạy cả có spread và spread = 0.

**Câu hỏi:** trên khung lớn hơn, cùng spread chiếm tỉ lệ nhỏ hơn so với stop. Các nhóm dương thô ở M5 có trở thành dương sau chi phí không? Có nhóm mới dương ở cả hai kỳ không?

## 3. Kiểu ngày (`g113_daytype.py`)

**Nhãn sau ngày** (chỉ để học và chấm):
- **ngày xu hướng:** |đóng − mở| / (cao − thấp) ≥ 0,6;
- **ngày đi ngang:** ≤ 0,3;
- còn lại là ngày trung gian.

**Đặc trưng lúc mở phiên Âu (10:00 server), chỉ dùng dữ liệu trước đó:**
- biên phiên Á / ATR D1, hướng và độ mạnh của phiên Á;
- biên ngày trước / ATR D1, tỉ lệ thân / biên của ngày trước;
- ADX D1, chế độ D1, phía EMA200 H4;
- volume tương đối của phiên Á;
- thứ trong tuần.

**Bước A:** học cuốn chiếu hàng tháng (hồi quy logistic và LightGBM) dự báo "ngày xu hướng". So độ chính xác / AUC với tỉ lệ nền và với "lặp lại kiểu ngày hôm trước".

**Bước B, chọn setup theo kiểu ngày dự báo** (chỉ các lệnh từ 10:00 trở đi):
- ngày dự báo **xu hướng** → lệnh theo đà (G110 theo, G112 đuổi);
- ngày dự báo **đi ngang** → lệnh đảo chiều (G110 ngược, G111 test vùng).

So với ba mốc:
- không phân loại (lấy mọi lệnh);
- **phân loại ngẫu nhiên** (xáo dự báo giữa các ngày, 200 lần);
- **phân loại hoàn hảo** dùng nhãn sau ngày. Đây chỉ là mức trần tham khảo, không giao dịch được.

**Tiêu chí:** chọn setup theo dự báo phải hơn không phân loại và hơn phân loại ngẫu nhiên ở **cả hai kỳ**, ít nhất 100 lệnh, báo riêng từng mã. Chạy với spread thật, kèm bản spread = 0.

## Kiểm tra

- **Test:**
  - spread = 0 thật sự bằng 0 sau khi nạp;
  - gộp nến M15/M30 đúng (open đầu, high max, low min, close cuối, volume tổng);
  - mốc thời gian đóng nến dùng đúng `BAR_SEC`;
  - đặc trưng kiểu ngày chỉ dùng dữ liệu trước 10:00;
  - nhãn kiểu ngày;
  - chọn setup theo dự báo không dùng nhãn.
- **Audit độc lập:**
  - tính lại bằng vòng lặp nến M15/M30 gộp, các audit hiện có chạy trên khung mới;
  - tính lại đặc trưng và nhãn kiểu ngày cho các ngày ngẫu nhiên.
