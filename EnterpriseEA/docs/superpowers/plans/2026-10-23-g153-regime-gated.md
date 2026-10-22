# G153: chấm lại các ứng viên theo chế độ thị trường (chỉ đánh khi xu hướng D1 cùng chiều) — kế hoạch đăng ký trước (23/10/2026)

## Vì sao

Người dùng (23/10): chuẩn cũ "dương ở mọi giai đoạn, cả hai chiều" quá chặt. Chiến lược có lãi ngoài đời thường chỉ thắng trong một chế độ
thị trường; S07 cũng gần hòa 2018–2021 rồi lãi lớn 2022–2026. Hướng mới:
- chấp nhận setup lãi trong chế độ hợp với nó;
- yêu cầu có quy tắc **nhận ra chế độ trước khi vào** và chỉ đánh khi hợp;
- yêu cầu không lỗ nặng khi tắt.

**Giới hạn phải nói rõ:** các ứng viên dưới đây đã được nhìn kết quả 2018–2026 ở G139 / G143 / G149. Gắn bộ lọc chế độ lúc này là quyết định sau
khi nhìn. Vì vậy:
- G153 có thêm **phép chuyển sang BTC**, thị trường chưa từng dùng cho các ứng viên này;
- ô đạt chỉ được đề xuất **SHADOW forward**, không LIVE.

## Bộ nhận chế độ (cố định, một bộ duy nhất)

Trạng thái D1 của ngày đã đóng trước lúc vào lệnh, theo luật R1 của XauRegime (G96):
- **+1 (xu hướng tăng)** khi close D1 > EMA50 D1 và EMA50 hôm nay > EMA50 10 ngày trước;
- **−1 (xu hướng giảm)** khi ngược lại cả hai;
- **0** cho các trường hợp còn lại.

Lệnh **cùng chế độ** = trạng thái bằng chiều lệnh. Bộ lọc G153 = chỉ giữ lệnh cùng chế độ.

## Ứng viên (luật đóng băng như lần thử trước, không chỉnh)

| Mã | Ứng viên | Nguồn |
|---|---|---|
| A1-M30, A1-H1 | trend pullback 5 lớp | G139 A1 |
| C-M30, C-H1 | Bollinger squeeze breakout theo D1 SMA | G139 C |
| K3 | limit chờ hồi trong nhịp mạnh (f 0,382) | G149 K3 |
| W1 | phá đỉnh / đáy tuần trước, không TP | G149 W1 |
| NY | động lượng giờ đầu phiên New York (M15) | G143 |

Tham chiếu (không quyết định): sổ S07 M30 chia theo cùng bộ nhận chế độ.

## Kỳ

05/2018–2021, 2022–2023, 01/2024–06/2026 (vàng). BTC: toàn bộ dữ liệu có (`data/m30v`, `data/h1v` BTCUSD).

## Đạt khi (từng ô; 7 ô nên p ≤ 0,007)

1. Vàng, chỉ lệnh cùng chế độ: R/lệnh > 0 ở cả 3 kỳ, ≥ 20 lệnh mỗi kỳ (W1: ≥ 10).
2. Bộ lọc có ích: R/lệnh cùng chế độ ≥ R/lệnh không lọc ở ≥ 2 / 3 kỳ.
3. Hai chiều: lệnh mua cùng chế độ (gộp 3 kỳ) > 0; lệnh bán cùng chế độ ≥ −0,05R nếu có ≥ 15 lệnh.
4. Bền: chi phí × 1,5 > 0, bỏ 5 lệnh lớn nhất > 0 (gộp 3 kỳ).
5. Thắng đối chứng: lệnh ngẫu nhiên **cũng trong chế độ cùng chiều**, cùng kỳ, chiều, giờ server, khoảng SL / TP theo ATR, số nến giữ (200 lần);
   p ≤ 0,007. Phép này tách phần "ăn theo xu hướng" khỏi phần setup thật sự thêm vào.
6. **BTC (mới)**: cùng luật, cùng bộ nhận chế độ trên BTC D1; R/lệnh cùng chế độ (gộp toàn kỳ) > 0. NY không áp cho BTC.

Báo thêm: R theo chế độ (cùng / trung tính / ngược), tỷ lệ thời gian mỗi chế độ theo năm, kết quả từng năm.

## Nếu đạt

Đề xuất chạy SHADOW trong bots host, kèm cổng chế độ, forward ≥ 30 lệnh trước khi bàn LIVE. Người dùng đồng ý mới làm.

Script `research/long/g153_regime_gated.py`. Không chỉnh luật sau khi chạy.
