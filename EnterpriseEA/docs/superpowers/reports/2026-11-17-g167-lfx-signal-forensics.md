# G167: phân tích tín hiệu nhóm "LFX _ĐỔI TÍN HIỆU" — entry, SL / TP, thời gian, đa khung — báo cáo mô tả (17/11/2026)

**Nguồn:** ảnh chụp kênh Telegram người dùng gửi (`Desktop\2026-11-17_214530.png`, 1413 × 164.055 px), 02/06 → 10/11/2026.

**Quy trình:**
1. OCR (`rapidocr`).
2. Tách tín hiệu (`research/long/g167_lfx/extract.py`).
3. Mô phỏng từng tín hiệu trên giá MT5 broker (`evaluate.py`): M1 từ 06/08, M5 trước đó.
4. Phân tích (`analyze.py`).

Dữ liệu tín hiệu trích ra chỉ nằm trong `research/long/results/g167/` (không đưa lên git).

**Đây là phân tích mô tả, không phải kiểm định đăng ký trước.** Mẫu 5 tháng, một chế độ thị trường. Mọi con số dưới đây là R **trước chi phí**. Chi phí
ước tính khoảng 0,03 R / lệnh với kèo tay và 0,04 R với bot.

## 1. Hai loại tín hiệu

| Loại | Thời gian | Số lượng mô phỏng được | Định dạng |
|---|---|---|---|
| **LFX BOT** | 02/06 → 17/07 | 85 (XAU, XAG, USOUSD) | `XAUUSD 5\|SELL`, Entry, SL, TP1, TP2, **Score/100**. Đến 12/06 có nhãn DUYỆT / TỪ CHỐI |
| **Kèo tay** ("Mr Fansipan", "Mr Beer") | 03/06 → 10/11 | 178 (vàng) | `SELL GOLD NOW 4376-80`, 3 TP, SL, "Quản Trị Vốn"; có dạng viết tắt `Sell 52 SL 68 TP 35-20-08` |

**Kiểm căn giờ:**
- giờ trên Telegram là giờ Việt Nam (UTC+7);
- giờ server broker = Telegram − 4 giờ trong mùa DST Mỹ, − 5 giờ từ 01/11;
- entry của bot lệch giá MT5 cùng phút với trung vị 0,16 %.

## 2. Kết quả mô phỏng

Quy ước:
- lệnh vào đúng lúc tin nhắn được gửi: bot ở giá Entry, kèo tay ở giá thị trường;
- cùng nến chạm cả SL lẫn TP thì tính SL trước (bi quan).

| Nhóm | n | TP1 trước SL | TP1 / TP2 / TP3 (R, trung vị) | R TB: chốt hết TP1 | R TB: chia đều các TP | R TB: chia đều + BE sau TP1 |
|---|---|---|---|---|---|---|
| **Kèo tay** | 178 | **46 %** | 0,89 / 1,99 / 3,06 | −0,12 | −0,07 | **+0,06** |
| Kèo tay: bán | 117 | 48 % | 0,92 / 2,0 / 3,06 | −0,09 | −0,04 | +0,09 |
| Kèo tay: mua | 61 | 43 % | 0,81 / 1,81 / 3,02 | −0,16 | −0,13 | −0,01 |
| **Bot: tất cả** | 85 | **45 %** | 1,48 / 2,43 / — | +0,18 | +0,17 | **+0,25** |
| Bot: DUYỆT | 14 | 64 % | 1,48 / 2,82 | +0,50 | +0,55 | +0,66 |
| Bot: TỪ CHỐI | 23 | 35 % | 1,5 / 2,62 | +0,08 | +0,13 | +0,19 |
| Bot: Score ≥ 70 | 8 | 75 % | | | | |

**Độ nhạy (kèo tay):**
- **55 % kèo được gửi khi giá đã ra ngoài vùng nêu trong kèo.**
- Nếu chỉ vào ở mép vùng (như lệnh limit, chờ tối đa 24 giờ): 181 lệnh khớp, TP1 trước SL 41 %, R TB −0,14 / −0,14 / −0,03. **Tệ hơn vào giá thị trường.**

**Theo tháng (kèo tay, R TB chia đều + BE):**

| Tháng | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|
| Số kèo | 12 | 16 | 33 | 61 | 40 | 16 |
| TP1 trước SL | 50 % | 56 % | 61 % | 43 % | 38 % | 38 % |
| R TB | +0,18 | +0,23 | **+0,51** | −0,09 | −0,05 | −0,38 |

Kết quả tốt dồn vào tháng 8; từ tháng 9 âm.

Bot chỉ có 6–7 tuần: tháng 6 +0,17 R (67 lệnh), tháng 7 +0,54 R (18 lệnh).

## 3. Cách đặt SL / TP

| | Kèo tay | Bot |
|---|---|---|
| SL (giá vàng) | TB 18,6 USD | TB 6,2 USD |
| SL / ATR M5 · M15 · H1 | 3,7 · 2,1 · **1,0** | **1,85** · 1,1 · 0,56 |
| TP1 | **~0,9 R**: gần, dễ chạm | ~1,5 R |
| TP2 | ~2 R | ~2,4–2,8 R |
| TP3 | ~3 R | — |
| Thời gian tới TP1 / SL (trung vị) | ~94 / 90 phút | 15 / 25 phút |

