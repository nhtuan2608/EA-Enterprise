# G156c: thư viện tình huống lặp lại, đa khung và key level — kế hoạch đăng ký trước (24/10/2026)

## Vì sao

G156a2 cho thấy đọc bối cảnh giá **rời rạc** không đoán được phá giả hay đi tiếp: khoảng 51 %, AUC 0,50. Người dùng hỏi tiếp (24/10):
hội đồng có thể **nhận diện các tình huống lặp lại có tên** không, và các tình huống đó có báo trước điều gì không. Các tình huống:
- trước tin / sau tin / tin đã ra nhưng chưa mở phiên Mỹ;
- quét thanh khoản rồi rút đúng hướng;
- volume ít mà giá vẫn chạy;
- "logic sai" (vàng và USD cùng chiều, phản ứng ngược kỳ vọng tin);
- **đồng thuận đa khung**;
- **key level** (hợp lưu, đã test nhiều lần, phá rồi retest giữ được).

G156c định nghĩa 12 tình huống bằng luật và đo xem mỗi tình huống có **giá trị dự báo** không.

## Cách đo chung

**Kết quả**: từ giá đóng nến sự kiện, ± 1 ATR14 M30 (của nến sự kiện), trong 8 nến (4 giờ). Đáp án:
- **THEO**: chạm + d × 1 ATR trước;
- **NGƯỢC**: chạm − d × 1 ATR trước.

Bỏ lưỡng lự và trường hợp một nến chạm cả hai. Chỉ số = **P(THEO)** trong các lần đã phân định. d là chiều của tình huống (định nghĩa
bên dưới).

**Đối chứng riêng cho từng tình huống**: cùng cách đo, cùng kỳ, trên các nến giống tình huống ở mọi điểm **trừ** yếu tố đang kiểm.

**Thống kê:**
- Chênh lệch = P(THEO | tình huống) − P(THEO | đối chứng), gộp 05/2018 → 06/2026.
- Khoảng tin cậy **99,6 %** (Bonferroni 0,05 / 12) bằng bootstrap khối tuần, 2.000 lần.

**Giờ:** giờ server; giờ New York = giờ server − 7 (đã kiểm ở MKT02). Tin 8:30 New York = 15:30 server; mở cửa 9:30 New York = 16:30 server.

**Chống trùng:** mỗi tình huống cách nhau ít nhất 4 nến.

## 12 tình huống

| Mã | Tình huống | Sự kiện (nến đóng) và chiều d | Đối chứng |
|---|---|---|---|
| T1 | **Trước tin** | nến đóng 30–60 phút trước tin USD HIGH; d = dấu lợi nhuận 4 nến (đà trước tin) | nến cùng giờ server, ngày không có tin USD HIGH trong ± 3 giờ; d như trên |
| T2 | **Nến tin** | nến M30 chứa giờ tin; d = chiều nến đó | nến cùng giờ, ngày không tin; d = chiều nến |
| T3 | **Tin đã ra, chưa mở phiên Mỹ** | ngày có tin USD HIGH lúc 15:30 server; sự kiện = nến đóng 16:30 (mở cửa New York); d = dấu (giá đóng − giá mở nến tin) | cùng nến 16:00–16:30, ngày không có tin 15:30; d = dấu (đóng − mở nến 15:30) |
| T4 | **Quét rồi rút cùng chiều D1** | đáy nến < đáy ngày trước hoặc đáy biên Á, giá đóng quay lại trên mức, chế độ D1 = +1 → d = +1 (đối xứng với đỉnh khi D1 = −1) | mọi nến cùng kỳ, d = chế độ D1 ≠ 0 (đo phần trôi theo xu hướng) |
| T5 | **Quét rồi rút ngược D1** | như T4 nhưng chế độ D1 ngược chiều rút | mọi nến, d = ngược chế độ D1 |
| T6 | **Giá chạy mà volume giảm** | \|lợi nhuận 8 nến\| ≥ 1,5 ATR theo chiều s; tick volume TB 4 nến gần nhất < 0,8 × TB 4 nến trước đó; d = s | cùng điều kiện giá, tick volume 4 nến gần ≥ 4 nến trước; d = s |
| T7 | **Vàng và USD cùng chiều** (lệch logic) | lợi nhuận 8 nến vàng ≥ 1 ATR theo chiều s, DXY cùng dấu ≥ 1 ATR DXY; d = s. **Chỉ từ 09/2021** | cùng điều kiện vàng, DXY ngược dấu ≥ 0,5 ATR DXY; d = s |
| T8 | **Phản ứng ngược kỳ vọng tin** | tin USD HIGH có thực tế và dự báo (cách tính lệch của G129); nến tin \|đóng − mở\| ≥ 0,5 ATR, đi **ngược** chiều mà tin gợi ý cho vàng; d = chiều nến | nến tin cùng độ lớn, đi **cùng** chiều tin gợi ý; d = chiều nến |
| T9 | **Đồng thuận đa khung** khi phá mức | sự kiện phá mức G156a; 4 khung cùng chiều phá: M30 (giá so với EMA50 M30), khung giờ (giá so với EMA100 M30), H4 (giá so với EMA200 H4), D1 (chế độ R1) | các sự kiện phá mức không đủ 4 khung cùng chiều |
| T10 | **Key level hợp lưu** | sự kiện phá mức có ≥ 1 mức **loại khác** (biên Á, ngày trước, tuần trước, swing còn hiệu lực) cách ≤ 0,5 ATR | các sự kiện phá mức không có mức nào gần |
| T11 | **Key level đã test nhiều lần** | sự kiện phá mức có ≥ 3 nến trước đó chạm tới cách mức ≤ 0,25 ATR mà không đóng vượt, trong thời gian hiệu lực của mức | các sự kiện phá mức có ≤ 1 lần chạm |
| T12 | **Phá + retest giữ** (xác nhận khung nhỏ) | sau khi phá đỉnh / đáy ngày hoặc tuần trước, trong 6 nến có nến lùi về cách mức ≤ 0,25 ATR mà vẫn đóng phía ngoài; sự kiện = nến đó; d = chiều phá | sự kiện phá đỉnh / đáy ngày, tuần trước tại chính nến phá |

## Phân loại kết quả

**"Có giá trị dự báo"** khi cùng đúng:
1. ≥ 100 lần đã phân định gộp, và ≥ 30 mỗi kỳ (T7: hai kỳ cuối);
2. khoảng tin cậy 99,6 % của chênh lệch không chứa 0;
3. chênh lệch cùng dấu ở ≥ 2 / 3 kỳ (05/2018–2021, 2022–2023, 2024–06/2026; T7: cả 2022–2023 và 2024–06/2026).

Không đạt thì: **"chỉ cảnh báo / giải thích"**. Hội đồng vẫn có thể gọi tên tình huống để cảnh báo rủi ro hoặc giải thích, nhưng không
dùng nó để đoán hướng.

Báo thêm (không quyết định):
- R trung bình của lệnh gốc S07 có nến tín hiệu trùng tình huống (trong 2 nến trước);
- kỳ sau 07/2026;
- phân bố theo năm.

Bước này không đổi EA và không tạo luật giao dịch. Kết quả chọn ra những tình huống hội đồng cần nhận diện (bước 3a) và cho mỗi tình
huống con số nền để dẫn.

Script `research/long/g156c_situations.py` (dùng lại hàm của `g156a_questions.py` và tin của `g129_gold_news.py`), kết quả
`research/long/results/g156c/`. Không chỉnh định nghĩa sau khi chạy.
