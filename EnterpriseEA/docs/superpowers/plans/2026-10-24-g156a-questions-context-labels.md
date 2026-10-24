# G156a: bộ phát câu hỏi, gói bối cảnh và cách chấm đáp án — kế hoạch đăng ký trước (24/10/2026)

Bước 2a của thiết kế [bộ não + hội đồng AI](../specs/2026-10-24-ai-brain-council-design.md). Mục tiêu: định nghĩa **khách quan, không
nhìn trước** cho:
- câu hỏi mà hệ thống tự đặt;
- dữ liệu gửi kèm;
- cách gán đáp án sau khi sự việc xảy ra.

Sau đó dựng lại toàn bộ trên lịch sử để biết hội đồng sẽ phải họp bao nhiêu và đáp án phân bố thế nào. Bước này **không chọn setup, không
quyết định giao dịch**. Bước 2b (mỏ neo) và G156 (hội đồng forward) dùng lại y nguyên các định nghĩa này.

## Dữ liệu và kỳ

- Nến **M30** XAUUSD (`data/m30v`, giờ server), 01/05/2018 → hết dữ liệu. Nến trong ngày thật có từ 19/03/2018.
- Lịch tin USD HIGH của MT5 (`research/calendar`, giờ server).
- Sổ S07 M30 bản Python G89 (gốc + bồi + vào sớm + vào lại, cả hai chiều).
- Chia kỳ để báo cáo độ ổn định: 05/2018–2021, 2022–2023, 2024–06/2026, sau 07/2026.

## Bốn loại câu hỏi

Mọi câu hỏi phát ra ở **giá đóng của một nến M30 đã đóng**. Chỉ dùng dữ liệu tới nến đó.

### Q1 — PHÁ MỨC: phá giả hay đi tiếp?

**Các mức:**

| Mức | Định nghĩa | Hiệu lực |
|---|---|---|
| Biên Á | cao / thấp nhất các nến 01:00–07:59 của ngày server | 08:00 → hết ngày |
| Đỉnh / đáy ngày trước (PDH / PDL) | của ngày server trước | cả ngày |
| Đỉnh / đáy tuần trước (PWH / PWL) | của tuần server trước (thứ Hai–thứ Sáu) | cả tuần |
| Swing M30 | nến có đỉnh (đáy) cao (thấp) nhất trong 6 nến mỗi bên; chỉ dùng sau khi đủ 6 nến bên phải | 5 ngày, hoặc tới khi bị phá |

**Sự kiện:** nến M30 **đầu tiên đóng vượt** mức (đóng > mức với đỉnh, < mức với đáy) trong khi nến trước đóng chưa vượt. Mỗi mức chỉ sinh
một sự kiện trong thời gian hiệu lực. Chiều d = chiều phá.

**Đáp án**: xét từ nến kế tiếp, tối đa 8 nến (4 giờ); A = ATR14 M30 của nến sự kiện.

| Đáp án | Điều kiện |
|---|---|
| **ĐI TIẾP** | giá chạm mức + d × 1 A trước khi có nến đóng quay lại phía bên kia mức |
| **GIẢ** | có nến đóng quay lại phía bên kia mức trước khi chạm + 1 A |
| **LƯỠNG LỰ** | không điều nào xảy ra trong 8 nến |

Trong cùng một nến vừa chạm + 1 A vừa đóng quay lại thì tính ĐI TIẾP (chạm xảy ra trước lúc đóng).

### Q2 — TÍN HIỆU BOT: lệnh S07 này có nên vào?

- **Sự kiện:** mỗi lệnh gốc S07 (chân đầu của một cụm, mọi loại vào: gốc, sớm, vào lại), tại nến tín hiệu.
- **Đáp án:** R cuối cùng của chân (chi phí harsh) **> 0** hay không. Kèm giá trị R để chấm theo tiền về sau.

### Q3 — VÀO SỚM: S07 mới đủ 4/5 điều kiện

**Năm điều kiện**, như `EEA_BotsS07Near` của EA, cửa sổ nén 8 nến M30:
1. trong cửa sổ có lúc ADX ≤ 20 và |DI+ − DI−| ≤ 6;
2. ADX quay lên, chưa quá 10 điểm từ đáy;
3. DI đúng chiều và đang tách;
4. đóng vượt cả 4 EMA 21/55/100/200;
5. nến H4 đã đóng cùng phía EMA200 H4.

