# G156a — bộ phát câu hỏi, gói bối cảnh, cách chấm: dựng lại trên lịch sử (24/10/2026)

Kế hoạch: [2026-10-24-g156a-questions-context-labels.md](../plans/2026-10-24-g156a-questions-context-labels.md) (commit `3aa3ad8`). Script
[`g156a_questions.py`](../../research/long/g156a_questions.py). Kết quả `research/long/results/g156a/` (Q1–Q4.csv, summary.json). Dữ liệu
XAUUSD M30, 05/2018 → 10/2026. Bước này **chỉ mô tả**, không chọn ngưỡng giao dịch.

## Ba kiểm tra bắt buộc

| Kiểm tra | Kết quả | Đạt |
|---|---|---|
| Không nhìn trước: tính lại gói bối cảnh trên dữ liệu bị cắt tại nến sự kiện, 300 sự kiện ngẫu nhiên | 0 sai lệch | **đạt** |
| Hội đồng họp trung bình ≤ 6 giờ / ngày (Q1–Q3) | **5,96** giờ / ngày, sát ngưỡng | đạt |
| Mỗi đáp án Q1 và Q4 ≥ 5 % | Q1: LƯỠNG LỰ chỉ 0,3 % | **không đạt (Q1)** · Q4 đạt |

Q1 thực tế là câu hỏi **hai đáp án** (đi tiếp / giả). Theo kế hoạch: không chỉnh ngưỡng ở đây; muốn đổi thì làm kế hoạch mới.

## Số câu hỏi mỗi tuần

| Q1 phá mức | Q2 tín hiệu S07 | Q3 S07 đủ 4/5 | Q4 lệnh đang mở (mỗi giờ) |
|---|---|---|---|
| 28,8 | 1,6 | 18,2 | 58,7 |

## Q1 — phá giả hay đi tiếp (4 giờ, ngưỡng 1 ATR M30)

| Loại mức | Số lần | Đi tiếp | Giả |
|---|---|---|---|
| Biên Á trên / dưới | 1.414 / 1.276 | 64 % / 64 % | 35 % / 36 % |
| Đỉnh / đáy ngày trước | 1.007 / 808 | 68 % / 67 % | 31 % / 33 % |
| Đỉnh / đáy tuần trước | 230 / 168 | 69 % / 73 % | 31 % / 27 % |
| Swing đỉnh / đáy M30 | 3.973 / 3.701 | 66 % / 67 % | 34 % / 33 % |

**Rất ổn định theo năm**: tỷ lệ "giả" 31–36 % ở mọi năm 2018–2026, mọi kỳ.

**Lưu ý về định nghĩa:**
- 1 ATR M30 là khoảng nhỏ, nên "đi tiếp" ở đây chỉ là **giá đi thêm một đoạn ngắn**. Không mâu thuẫn với B2 của bộ kiến thức ("biên Á bị
  phá rồi kéo về 80–92 %"): B2 tính cả việc **chạm lại** biên bất cứ lúc nào trong ngày, còn ở đây tính **nến đóng quay lại trước khi đi
  thêm 1 ATR**.
- Hai câu hỏi khác nhau thì cho tỷ lệ khác nhau. Hội đồng phải luôn biết đang trả lời câu nào.
- Nếu muốn câu hỏi "phá giả kiểu MM" khó hơn (ví dụ đi thêm 2 ATR, hoặc ATR H1), cần một kế hoạch mới. Không đổi ở đây.

## Q2 — tín hiệu S07: chỉ 29 % lệnh gốc thắng

| Kỳ | 05/2018–2021 | 2022–2023 | 2024–06/2026 | sau 07/2026 |
|---|---|---|---|---|
| Tỷ lệ lệnh gốc có R > 0 | 26 % | 28 % | 32 % | 29 % |

S07 thắng ít nhưng thắng lớn (TP 8R, giữ theo xu hướng), nên vẫn +0,34R/chân.

**Hệ quả quan trọng cho hội đồng: phải chấm Q2 bằng R kỳ vọng, không bằng xác suất thắng.**
- Một hội đồng "bỏ những lệnh có khả năng thua" sẽ bỏ gần hết lệnh và giết lợi thế của S07.
- Câu hỏi Q2 phải là "R kỳ vọng của lệnh này cao hay thấp hơn bình thường", không phải "lệnh này thắng không".

## Q3 — vào sớm khi S07 mới đủ 4/5 điều kiện

| Số lần 4/5 | S07 vào thật trong 2 giờ | Giá vào sớm tốt hơn (khi S07 có vào) |
|---|---|---|
| 7.931 (18 / tuần) | **5,6 %** | trung vị **+0,28R**, trung bình +0,28R |

- 94 % số lần "đủ 4/5" **không bao giờ** thành lệnh S07 trong 2 giờ.
- Vào sớm chỉ đáng khi hội đồng đoán trước được rất chính xác lần nào sẽ hoàn tất. Lấy tạm khoảng 1R thiệt mỗi lệnh sớm hỏng (con số này
  phải đo ở G156b): mỗi lệnh hỏng mất cỡ 1R, còn mỗi lệnh trúng chỉ lợi khoảng 0,28R. Như vậy cần độ chính xác khoảng 78 % trở lên mới
  hòa, trong khi tỷ lệ nền chỉ 5,6 %.
- Khớp với G73 (vào sớm dính phá giả). Câu hỏi Q3 vẫn được giữ ở dạng ảo để đo, nhưng kỳ vọng rất thấp.

## Q4 — lệnh đang mở: đi tiếp +1R hay quay về giá vào

| Lúc kiểm tra | Số lần | Đi tiếp | Quay về | Đóng trước |
|---|---|---|---|---|
| Lệnh **đang lời** | 22.116 | 48 % | 25 % | 28 % |
| Lệnh **đang lỗ** | 3.509 | 0 % | 100 % | — |

- Với lệnh đang lỗ, định nghĩa suy biến: giá vào nằm ngay trên đường đi tới +1R. Từ G156b, **Q4 chỉ hỏi cho lệnh đang lời**; lệnh lỗ để
  luật S07 quản lý. Đây là điều chỉnh phạm vi, không đổi cách chấm.
- Theo kỳ, đi tiếp: 05/2018–2021 34 %, 2022–23 37 %, 2024–06/2026 **48 %**, sau 07/2026 34 %. Phụ thuộc chế độ thị trường, khớp A6–A8.

## Rút ra cho bước 2b (mỏ neo) và thiết kế hội đồng

1. Đường ống câu hỏi + bối cảnh + đáp án **dùng được**, không nhìn trước, tần suất họp vừa ngưỡng (khoảng 6 giờ / ngày).
2. Q1 có tỷ lệ nền rất ổn định (khoảng 66 / 34). Mỏ neo phải trả lời: bối cảnh (D1, khoảng cách, phiên, biến động...) có làm tỷ lệ này
   đổi khác một cách ổn định không.
3. Q2 phải chấm bằng **R**, không bằng tỷ lệ thắng.
4. Q3: vào sớm gần như chắc chắn không đáng, trừ khi mỏ neo cho thấy có nhóm 4/5 hoàn tất với xác suất rất cao.
5. Q4 chỉ cho lệnh đang lời.
