# G99: chuỗi bối cảnh nào làm tăng tỉ lệ cú bán vàng lớn? (H1 từ 2018)

Ngày 11/10/2026. Ý người dùng (chart 03/03 và 12/03/2026): không khắt khe ở EMA, tìm chuỗi bối cảnh đủ tin cậy cho lệnh bán, chưa xét rủi ro, ưu tiên tăng tỉ lệ bắt được cú giảm lớn.

Script: `research/long/g99_sell_context.py`. Chỉ dùng dữ liệu MT5.

## Cách đo

**Kỳ:**
- Train: 03/2018–2021.
- Validate: 2022–06/2025 (có đợt giảm 2022 và đợt tăng 2024–25).
- Test: 07/2025–06/2026, **vẫn kín**. Hai ví dụ của người dùng nằm trong kỳ này và chỉ dùng để minh họa.

**Nhãn kết quả (tính tại giá đóng nến H1):**
- **BIG6:** giá rơi ≥ 6 ATR H1 trước khi bật lên 2 ATR, trong 120 nến.
- **BIG10:** tương tự với 10 ATR.
- Mỗi cụm 24 nến chỉ tính một lần.

**Nền chung:** "bán lỏng" = giá đóng dưới EMA21 H1 và DI− > DI+.

| Kỳ | Số lần | P(BIG6) | P(BIG10) |
|---|---|---|---|
| Train | 685 | 21,8% | 12,0% |
| Validate | 602 | 23,9% | 9,8% |

**18 điều kiện bối cảnh:**

| Nhóm | Điều kiện |
|---|---|
| Cấu trúc | F1 đỉnh gần đây; F2 đỉnh thấp hơn; F12 phá đỉnh 20 ngày thất bại; F14 nến D1 từ chối |
| Đà | F3 giá giãn xa EMA50 D1; F4 EMA21 vừa cắt EMA55; F5 dưới EMA100; F6 có nén ADX; F7 DI− đang mạnh; F8 thủng đáy ngày trước; F9 nến đẩy mạnh; F10 volume lớn; F11 phiên London/NY; F13 H4 dưới EMA55 |
| USD (EURUSD + USDJPY) | F15 USD tăng 24 giờ; F16 USD có xu hướng tăng; F17 vàng tăng trong khi USD cũng tăng; F18 USD tăng mạnh |

Tất cả chuỗi 1–3 điều kiện đều được thử.

**Đối chứng:** dời các điều kiện theo thời gian (giữ nguyên tần suất, phá liên hệ với kết quả). Mục đích là xem độ nâng tỉ lệ cao nhất có thể xuất hiện **do may mắn** khi thử nhiều chuỗi.

## Kết quả

1. **Từng điều kiện riêng lẻ** đều nâng tỉ lệ BIG6 trong khoảng 0,88–1,16 lần, tức gần như không đổi.
2. **Chuỗi 2–3 điều kiện:** 845 chuỗi có ≥ 25 lần ở cả hai kỳ. Không chuỗi nào nâng tỉ lệ ≥ 1,5 lần ở cả hai kỳ.

   | Chuỗi tốt nhất | Nâng BIG6 (train / validate) | Nâng BIG10 (train / validate) |
   |---|---|---|
   | F11 + F12 + F17 (phiên London/NY + phá đỉnh 20 ngày thất bại + vàng đã tăng ngược USD) | 1,36 / 1,45 | 1,71 / 1,57 |

   Chuỗi này đưa P(BIG6) lên 30–35%. Nhưng các điều kiện bị dời ngẫu nhiên cũng đạt mức tốt nhất khoảng 1,25 (bách phân vị 90: 1,48), nên **chưa tách được khỏi may mắn**.
3. **Điểm chung của 2 ví dụ** (F1 đỉnh gần đây, F2 đỉnh thấp hơn, F16 USD có xu hướng tăng, F17 vàng tăng ngược USD) khi đo trên dữ liệu:

   | Chuỗi | Nâng BIG6 (train / validate) | Nâng BIG10 (train / validate) | p (dời ngẫu nhiên điều kiện USD) |
   |---|---|---|---|
   | F1 + F2 + F16 + F17 | 0,92 / 1,31 | 1,22 / 2,00 | 0,52 |
   | F16 + F17 | 1,01 / 1,19 | 1,12 / 1,53 | 0,20 |
   | F1 + F16 + F17 | 1,05 / 1,11 | 1,27 / 1,42 | 0,14 |

## Kết luận

- Chủ đề lặp lại nhiều nhất ở các chuỗi đứng đầu: **vàng đã tăng trong khi USD cũng tăng (lệch nhau), rồi phá đỉnh thất bại hoặc tạo đỉnh thấp hơn**. Nó làm tăng khả năng có **cú giảm rất lớn (≥ 10 ATR)** khoảng 1,3–1,7 lần.
- Mức nâng này **chưa vượt được ngưỡng may mắn** trên 7 năm dữ liệu H1, vì số cú bán lớn quá ít (vài chục lần mỗi kỳ).
- Các điều kiện giá/EMA/DMI H1 đơn thuần không phân biệt được cú bán lớn với nhịp hồi thông thường.
- Không đưa vào EA. Nếu tiếp tục, bước đúng là đăng ký trước chuỗi "lệch USD + đỉnh thất bại", rồi xác nhận một lần trên kỳ test kín.