**Sự kiện:** nến đầu tiên mà số điều kiện theo chiều d **bằng đúng 4** (nến trước < 4).

**Đáp án:**
- (a) có lệnh gốc S07 cùng chiều vào trong **4 nến tiếp theo (2 giờ)** hay không;
- (b) nếu có: giá vào sớm tốt hơn bao nhiêu R = d × (giá vào S07 − giá đóng lúc sự kiện) / khoảng stop của lệnh S07;
- (c) R cuối của lệnh S07 đó.

### Q4 — QUẢN LÝ LỆNH: lệnh đang mở sẽ đi tiếp hay quay về?

- **Sự kiện:** mỗi nến đóng tròn giờ (hh:30 đóng → hh+1:00) trong lúc một chân S07 đang mở.
- **Đáp án:** từ giá đóng lúc đó (p0), xét đường giá tới lúc chân thoát:

| Đáp án | Điều kiện |
|---|---|
| **ĐI TIẾP** | chạm p0 + d × 1R trước khi chạm giá vào |
| **QUAY VỀ** | chạm giá vào trước |
| **ĐÓNG TRƯỚC** | chân thoát trước khi điều nào xảy ra |

1R = khoảng stop ban đầu của chân. Nếu p0 đang lỗ (chưa qua giá vào) thì QUAY VỀ nghĩa là chạm lại giá vào theo chiều có lợi: vẫn ghi,
nhưng báo riêng.

## Gói bối cảnh (mọi câu hỏi)

Chỉ dùng nến đã đóng tới nến sự kiện:

| Nhóm | Trường |
|---|---|
| Thời gian | giờ server, thứ, phiên (Á / Âu / Mỹ / muộn), phút tới tin USD HIGH kế tiếp và từ tin trước |
| Xu hướng | chế độ D1 R1 (+1 / 0 / −1), phía SMA50 / 200 D1, phía EMA200 H4, dải EMA M30 xếp thứ tự, ADX và DI M30 |
| Biến động | ATR14 M30, ATR14 / ATR100, phân vị ATR14 trong 1 năm trước, phạm vi ngày đã chạy / ADR20, độ rộng biên Á / ATR D1 |
| Vị trí | khoảng cách (theo ATR) tới VWAP ngày, biên Á, PDH / PDL, PWH / PWL, EMA200 D1; lợi nhuận 4 nến và 16 nến gần nhất (ATR) |
| Thực thi | spread / ATR |
| Riêng Q1 | loại mức, giá đóng vượt mức bao nhiêu ATR, số lần đã chạm mức trước đó trong ngày |
| Riêng Q2 / Q3 / Q4 | các điều kiện S07, loại lệnh, R đang có (Q4), số giờ đã giữ (Q4) |

## Kiểm tra bắt buộc (bước 2a xong khi qua cả ba)

1. **Không nhìn trước**: lấy 300 sự kiện ngẫu nhiên, tính lại gói bối cảnh trên dữ liệu **bị cắt tại nến sự kiện**. Mọi trường phải trùng
   khớp.
2. **Tần suất họp**: số giờ trong ngày có ít nhất một câu hỏi Q1–Q3. Trung bình ≤ 6 giờ / ngày.
   - Nếu vượt: bỏ mức swing trước; vẫn vượt thì bỏ PDH / PDL. Ghi rõ đã bỏ gì.
   - Q4 không tính vào đây: đó là cập nhật kế hoạch cho lệnh đang mở, đi cùng lần họp đầu giờ.
3. **Đáp án không suy biến**: mỗi đáp án của Q1 và Q4 chiếm ≥ 5 % tổng số sự kiện. Nếu không thì báo cáo; chỉ được chỉnh ngưỡng bằng một
   kế hoạch mới.

## Báo cáo

- Số câu hỏi mỗi tuần theo loại.
- Phân bố đáp án theo kỳ và theo năm.
- Mỗi loại mức của Q1: tỷ lệ ĐI TIẾP / GIẢ / LƯỠNG LỰ, để đối chiếu với B2 và B6 của bộ kiến thức.
- Số giờ họp mỗi ngày.

Bước này **chỉ mô tả**: không chọn ngưỡng giao dịch, không đổi EA.

Script `research/long/g156a_questions.py`, kết quả `research/long/results/g156a/`. Không chỉnh định nghĩa sau khi chạy. Có lỗi thì sửa và
ghi rõ trong báo cáo.
