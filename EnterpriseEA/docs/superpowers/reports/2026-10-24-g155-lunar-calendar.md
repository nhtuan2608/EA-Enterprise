# G155 — âm lịch, sóc/vọng, tiết khí với vàng và S07 (24/10/2026)

Kế hoạch đăng ký trước: [2026-10-24-g155-lunar-calendar.md](../plans/2026-10-24-g155-lunar-calendar.md) (commit `78dbe96`). Script
[`g155_lunar.py`](../../research/long/g155_lunar.py). Âm lịch tính bằng `lunar_python`, cùng thư viện gốc với Ching-Oracle.

**Kết luận: KHÔNG ĐẠT ở cả 3 mục tiêu.** Không ô âm lịch nào vượt được mức có thể xảy ra do may.

Sửa trước khi chốt số: bảng tiết khí của thư viện ghi vài tiết đầu năm sau bằng phiên âm (`DA_HAN`, `LI_CHUN`...). Đã gộp về đúng 24 tên.
Kết quả không đổi.

## Kết quả

| Mục tiêu | Mẫu | Ô mạnh nhất | t | **p cả họ** | Mức \|t\| do may (p95) | Cùng dấu 3 kỳ | Kết luận |
|---|---|---|---|---|---|---|---|
| T1 hướng giá ngày | 4.342 ngày (2010–06/2026) | tháng 7 âm (+0,10 vs +0,02 ATR) | 2,28 | **0,66** | 3,35 | không | KHÔNG ĐẠT |
| T2 biến động ngày | 4.342 ngày | tiết Tiểu Mãn 小满 (0,91 vs 1,03 ATR) | −3,56 | **0,59** | 5,09 | có | KHÔNG ĐẠT |
| T3 R chân S07 | 1.208 chân (05/2018–06/2026) | tiết Sương Giáng 霜降 (−0,23 vs +0,37R) | −4,06 | **0,72** | 8,61 | có | KHÔNG ĐẠT |

Riêng **sóc / vọng** (trăng non, trăng tròn):
- vàng: không khác gì (t −1,5 tới +0,4);
- S07 vào lệnh quanh rằm: −0,06R so với +0,39R (t −3,3), nhưng cũng nằm trong mức do may của S07.

## Điểm đáng học: vì sao t = −4 mà vẫn không có ý nghĩa

Với phép t thông thường:
- t −4,06 của tiết Sương Giáng trên S07 tương đương p khoảng 0,00005, nghe như một phát hiện;
- quanh rằm (t −3,3) cũng vậy.

Nhưng **đối chứng dịch nhãn** cho thấy dịch âm lịch đi một khoảng ngẫu nhiên vẫn thường tạo ra ô có |t| tới 4,9 (trung vị) và 8,6 (p95). Lý do:
- lệnh S07 đi theo cụm: một đợt xu hướng sinh nhiều chân cùng vài ngày, nên thắng hay thua theo cả cụm;
- 59 chân trong tiết Sương Giáng thực ra chỉ là vài đợt, mỗi năm một đợt;
- thêm 42 ô được thử cùng lúc.

Phép t thường bỏ qua cả hai điều này. Phép dịch nhãn thì giữ nguyên chúng. Vàng theo ngày ít bị cụm hơn, nên mức do may thấp hơn (3,4–5,1), nhưng
các ô thật vẫn không vượt qua.

## Kết luận

Theo luật đăng ký: âm lịch, sóc/vọng, tiết khí và tháng âm **không có tác dụng đo được** lên hướng giá vàng, biến động vàng hay kết quả S07,
2010–2026.

Cùng với G147 (lịch dương): hiệu ứng lịch không phải nguồn lợi thế cho hệ thống này. Ching-Oracle nên giữ đúng vai trò của nó (suy ngẫm,
học), không nối vào quyết định vào lệnh hay rủi ro.
