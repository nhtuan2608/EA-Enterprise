# G111: thoái lui, Fibonacci, test vùng khi cạn volume và đảo chiều tại vùng / hợp lưu — kế hoạch đăng ký trước

Ngày 13/10/2026. Chỉ dùng dữ liệu MT5 (raw M5 có tick volume; EURUSD/GBPUSD đã đổi sang giờ server). Nối tiếp G109 (bản đồ vùng) và G110 (phá thật / phá giả).

**Ý của người dùng:**
- Test cạn volume.
- Test đảo chiều ở vùng nào, hợp lưu nào.
- Có cần Fibonacci từ đáy và đỉnh đầu ngày không; Fibonacci của nhịp tăng/giảm ngày hôm trước và hôm sau; giá thoái lui về mức nào.
- Tìm plan và sự lặp lại; kiểm tra bằng ngẫu nhiên để chọn lọc, rồi thêm vào những gì đã có.

**Kế thừa:**
- G109: vùng không hút giá hơn mức giả ở cùng khoảng cách. "Quét rồi rút râu" âm.
- G110 bước 2: "cạn volume trước khi phá" không giúp phân biệt phá thật / phá giả. Phân kỳ giá–delta, phá cấu trúc H1 và FVG phía trước thì có.

Vì vậy G111 xét **giá chạm vùng mà không phá** (test) thay vì phá.

## Phần A — thoái lui và Fibonacci: có lặp lại không

**Mức Fibonacci:**
- **Ngày hôm trước:** nhịp từ đáy tới đỉnh, hoặc từ đỉnh tới đáy, theo hướng của ngày đó (đóng cửa so với mở cửa). Các mức thoái lui 23,6 / 38,2 / 50 / 61,8 / 78,6%. Biết từ lúc mở ngày.
- **Trong ngày:** biên đỉnh–đáy của phiên Á (biết lúc 10:00 server) và của ngày tính đến 15:00 server (trước phiên Mỹ). Thoái lui theo hướng nhịp chính của khoảng đó.

**Mô tả:**
1. Hôm nay giá thoái lui sâu tới đâu trong biên ngày trước, trước khi đi tiếp theo hướng cũ hoặc đảo chiều. Phân bố độ sâu; có dồn quanh các tỉ lệ Fibonacci không.
2. Tỉ lệ chạm và tỉ lệ bật lại ở mỗi mức Fibonacci, so với **các mức "Fibonacci giả"** cùng biên (tỉ lệ 0,30 / 0,45 / 0,55 / 0,70) ở cùng khoảng cách tới giá. Đây là đối chứng chính cho câu hỏi "có cần Fibonacci không".

## Phần B — test vùng và đảo chiều

**Mức được xét:** vùng thật G109 (đầu ngày + trong ngày), mức Fibonacci phần A, Fibonacci giả, vùng giả G109.

**Sự kiện test:** lần đầu giá chạm biên của mức từ một phía, và nến M5 chạm đó **không đóng vượt mép xa**.

**Lệnh đảo chiều (T):**
- Limit tại mép gần, ngay lúc chạm. Nếu nến chạm đã khớp limit thì tính khớp ở mép gần.
- Stop: mép xa + 0,5 × bề rộng vùng + spread.
- Mục tiêu 2R. Có thêm mục tiêu "vùng kế tiếp phía sau", chỉ nhận khi RR ≥ 1.
- Giữ tối đa 4 giờ. Lọc chi phí như G109 (stop ≥ 8 spread, ATR M5 ≥ 3 spread, không vào 23:00–01:00).

**Đặc trưng (chỉ dùng nến tới lúc chạm):**
- **Cạn volume:** volume tương đối 6 và 12 nến tiếp cận; độ dốc volume; volume của nến chạm; tốc độ tiếp cận (ATR mỗi giờ).
- **Phân kỳ** giá–delta 12 nến khi tiếp cận (đặc trưng tốt nhất của G110).
- **Loại mức và hợp lưu:** loại vùng; số mức trong biên; có Fibonacci trùng vùng thật không; có số tròn không.
- **Bối cảnh như G110:** ADX H1, chiều so với D1, phía EMA200 H4, giờ; FVG phía sau (mức có nằm trong khoảng trống giá không); phá cấu trúc H1 gần đây.

**Đánh giá:**
- **Bước 2:** tỉ lệ đảo chiều thành công và R của lệnh T theo loại mức, theo hợp lưu, theo nhóm cạn volume. So với Fibonacci giả, vùng giả và vào ngẫu nhiên (cùng ngày, cùng chiều, cùng khoảng stop và RR). Kiểm định xáo trộn như G110.
- **Bước 3:** học cuốn chiếu hàng tháng (LightGBM). Vào lệnh T ở nhóm 10% xác suất đảo chiều cao nhất (ngưỡng lấy từ các tháng trước), lệnh không chồng.

  So sánh 4 biến thể:
  - **C** = chỉ bối cảnh;
  - **+V** = thêm cạn volume và phân kỳ;
  - **+F** = thêm Fibonacci và hợp lưu;
  - **+VF** = thêm cả hai.

  Đối chứng là chọn ngẫu nhiên. Chỉ giữ nhóm nào hơn C ở cả train lẫn validate.

## Phần C — đưa vào những gì đã có

Nếu Fibonacci hơn Fibonacci giả ở phần A hoặc B, thêm Fibonacci vào bản đồ vùng G109. Sau đó chạy lại:
- nhận định đầu ngày (G109 bước 2);
- sự kiện phá (G110) với các mức Fibonacci.

Nếu không hơn, ghi rõ là không cần Fibonacci.

## Kỳ, tiêu chí, kiểm tra

- **Kỳ:** train 07/2024–03/2025, validate 04–12/2025 (FX tới 10/2025). **Test 2026 niêm phong.** Vàng là chính; EURUSD/GBPUSD/USDJPY để kiểm tra.
- **Tiêu chí:** như G110. Ít nhất 100 lệnh; cận dưới 90% > 0; hơn các đối chứng ở cả hai kỳ; báo riêng từng chiều và từng mã.
- **Test:**
  - mức Fibonacci của ngày trước chỉ dùng dữ liệu ngày trước;
  - Fibonacci trong ngày chỉ có sau khi biên đã hình thành;
  - sự kiện test (chạm mà không đóng vượt);
  - lệnh T;
  - không nhìn trước.
- **Audit độc lập:** tính lại bằng vòng lặp thô.
