# G156a2 — đặt lại Q1 / Q4 tính từ giá hiện tại: phá giả hay đi tiếp **không đoán được từ giá** (24/10/2026)

Kế hoạch: [2026-10-24-g156a2-repose-from-price.md](../plans/2026-10-24-g156a2-repose-from-price.md) (commit `1c0a038`). Script
[`g156a2_repose.py`](../../research/long/g156a2_repose.py); mỏ neo chạy lại bằng `g156b_anchor.py --repose`. Kết quả
`research/long/results/g156a2/`, `results/g156b2/`.

## Định nghĩa mới

Hai mốc đối xứng tính từ giá đóng lúc hỏi:
- **Q1b**: ± 1 ATR M30, trong 4 giờ;
- **Q4b**: ± 1R, tới khi chân thoát.

Với bước ngẫu nhiên, mỗi bên khoảng 50 %.

## Phân bố đáp án

**Q1b** (12.577 sự kiện phá mức): đi tiếp 46,8 %, giả 45,3 %, lưỡng lự 5,5 %, cả hai trong một nến 2,3 %.

Tỷ lệ đi tiếp trong các lần đã phân định, theo năm:

| 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| 54 % | 52 % | 50 % | 45 % | 53 % | 52 % | 51 % | 52 % | 51 % |

Theo loại mức (phân định): 48–55 % mọi loại (biên Á 48–51 %, đỉnh/đáy ngày trước 51–55 %, tuần 52–54 %, swing 49–52 %).

**Q4b** (25.625 lần kiểm lệnh đang mở): đi tiếp 44,3 %, ngược 26,4 %, đóng trước 29,0 %.

| Nhóm | Số lần phân định | Đi tiếp |
|---|---|---|
| lệnh đang lời | 16.834 | **61 %** (theo năm 54–69 %) |
| lệnh đang lỗ | 1.282 | 86 %, **suy biến**: mốc −1R của lệnh lỗ nằm sau SL, nên hiếm khi chạm. Không dùng con số này |

## Mỏ neo chạy lại (luật G156b)

| Câu | Mỏ neo | Kỹ năng so với tỷ lệ nền (kiểm) | AUC tốt nhất | Bối cảnh có giá trị |
|---|---|---|---|---|
| Q1b | **M0: tỷ lệ nền khoảng 51 %** | M1 −0,003 · M2 −0,008 · M3 −0,016 | 0,50–0,52 | **không** |
| Q4b | M1 (R đang có × D1) | +0,026, 95 % [−0,004; 0,057] | 0,64 | **không** (cận dưới < 0) |

Q1b: mọi mô hình đều **thua** việc cứ đoán tỷ lệ nền, ở cả kỳ chọn, kỳ kiểm và kỳ sau. Trường quan trọng nhất cũng chỉ làm Brier đổi
≤ 0,002.

## Kết luận

1. **Khi bỏ hình học ra, phá giả hay đi tiếp gần như tung đồng xu**: khoảng 51 / 49, ổn định 2018–2026. Không trường bối cảnh giá nào
   (chế độ D1, phiên, biến động, VWAP, khoảng cách tới các mức, tin, spread...) đoán tốt hơn.
   - Khớp B1 (hướng giá ngắn hạn gần như ngẫu nhiên), G95 F1, G97, G146.
   - Kỹ năng của G156b ở Q1 là hình học của câu hỏi cũ.
2. **Bộ kiến thức cần sửa B8.** G110 ("phá thật / giả đoán được, AUC 0,70") cũng dùng định nghĩa "giữ được / quay lại mức". Định nghĩa đó
   có cùng phần hình học. Đã ghi chú vào bộ kiến thức.
3. **Lệnh S07 đang lời đi tiếp +1R trước khi lùi 1R ở 61 %**: đó là lợi thế xu hướng của chính S07 (A8). Đây là tỷ lệ nền chứ không phải
   bối cảnh: chia theo R đang có và chế độ D1 không cải thiện chắc chắn. Lưu ý: có những lần bot thoát trước khi chạm mốc nào (đóng
   trước), những lần này không được tính.
4. **Hệ quả cho hội đồng AI (quan trọng nhất)**:
   - Với câu "phá giả hay đi tiếp", **mỏ neo là 51 %**. Mọi agent dựa trên đọc biểu đồ / bối cảnh giá **không có cơ sở** để làm tốt hơn
     tung đồng xu.
   - Nếu hội đồng làm tốt hơn trên forward, giá trị đó phải đến từ **thông tin ngoài giá**: nội dung tin, sự kiện bất thường, thực thi
     broker.
   - Hội đồng **không nên** được thiết kế quanh việc "đọc chart để đoán phá giả". Nên tập trung vào:
     - (a) sự kiện và tin bằng chữ;
     - (b) bất thường và rủi ro thực thi;
     - (c) giám sát bot lệch dấu vân tay;
     - (d) giải thích.
5. Với quản lý lệnh: lệnh S07 đang lời **nên được để chạy** (61 % đi tiếp). Mọi kế hoạch "giảm / chốt sớm" của hội đồng phải thắng con số
   này trên forward mới được áp dụng.
