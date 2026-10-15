# G74: Bồi lệnh S07 khi giá hồi về EMA / vùng — kế hoạch đăng ký trước (10/10/2026)

## Vì sao

Bồi lệnh hiện tại (G70 phương án B, đã vào EA thành S07A) lấy **tín hiệu S07 ở khung khác** (M15/H1/H4) khi lệnh gốc M30 đang lời: tối đa 2 lệnh bồi, 3 lệnh mở, cách nhau ≥ 1 giờ, cùng rủi ro 1,5%, không BE. Lệnh bồi kiểu này vào lúc giá **bung tiếp** nên thường mua đuổi, SL xa (đáy vùng nén mới).

Người dùng muốn đánh giá các **vùng** và khả năng giá **hồi về các EMA**, kết hợp chỉ báo, để bồi ở giá tốt hơn. Giả thuyết: khi lệnh gốc đã chạy, các lần giá hồi về EMA21/EMA55 hoặc về mép trên vùng nén cũ (kháng cự cũ thành hỗ trợ) rồi bật lại là điểm bồi có SL gần và R tốt hơn.

## Phần 1 — đánh giá vùng (mô tả, không dùng để chọn)

Với mọi lệnh gốc S07 (sổ mua M30, sổ bán H1), trong lúc lệnh còn mở, ghi lại:
- giá có hồi về EMA21, EMA55, EMA100 của khung lệnh gốc không (nến chạm EMA ± 0,1 ATR) và hồi về mép vùng nén (± 0,3 ATR);
- lần hồi đó đến sau bao nhiêu nến, khi lệnh gốc đã lời bao nhiêu R;
- sau lần chạm đầu tiên, giá còn đi tiếp bao xa theo chiều lệnh (MFE tính theo ATR) trước khi lệnh gốc thoát.

## Phần 2 — cách bồi (thử từng cách, so với bản hiện tại)

Chung cho mọi cách:
- Chỉ bồi khi lệnh gốc còn mở và **đang lời** ở nến tín hiệu bồi.
- Tối đa 2 lệnh bồi; tối đa 3 lệnh mở cùng lúc trên toàn sổ; các lệnh cách nhau ≥ 1 giờ.
- Mỗi lệnh rủi ro 1,5%, không BE.
- Lệnh bồi vào ở giá mở nến kế tiếp.
- SL = đáy (đỉnh) thấp nhất từ lần chạm tới nến tín hiệu ∓ 0,1 ATR, giữ trong 1–4 ATR như S07.
- Mỗi lệnh bồi thoát theo luật E2X **trên khung của nó** (đóng ngược EMA55, chuyển EMA100 khi đã chạy ≥ 3R), TP 8R, giữ tối đa như S07 ở khung đó.

| Mã | Vùng chạm (lệnh mua; bán đối xứng) | Nến kích hoạt |
|---|---|---|
| A0 | không bồi | — |
| A1 | **bản hiện tại**: tín hiệu S07 ở M15/H1/H4 (G70 B) | — |
| P1 | đáy nến ≤ EMA21 + 0,1 ATR và giá đóng ≥ EMA55 (hồi nông), khung lệnh gốc | đóng cửa > đỉnh nến trước và > EMA21 |
| P2 | đáy nến ≤ EMA55 + 0,1 ATR và giá đóng ≥ EMA100 (hồi sâu), khung lệnh gốc | đóng cửa > đỉnh nến trước và > EMA55 |
| P3 | đáy nến ≤ mép trên vùng nén + 0,3 ATR và giá đóng ≥ mép − 0,3 ATR (kháng cự cũ thành hỗ trợ) | đóng cửa > đỉnh nến trước và > mép vùng |
| P4 | như P1 nhưng trên **M15** (khung nhỏ hơn lệnh gốc M30); lệnh bồi thoát theo M15 | như P1 trên M15 |

Mỗi cách P chạy hai bản xác nhận chỉ báo:
- **C0:** không thêm.
- **C1:** ở nến kích hoạt, +DI > −DI (−DI > +DI khi bán) và ADX ≥ 20.

Tổng cộng 8 bản P so với A1. Một lần chạm chỉ cho một lệnh bồi; sau khi kích hoạt phải có lần chạm mới.

## Kỳ và dữ liệu

- XAUUSD, dữ liệu MT5. Kỳ như G68–G70: 09/2018–07/2021 (pre), train 20/07/2021–2023, validate 2024–06/2025, test 07/2025–06/2026; 07/2026–nay chỉ báo cáo.
- P4 cần M15 nên chỉ có từ 07/2021, không có kỳ pre.
- Chi phí khắt khe G68 cho mọi lệnh (gốc và bồi).

## Chọn và tiêu chí (chốt trước)

Đơn vị: **tổng R mỗi lệnh gốc** (gồm lệnh bồi), chi phí khắt khe.

1. Ứng viên: các bản P có tổng R/lệnh gốc **cao hơn A1 ở cả train và validate**.
2. Chọn ứng viên có tổng R train + validate cao nhất.
3. Bản được chọn **thay A1** khi đạt cả bốn điều:
   - tổng R/lệnh gốc ≥ A1 ở test và ở pre (P4 chỉ xét test);
   - riêng các lệnh bồi có R/lệnh > 0 ở train, validate và test;
   - DD p90 (1 năm, 1,5%/lệnh, lãi kép) ≤ A1 + 2 điểm %;
   - lệnh bồi thắng bồi ngẫu nhiên p < 0,05/8. Đối chứng ngẫu nhiên: cùng số lệnh bồi mỗi kỳ, vào ở một nến ngẫu nhiên trong một lệnh gốc đang lời cùng kỳ, cùng SL tính theo ATR, cùng cách thoát, 200 lần.

Quyết định cho EA dựa trên **sổ mua**. Sổ bán (lệnh gốc H1, đang SHADOW) chạy cùng các cách để báo cáo, không dùng để chọn.

Không bản nào đạt → giữ S07A như hiện tại, báo cáo trung thực.

## Đầu ra

`research/long/g74_pullback_adds.py`, báo cáo `reports/2026-10-10-g74-pullback-adds.md`.
