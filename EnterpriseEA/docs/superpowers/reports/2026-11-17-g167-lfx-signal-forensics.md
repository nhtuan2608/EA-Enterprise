# G167: phân tích tín hiệu nhóm "LFX _ĐỔI TÍN HIỆU" — entry, SL / TP, thời gian, đa khung — báo cáo mô tả (17/11/2026, bản 2)

**Nguồn:** ảnh chụp kênh Telegram người dùng gửi (`Desktop\2026-11-17_214530.png`, 1413 × 164.055 px), 02/06 → 10/11/2026.

**Quy trình:**
1. OCR (`rapidocr`).
2. Tách tín hiệu (`research/long/g167_lfx/extract.py`).
3. Mô phỏng từng tín hiệu trên giá MT5 broker (`evaluate.py`): M1 từ 06/08 (vàng / bạc / dầu) hoặc 08–09 (EUR / BTC), M5 trước đó.
4. Phân tích (`analyze.py`).

Dữ liệu tín hiệu trích ra chỉ nằm trong `research/long/results/g167/` (không đưa lên git).

**Đây là phân tích mô tả, không phải kiểm định đăng ký trước.** Mẫu 5 tháng, một chế độ thị trường. Mọi R là **trước chi phí**; chi phí ước tính ~0,03 R / lệnh
kèo tay, ~0,04 R bot.

## Bản 2: sửa sau khi kiểm độ đầy đủ

Bản đầu bỏ sót và gán sai nhiều kèo. Các lỗi đã sửa:

| Lỗi | Ảnh hưởng | Sửa |
|---|---|---|
| OCR đọc "GOLD" thành **"G0LD"** | ~30 kèo **mua** bị bỏ | chuẩn hóa g0ld → gold |
| "BUY Limit GOLD", "SELL LIMIT GOLD", đầu kèo tách 2 dòng, dạng `Entry:` ở dòng sau | kèo limit bị bỏ | nhận cả hai thứ tự, ghép dòng |
| Kèo mã khác (EURUSD ×4, BTC ×2, dầu ×2) | chưa tính | thêm dữ liệu MT5 BTCUSD, EURUSD-VIP |
| OCR **bỏ sót tiêu đề ngày** (ví dụ "June 4", "September 1"), nên kèo bị gán vào ngày trước | kèo bị mô phỏng sai ngày | thử cùng giờ ở ngày gán và 1–4 ngày sau, chọn ngày giá khớp Entry / vùng nhất. 49 kèo được dời (bot: 16); sau khi dời, Entry bot lệch giá thật 0,01–0,2 % |
| Kèo không ghi SL ("Sell 05 Anh Em") | bị loại | mô phỏng với SL 1 ATR H1, TP 0,9 / 2 / 3 R (hình mẫu chung); đánh dấu giả định (27 kèo) |

**Độ phủ cuối:**
- tách được 89 khối bot + 278 kèo tay; 362 kèo có ngày giờ;
- **343 mô phỏng được**: bot 85, kèo tay 258 (27 với SL giả định);
- 10 kèo limit không khớp trong 24 giờ;
- 9 kèo có mức giá không hợp lệ (OCR sai số hoặc giá viết tắt không dựng lại được).

Những dòng "sell / buy" còn lại không bắt là câu chat ("Sell nha ae", "Buy tìm điểm sell nào"...) hoặc bản trích dẫn / đăng lại của kèo đã có.

**Hệ quả quan trọng:** kết quả của **bot đổi rõ** so với bản 1, vì 16 kèo bot trước đây bị mô phỏng sai ngày. **Bản 2 là bản đúng.**

## 1. Hai loại tín hiệu

| Loại | Thời gian | Mô phỏng | Định dạng |
|---|---|---|---|
| **LFX BOT** | 02/06 → 17/07 | 85 (XAU 46, USOUSD 26, XAG 17 — sau khi lọc) | `XAUUSD 5\|SELL`, Entry, SL, TP1, TP2, **Score/100**; đến 12/06 có nhãn DUYỆT / TỪ CHỐI |
| **Kèo tay** (chủ yếu "Mr Fansipan") | 03/06 → 10/11 | 258 (vàng 252, EUR 4, dầu 2, BTC 2 — một số trùng lọc) | `SELL GOLD NOW 4376-80`, 3 TP, SL; dạng viết tắt `Sell 52 SL 68 TP 35-20-08`; LIMIT theo vùng |

