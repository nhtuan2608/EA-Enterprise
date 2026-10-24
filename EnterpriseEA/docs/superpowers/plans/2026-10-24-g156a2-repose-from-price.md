# G156a2: đặt lại Q1 và Q4 tính từ giá hiện tại — kế hoạch đăng ký trước (24/10/2026)

## Vì sao

G156b cho thấy kỹ năng của mỏ neo ở Q1 và Q4 phần lớn là **hình học của câu hỏi**:
- Q1 tính mốc "đi tiếp" từ mức bị phá, nên nến đã đóng xa mức gần như chắc chắn "đi tiếp";
- Q4 tính mốc "quay về" tại giá vào, nên lệnh lời càng nhiều càng khó "quay về".

Để chấm được **phán đoán** của mỏ neo và của hội đồng, hai câu hỏi được đặt lại với **hai mốc đối xứng tính từ giá đóng lúc hỏi**. Q2 và
Q3 giữ nguyên.

## Định nghĩa mới

Giá lúc hỏi p0 = giá đóng nến M30 sự kiện. Chiều d = chiều phá (Q1) hoặc chiều lệnh (Q4). Xét từ nến kế tiếp.

| Câu | Đơn vị khoảng | Thời hạn | ĐI TIẾP | NGƯỢC LẠI | không rõ |
|---|---|---|---|---|---|
| **Q1b** (mọi sự kiện phá mức của G156a) | 1 ATR14 M30 của nến sự kiện | 8 nến (4 giờ) | chạm p0 + d × 1 ATR trước | chạm p0 − d × 1 ATR trước (**GIẢ**) | không chạm mốc nào: **LƯỠNG LỰ** |
| **Q4b** (mỗi giờ tròn khi một chân S07 đang mở, **cả lệnh lời lẫn lỗ**) | 1R = khoảng stop ban đầu của chân | tới khi chân thoát | chạm p0 + d × 1R trước | chạm p0 − d × 1R trước (**NGƯỢC**) | chân thoát trước: **ĐÓNG TRƯỚC** |

Ghi chú:
- Q1b, Q4b: một nến chạm cả hai mốc thì tính **CẢ HAI** và loại khỏi việc chấm (báo số lượng).
- Q1b: với bước ngẫu nhiên không trôi, P(ĐI TIẾP) ≈ 50 %. Lệch khỏi 50 % mới là thông tin.

## Mỏ neo

Chạy lại **y nguyên** G156b (M0–M3, cuốn chiếu, chọn 2020–2023, kiểm 2024–06/2026, bootstrap khối tuần, cùng luật "bối cảnh có giá trị"),
chỉ thay đáp án. Hai điều chỉnh phạm vi:
- **Q1b**: bỏ LƯỠNG LỰ và CẢ HAI khi chấm;
- **Q4b**: dùng mọi chân đang mở (không lọc "đang lời"). Bỏ ĐÓNG TRƯỚC và CẢ HAI khi chấm.

Q2 và Q3 không chạy lại.

## Báo cáo

- Phân bố đáp án theo kỳ và năm.
- Kết quả mỏ neo theo luật G156b.
- Trường quan trọng.
- So sánh với Q1 / Q4 của G156b, để thấy phần hình học chiếm bao nhiêu.

Script `research/long/g156a2_repose.py` (dùng lại hàm của `g156a_questions.py`), kết quả `research/long/results/g156a2/` và
`research/long/results/g156b2/`. Không chỉnh định nghĩa sau khi chạy.