**Đọc ra:**
- **Kèo tay:** SL ≈ 1 ATR H1, TP chia nấc ~1 R / 2 R / 3 R. TP1 < 1 R nên **chỉ chốt TP1 là âm kỳ vọng** nếu tỷ lệ thắng < 53 %. Chỉ khi chia nhiều TP và
  **dời BE sau TP1** thì mới hòa hoặc dương nhẹ.
- **Bot:** SL ≈ 1,85 ATR M5 (khung lướt 5–10 phút), TP1 ≈ 1,5 R, TP2 ≈ 2,5 R, ngã ngũ trong vòng nửa giờ.

## 4. Thời gian ra lệnh (kèo tay, giờ Việt Nam)

- Tập trung **09:00–20:00**, tức phiên Âu và đầu phiên Mỹ. Đỉnh lúc 12:00 và 18:00–19:00.
- Rất ít kèo sau 22:00.
- Thứ Ba / Thứ Năm nhiều nhất, Thứ Sáu ít nhất, không có cuối tuần.

## 5. Bối cảnh đa khung

Mỗi ô ghi: % tín hiệu có đặc điểm / % nến ngẫu nhiên → tỷ lệ.

**Kèo tay ≈ "theo xu hướng khung lớn, vào ở nhịp hồi khung nhỏ":**
- giá cùng phía EMA50 trên H1 / H4 / D1: 60–67 % / 50–54 % → × 1,2;
- EMA50 H1 / H4 dốc cùng chiều: × 1,2;
- D1 cùng chế độ: × 1,2;
- khung nhỏ đang hồi ngược chiều lệnh: EMA50 M5 dốc ngược × 0,83; RSI M15 ở vùng 60 / 40 ngược chiều × 1,35;
- **tránh RSI H4 cực trị:** × 0,41.

**Bot ≈ "bắt đảo chiều ở cực trị (fade)":**
- RSI quá mua / quá bán ngược chiều lệnh trên M15 / H1 / H4: × 2,2–2,8;
- chế độ D1 ngược chiều lệnh: 62 % so với 40 %, × 1,55;
- giá ở 1/3 biên 12 giờ phía ngược (bán ở đỉnh / mua ở đáy): × 1,5;
- nến H1 vừa đóng ngược chiều lệnh: × 1,36.

Không đặc điểm nào xuất hiện ở gần 100 % tín hiệu. Đây là xu hướng của bộ tín hiệu, không phải một luật cứng mà ta tái tạo được.

## 6. Giống phương pháp nào đã test

| Tín hiệu | Gần với | Kết quả trước đây của ta |
|---|---|---|
| Kèo tay: xu hướng H1 / H4 / D1 + vào nhịp hồi M5 / M15, SL ~1 ATR H1, TP 1 / 2 / 3 R | S07 (pullback theo trend), E4 (G158), **Z1 vùng EMA (G163)** | G163: Z1 không hơn vào ngẫu nhiên cùng chiều D1; lệnh bán âm |
| Bot: RSI cực trị ngược chiều, chống D1, ở đỉnh / đáy biên 12 h | **G130 / G131 RSI cực trị**, bắt đỉnh / đáy | G130 / G131 âm ở kỳ kiểm khi đánh ngược trend |

## 7. Kết luận

1. **Kèo tay** thắng TP1 46 %, nhưng TP1 chỉ ~0,9 R. Tổng thể **xấp xỉ hòa vốn**: +0,06 R trước phí khi chia TP + BE, âm nếu chỉ chốt TP1. Lãi dồn vào tháng 8,
   âm từ tháng 9.
2. **Bot LFX** cho +0,18–0,25 R / lệnh trước phí (~+0,14–0,21 sau phí) trong 6 tuần. Kèo DUYỆT / Score ≥ 70 tốt hơn TỪ CHỐI, nhưng chỉ 8–14 lệnh: **chưa đủ để
   tin Score**.
3. Phương pháp của cả hai đều thuộc nhóm ta đã test trên dữ liệu dài mà không thấy lợi thế bền.
4. **Muốn biết chắc**, bước tiếp theo đúng là viết luật tái tạo từ mục 3–5 và **kiểm định đăng ký trước trên 2018–2026**:
   - luật "bot-like": RSI cực trị + SL 1,85 ATR M5 + TP 1,5 / 2,5 R;
   - luật "kèo tay": trend H1 / H4 + nhịp hồi M15 + SL 1 ATR H1 + TP 1 / 2 / 3 R + BE.

   Không nên chạy theo kèo của nhóm chỉ dựa trên 5 tháng này.

**Giới hạn:**
- OCR có thể sai vài số;
- kèo viết tắt được dựng lại theo giá gần nhất;
- giờ gửi tin không phải giờ khớp lệnh thật;
- tin "đã TP" do nhóm tự báo không được dùng: mọi kết quả ở đây là tự mô phỏng.