Giờ Telegram là giờ Việt Nam (UTC+7). Giờ server broker = Telegram − 4 giờ (mùa DST Mỹ), − 5 giờ từ 01/11.

## 2. Kết quả mô phỏng

Quy ước:
- vào lúc tin nhắn được gửi: bot ở giá Entry, kèo tay ở giá thị trường; limit chờ chạm vùng tối đa 24 giờ;
- cùng nến chạm cả SL lẫn TP thì tính SL trước.

| Nhóm | n | TP1 trước SL | TP1 / TP2 / TP3 (R, trung vị) | Chốt hết TP1 | Chia đều các TP | Chia đều + BE sau TP1 |
|---|---|---|---|---|---|---|
| **Kèo tay** | 258 | **48 %** | 0,86 / 1,94 / 3,0 | −0,10 | −0,09 | **+0,04** |
| Kèo tay: bán | 162 | 49 % | 0,89 / 1,97 / 2,99 | −0,11 | −0,07 | +0,06 |
| Kèo tay: mua | 96 | 46 % | 0,81 / 1,83 / 2,99 | −0,09 | −0,10 | +0,02 |
| **Bot: tất cả** | 85 | **36 %** | 1,48 / 2,43 / — | −0,10 | −0,14 | **−0,07** |
| Bot: DUYỆT | 14 | **64 %** | 1,48 / 2,82 | +0,50 | +0,71 | +0,78 |
| Bot: TỪ CHỐI | 23 | **17 %** | 1,5 / 2,62 | −0,63 | −0,68 | −0,61 |
| Bot: không nhãn (15/06–17/07) | 46 | 37 % | 1,45 / 2,25 | −0,02 | −0,12 | −0,05 |

**Bot theo Score:**

| Score | < 60 | 60–69 | ≥ 70 |
|---|---|---|---|
| TP1 trước SL | 19 % | 33 % | 75 % |
| n | 16 | 15 | 8 |

**Theo tháng (kèo tay, chia đều + BE):**

| Tháng | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|
| Số kèo | 18 | 24 | 53 | 64 | 59 | 40 |
| TP1 trước SL | 39 % | 46 % | 53 % | 44 % | 49 % | 50 % |
| R TB | −0,13 | −0,10 | **+0,29** | −0,13 | +0,09 | +0,06 |

**Theo tháng (bot):** tháng 6 −0,08 R (67 kèo), tháng 7 −0,04 R (18 kèo).

**Độ nhạy:**
- **55 %** kèo tay được gửi khi giá **đã ra ngoài vùng** nêu trong kèo.
- Vào ở mép vùng (như limit) cho kết quả kém hơn vào ngay (bản 1: R TB −0,14 / −0,14 / −0,03).
- Nhóm 27 kèo SL giả định có TP1 trước SL 56 %. Bỏ nhóm này, kết luận không đổi.
- Kèo mã khác (8): 2 / 6 chạm TP1. Quá ít để kết luận.

## 3. Cách đặt SL / TP

| | Kèo tay | Bot |
|---|---|---|
| SL (vàng) | TB ~19,7 USD | TB ~6,2 USD |
| SL / ATR M5 · M15 · H1 | 3,7 · 2,1 · **1,0** | **1,8** · 1,1 · 0,54 |
| TP | **~0,9 R / 2 R / 3 R** (TP1 gần) | ~1,5 R / 2,4–2,8 R |
| Thời gian tới TP1 / SL (trung vị) | ~1,5 giờ | ~20–25 phút |

- **Kèo tay:** TP1 < 1 R, nên **chỉ chốt TP1 là âm kỳ vọng** với tỷ lệ thắng 48 %. Chỉ chia TP và dời BE sau TP1 mới hòa / dương nhẹ.
- **Bot:** khung lướt M5 / M10, TP1 ~1,5 R. Hòa vốn cần ~40 % chạm TP1, nhưng tổng thể chỉ đạt 36 %. Kèo **DUYỆT / Score ≥ 70** đạt 64–75 %.

## 4. Thời gian ra lệnh (kèo tay, giờ Việt Nam)

