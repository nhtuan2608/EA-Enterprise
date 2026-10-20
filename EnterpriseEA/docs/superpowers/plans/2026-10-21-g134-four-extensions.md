# G134: bốn hướng mở rộng sau tổng hợp mọi setup — kế hoạch (21/10/2026)

Người dùng đồng ý làm cả 4 hướng mở rộng (trả lời G133). Không hướng nào còn kỳ kín mới. Vì vậy G134 là **tính lại sổ, so sánh và forward**, không phải kiểm định mới. Mọi con số dùng chi phí khắt khe như các nghiên cứu nguồn.

## 1. Trọng số golden/death cross D1 cho S07

- **Nguồn**: G133 phần 2 đạt; bộ lọc được chọn trên 2018–2025 và đã xác nhận trên 2026.
- **Sổ**: chân S07 (G89/G107). Trạng thái SMA50/SMA200 của nến D1 đã đóng tại lúc vào.
- **Biến thể kích thước** cho lệnh **ngược** trạng thái:

| Mã | Lệnh ngược trạng thái |
|---|---|
| W1.0 | không đổi (gốc) |
| W0.5 | × 0,5 |
| W0 | bỏ |

- **Mô phỏng** như G128: vốn 10.000, 1,5% × trọng số EA, lãi kép.
- **Báo cáo theo kỳ**: train / validate / 2026, với %/năm, DD, MAR.
- **Chọn trước**: W0.5. Chỉ đổi sang W0 nếu W0.5 có MAR thấp hơn gốc ở bất kỳ kỳ nào.

## 2. S07 khung H1 như một bot riêng

- **Luật** G67 cuối (gốc + B6, thoát đóng ngược EMA55, TP 8R) trên H1, cửa sổ nén 4 giờ (4 nến), nghỉ 2 nến, giữ tối đa 120 nến.
- **Báo cáo**:
  - theo kỳ (2018–07/2021 chưa dùng, train, validate, test, 07/2026+);
  - mua và bán riêng;
  - đối chứng ngẫu nhiên.
- **So với S07 M30** (sổ G89):
  - tỷ lệ lệnh H1 trùng thời gian và cùng chiều với một chân M30;
  - danh mục M30 + H1 (1,5% mỗi lệnh) so với M30 một mình (MAR theo kỳ).

## 3. Nến V M30 (G118 ứng viên A) — tái lập và forward

- **Luật**: nến V cắt EMA200, giá quay về trong 6 nến, quản lý hedge G116, stop ± 2 ATR. Điều kiện ở nến V:
  - EMA21/55/100 xòe ngược chiều nến V;
  - ADX < 25;
  - dốc EMA200 ngược chiều nến V.
- **Tái lập trên dữ liệu nghiên cứu**: phải ra khoảng 211 nhóm, +0,42U.
- **Forward**: dựng trên nến M30 của terminal (chỉ đọc). Plan và nến dùng **cùng một bản nến trong một lần chạy** (bài học G108). Ghi mọi nhóm từ 10/10/2026, có kết quả nếu đã đóng.

## 4. CtxBox chiều mua (G106) — forward

- Chạy `g106_shadow.py` (forward từ 12/10/2026, chỉ đọc nến terminal). Báo cáo các lệnh ảo M5/M15/M30/H1.

## Đầu ra

`research/long/g134_extensions.py`, báo cáo `reports/2026-10-21-g134-four-extensions.md`.
