# G121: cung–cầu không dựa vào chỉ báo — dòng lệnh từ tick và volume profile — kế hoạch đăng ký trước

Ngày 15/10/2026. Người dùng muốn phương pháp mới, **độc lập** với S07 và VHedge, xác nhận cung–cầu mà không dựa nhiều vào chỉ số tính toán. Sau đó so dần với các bot đang có.

## Dữ liệu và kỳ

**Dữ liệu:** XAUUSD-VIP, **tick thật** của terminal (chỉ đọc), từ 20/02/2024. Script `research/long/g121_ticks.py`.
- Chỉ dùng tick có giá bid thay đổi.
- Theo từng nến M5: n, up, down, delta = up − down, số tick ở 20% trên / 20% dưới của nến.
- Theo từng ngày server: số tick theo bậc giá $0,5.

| Kỳ | Thời gian | Ghi chú |
|---|---|---|
| Train | 03/2024–06/2025 | chọn biến thể |
| Validate | 07–12/2025 | |
| Test | năm 2026 | **kín**, mở một lần |

**ATR:** chỉ dùng ATR14 M5 để đo khoảng cách stop. Không dùng chỉ báo nào khác.

## A. Dòng lệnh từ tick (M5)

Các đại lượng ở nến i:
- **Hoạt động:** n so với trung bình 20 nến trước.
- **Chủ động:** d = delta / n, từ −1 đến +1.
- **Vị trí đóng cửa** trong nến; mức cao/thấp nhất 24 nến.

| Mã | Tín hiệu | Ý nghĩa cung–cầu |
|---|---|---|
| **A1** hấp thụ ở đỉnh | Nến chạm mức cao nhất 24 nến, hoạt động ≥ 1,5 lần trung bình, mua chủ động mạnh (d thuộc 1/3 cao nhất), nhưng đóng ở nửa dưới nến → **BÁN** | Bên mua đẩy mạnh nhưng bị chặn |
| **A1** hấp thụ ở đáy | Đối xứng → **MUA** | |
| **A2** kiệt sức | Giá lập đỉnh 24 nến mới, nhưng tổng delta của nhịp lên (từ đáy 24 nến gần nhất tới nay) thấp hơn tổng delta của nhịp lên tới đỉnh trước đó → **BÁN** (đối xứng → MUA) | Đỉnh mới mà lực mua yếu dần |
| **A3** lực chủ động | Nến đóng phá mức cao 24 nến, hoạt động ≥ 1,5 lần, d thuộc 1/10 cao nhất → **MUA theo** (đối xứng) | Có lực thật theo chiều phá |

**Lệnh cho A:**
- Vào ở giá mở nến kế tiếp. Stop ở cực trị nến tín hiệu ± 0,1 ATR, trong khoảng 0,5–4 ATR.
- Thoát (thử cả ba): TP 2R; TP 3R; thoát cấu trúc (nến M5 đóng qua cực trị của nến trước đó sau khi đạt +1R).
- Đóng sau tối đa 48 nến (4 giờ).

Ngưỡng tam phân vị / thập phân vị lấy từ dữ liệu train.

## B. Volume profile (từ tick theo mức giá của ngày trước)

Profile ngày trước gồm:
- **POC:** bậc giá nhiều tick nhất.
- **Vùng giá trị VA:** 70% số tick quanh POC, có cạnh trên VAH và cạnh dưới VAL.
- **LVN:** bậc giá trong VA có số tick < 25% POC.

| Mã | Tín hiệu | Lệnh |
|---|---|---|
| **B1** quay lại vùng giá trị ("luật 80%") | Ngày mở cửa ngoài VA của hôm qua, sau đó 2 nến M5 liên tiếp đóng bên trong VA | Vào theo chiều vào VA. Mục tiêu cạnh VA bên kia, stop cách cạnh vừa vào lại 1 ATR |
| **B2** bị từ chối ở cạnh | Nến M5 chạm VAH/VAL/POC hôm qua (lần đầu trong ngày) rồi đóng lại ở phía cũ | Vào ngược chiều chạm, mục tiêu POC (nếu chạm POC thì mục tiêu VAH/VAL theo chiều), stop ngoài mức + 0,5 ATR |
| **B3** qua vùng mỏng | Nến M5 đóng vượt qua một LVN của hôm qua | Vào theo chiều, mục tiêu bậc dày kế tiếp, stop phía bên kia LVN + 0,5 ATR |

Với B: đóng lệnh trước giờ đóng cửa ngày server. Tối đa 1 lệnh mỗi kiểu mỗi ngày.

## Đối chứng

- **A:** vào lệnh ở nến ngẫu nhiên **cùng giờ trong ngày** và cùng chiều, cùng cách đặt stop/thoát, cùng số lệnh, 200 lần.
- **B:** **mức giả** = các mức VAH/VAL/POC/LVN dịch đi một khoảng ngẫu nhiên (±1–3 lần độ rộng VA), cùng luật vào/ra, 200 lần (cách G109).

## Tiêu chí đạt (mỗi tín hiệu × một cách thoát)

1. Train và validate đều có R/lệnh > 0, với ≥ 60 lệnh ở train.
2. Thắng đối chứng với p < 0,10 ở validate.
3. Lợi nhuận đến từ cả mua lẫn bán (không chiều nào âm rõ), hoặc ghi rõ nếu chỉ một chiều.

Ô đạt sẽ được đưa vào kỳ test 2026 một lần, rồi so với S07, VHedge và XauRegime trên cùng kỳ, cùng rủi ro 1,5%/lệnh, INITIAL.