- Trải từ **08:00 đến 22:00**.
- Dày nhất **09:00–14:00** (phiên Á muộn / Âu) và **18:00–21:00** (đầu phiên Mỹ).
- Ít sau 23:00.
- Thứ Năm / thứ Ba nhiều nhất, thứ Hai ít hơn, gần như không có cuối tuần.

## 5. Bối cảnh đa khung

Mỗi ô ghi: % tín hiệu / % nến ngẫu nhiên → tỷ lệ.

**Kèo tay ≈ "theo xu hướng khung lớn, vào ở nhịp hồi khung nhỏ":**
- giá cùng phía EMA50 trên D1 / H4 / H1: 69 / 66 / 62 % so với 53 / 54 / 52 % → × 1,2–1,3;
- D1 cùng chế độ: 57 % / 45 %, × 1,28;
- EMA50 H1 / H4 dốc cùng chiều: × 1,2;
- khung nhỏ đang hồi ngược: RSI M15 ở 60 / 40 ngược chiều × 1,34, EMA50 M5 dốc ngược × 0,88;
- **tránh RSI H4 cực trị**: × 0,36–0,49;
- tránh đánh ngược chế độ D1: × 0,74.

**Bot ≈ "bắt đảo chiều ở cực trị (fade)":**
- RSI quá mua / quá bán ngược chiều lệnh trên M15 / H1 / H4: × 2,5–3,0;
- chế độ D1 ngược chiều lệnh: 62 % / 40 %, × 1,55;
- giá ở 1/3 biên 12 giờ phía ngược: × 1,56;
- nến H1 vừa đóng ngược chiều lệnh: × 1,45;
- 4 giờ trước đi ngược chiều lệnh: × 1,36.

Không đặc điểm nào xuất hiện ở gần 100 % tín hiệu. Đây là xu hướng, không phải luật cứng.

## 6. Giống phương pháp nào đã test

| Tín hiệu | Gần với | Kết quả trước đây của ta |
|---|---|---|
| Kèo tay: xu hướng H1 / H4 / D1 + vào nhịp hồi M5 / M15, SL ~1 ATR H1, TP 1 / 2 / 3 R | S07 (pullback theo trend), E4 (G158), **Z1 vùng EMA (G163)** | G163: Z1 không hơn vào ngẫu nhiên cùng chiều D1; lệnh bán âm |
| Bot: RSI cực trị ngược chiều, chống D1, ở đỉnh / đáy biên 12 h | **G130 / G131 RSI cực trị**, bắt đỉnh / đáy | G130 / G131 âm ở kỳ kiểm khi đánh ngược trend |

## 7. Kết luận

1. **Kèo tay**: TP1 trước SL 48 %, TP1 chỉ ~0,9 R.
   - Tổng thể **xấp xỉ hòa vốn**: +0,04 R trước phí khi chia TP + BE, ≈ 0 sau phí; âm nếu chỉ chốt TP1.
   - Tốt nhất tháng 8, dao động quanh 0 các tháng khác.
2. **Bot LFX**: tổng thể **âm nhẹ** (−0,07 R).
   - Nhãn **DUYỆT / Score cao phân loại rất rõ**: DUYỆT 64 % TP1, +0,78 R (n = 14); TỪ CHỐI 17 %, −0,61 R (n = 23); Score ≥ 70: 75 % (n = 8).
   - Đây là phát hiện thú vị nhất, nhưng **mẫu quá nhỏ** và bot ngừng gửi nhãn sau 12/06.
3. Phương pháp của cả hai thuộc nhóm ta đã test trên dữ liệu dài mà không thấy lợi thế bền.
4. **Bước tiếp theo nếu muốn dùng:** viết luật tái tạo và kiểm định đăng ký trước trên 2018–2026.
   - Ưu tiên luật "bot" kèm **bộ lọc chất lượng kiểu Score** (RSI cực trị + giá ở biên 12 h + nến H1 ngược). Đo xem bộ lọc đó có tách lệnh tốt / xấu như nhãn
     DUYỆT không.

**Giới hạn:**
- OCR có thể sai vài số;
- kèo viết tắt được dựng lại theo giá gần nhất;
- ngày được tự sửa khi tiêu đề ngày bị sót;
- giờ gửi tin không phải giờ khớp lệnh thật;
- tin "đã TP" do nhóm tự báo không được dùng.

## 8. Bổ sung: 7 chart setup LFX (04–17/11/2026, XAUUSD M30 OANDA)

Script `research/long/g167_lfx/charts7.py`. Giá OANDA lệch MT5 −1,6 … +3,5 USD; các mức đã quy đổi sang giá MT5 trước khi mô phỏng (M1, cùng nến chạm SL
và TP thì tính SL trước).

| Kèo | Lệnh chờ | Cách giá lúc gửi | SL (ATR H1) | Vùng trùng swing H1 cũ | Khớp | Kết quả |
|---|---|---|---|---|---|---|
| 1a sell 3965 | sell limit | 2,2 ATR H1 | 0,8 | có (3970–3976) | sau 2,8 h | **SL** sau 6 phút (−1 R) |
| 1b buy 3896 | buy limit | 2,3 | 1,2 | có (3895) | không khớp trong 72 h | — |
| 2 buy 4078–4099 | buy limit | 1,7 | 1,5 | có (4083) | sau 9,1 h | **SL** sau 10,8 h (−1 R) |
| 3 buy 4028–4036 | buy limit | 0,5 | 0,8 | có (4025–4034) | sau 1,4 h | **TP1 + TP2 + TP3** (+1,62 R chia đều) |
| 4 sell 4120–4127 | sell limit | 0,8 | 1,3 | biên range (thấy trên chart) | sau 2,5 h | **TP1 + TP2** (+1,41 R) |
| 6 sell 4067–4073 | sell limit | 1,6 | 1,3 | có (4066–4071) | không khớp | — |
| 5 sell 3924–3930 | sell limit | 1,0 | 1,2 | có (3925) | không khớp | — |
| 7 sell 3888–3896 | sell limit | 1,3 | 1,15 | có (3888–3895) | sau 11,7 h (22:42 hôm nay) | **TP1 + TP2**, TP3 còn mở (≥ +0,52 R) |

**Tổng 8 kèo:** 5 khớp. 2 SL, 3 thắng. Tổng ≈ +1,5 R (chia đều TP, chưa tính TP3 của kèo 7). Mẫu quá nhỏ để kết luận.

**Phương pháp đọc từ 7 chart:**
- **Entry:** lệnh **chờ đặt sẵn** (limit) tại **vùng hỗ trợ / kháng cự cũ**, cách giá 0,5–2,3 ATR H1. 7 / 8 vùng trùng đỉnh / đáy swing H1 trong 10 ngày; thường
  là mức vừa bị phá rồi chờ test lại (S/R flip).
- **Không chờ nến xác nhận.** Nến xác nhận M5 / M15 xuất hiện 18–65 phút sau khớp ở cả kèo thắng lẫn kèo thua, nên không phân biệt được.
- **SL:** phía sau vùng, **~1,15–1,5 ATR H1** (≈ 1,6–2 ATR M30, 18–28 USD); hai kèo SL ngắn 0,8 ATR.
- **TP:** TP1 gần (0,45–1,1 R, thường là giá lúc gửi hoặc swing gần); TP2 1,1–2,2 R; TP3 1,6–2,4 R ở vùng S/R đối diện.
- **Đa khung:**
  - **kèo sell** (1a, 4, 5, 6, 7): D1 dưới EMA50 cả 5 / 5, H4 dưới EMA50 4 / 5. Vào khi M15 / M30 đang hồi lên (RSI M15 51–69). Tức là **bán nhịp hồi vào kháng cự
    trong xu hướng giảm D1 / H4**.
  - **kèo buy** (2, 3): H4 trên EMA50, mua nhịp hồi sau một đợt tăng mạnh.
  - Kèo 1b là kèo buy trong range, ngược D1.
- **Thời gian:** gửi 09:00–12:41 giờ VN (phiên Á). Lệnh khớp trong phiên Âu / Mỹ (12:22–22:42).

**So với phương pháp đã test:**
- Gần **G160b "phục kích ở bản đồ thanh khoản"** (chưa chạy).
- Khác G163 Z2: Z2 vào khi nến chạm mức + đóng xác nhận, không đặt limit ở mức vừa bị phá.

**Đề xuất:** kiểm định đăng ký trước luật "S/R flip limit theo chiều D1" trên 2018–2026. Luật gồm: limit ở swing H1 vừa bị phá, SL 1,3 ATR H1, TP 1 R / 2 R / vùng
đối diện, hết hạn 24 h. Đối chứng là limit ở mức giả cùng khoảng cách.
