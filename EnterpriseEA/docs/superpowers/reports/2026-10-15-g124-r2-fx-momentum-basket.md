# G124 R2: rổ động lượng chậm FX — kết quả

Ngày 15/10/2026.
- Kế hoạch: `docs/superpowers/plans/2026-10-15-g124-r2-fx-momentum-basket.md` (commit `4a974de`).
- Script: `research/long/g124_fx_momentum.py`.
- Bảng: `research/long/out/g124_r2.csv`. Log: `out/g124_r2_log.txt`.

## Kết luận ngắn

**Không biến thể nào đạt.** Kỳ test 2023–10/2026 **vẫn kín**.

- **Rổ 6 cặp chính:** Sharpe chỉ khoảng 0,1–0,2 mỗi năm, sụt vốn 33–41% (ở biến động mục tiêu 10%/năm), có tới 4 năm âm liên tiếp. Không thắng đối chứng ngẫu nhiên (p 0,17–0,48).
- **Thêm cặp chéo (rổ 21 cặp)** làm kết quả **kém hơn**: Sharpe âm ở hầu hết các ô.

Động lượng chậm của FX trong 2010–2022 quá yếu để làm chiến lược.

## Kết quả (sau chi phí, chưa swap; rổ được nhân hệ số để biến động năm ở train = 10%)

| Rổ | Tín hiệu | Sharpe train | %/năm train | Sharpe validate | %/năm validate | +1 pip (tra / val) | Cận dưới 90% | Sụt vốn | Năm âm liên tiếp | Ngẫu nhiên (val), p | Đạt |
|---|---|---|---|---|---|---|---|---|---|---|---|
| U6 | L60 | +0,20 | +2,0 | −0,01 | −0,1 | +0,19 / −0,03 | −0,23 | 36% | 3 | −0,02, p 0,49 | không |
| U6 | L120 | +0,19 | +1,9 | +0,12 | +1,4 | +0,18 / +0,11 | −0,19 | 41% | 4 | −0,05, p 0,34 | không |
| U6 | L250 | −0,02 | −0,2 | +0,49 | +6,3 | −0,03 / +0,49 | −0,24 | 36% | 4 | +0,02, p 0,17 | không |
| U6 | VOTE | +0,18 | +1,8 | +0,23 | +3,0 | +0,17 / +0,22 | −0,17 | 33% | 4 | −0,08, p 0,30 | không |
| U21 | L60 | +0,02 | +0,2 | −0,48 | −5,1 | | −0,50 | 42% | 3 | p 0,83 | không |
| U21 | L120 | −0,26 | −2,6 | −0,25 | −2,7 | | −0,59 | 52% | 5 | p 0,66 | không |
| U21 | L250 | −0,04 | −0,4 | −0,17 | −1,9 | | −0,42 | 28% | 2 | p 0,55 | không |
| U21 | VOTE | −0,04 | −0,4 | −0,33 | −3,9 | | −0,46 | 42% | 6 | p 0,69 | không |

Chi phí giao dịch chỉ khoảng 0,1–0,4%/năm, nên chi phí không phải lý do. Bản thân tín hiệu yếu.

**Lợi nhuận theo năm, U6 VOTE (%, ở biến động 10%):**

| 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | −5 | −10 | +2 | +23 | +15 | −4 | −5 | 0 | −14 | +6 | −1 | +21 |

## Đọc kết quả

1. **Lãi chỉ đến trong vài năm FX có xu hướng mạnh:** 2014–2015 (USD tăng mạnh) và 2022 (Fed tăng lãi suất). Các năm còn lại âm hoặc ≈ 0.
   - Sharpe khoảng 0,2 với sụt vốn 33–41% thì không dùng được.
   - Kết quả khớp với FX02: động lượng FX phụ thuộc chế độ thị trường.
2. **Cặp chéo kéo kết quả xuống:**
   - Các cặp chéo giữa EUR, GBP, AUD, NZD, CAD, JPY chủ yếu đi ngang, đảo chiều nhiều.
   - Thêm chúng làm loãng phần động lượng USD vốn là nguồn lãi chính.
3. **So với R1:**
   - Ô "hộp 24, TP 3R, theo chiều 120 ngày" của R1 cho +0,13 / +0,17R/lệnh, tốt hơn rõ so với giữ liên tục theo động lượng.
   - Tức là chiều động lượng chỉ hữu ích khi **kết hợp với điểm vào có cấu trúc**: vào ở chỗ bung ra, stop ở cạnh hộp. Nó không phải nguồn lãi đứng riêng.

## Tổng kết G124 đến giờ

| Hướng | Kết quả |
|---|---|
| R1: co hẹp → bung ra + lọc "đi thẳng" | Không đạt. Lọc ER không giúp. |
| R2: rổ động lượng chậm | Không đạt. Sharpe khoảng 0,2, sụt vốn lớn. |
| Ứng viên còn lại | Ô đối chứng R1 "hộp 24, TP 3R, chiều 120 ngày" (+0,13 / +0,17R/lệnh, p 0,18 ở validate). Ô này đã được chọn sau khi thấy train và validate. |

Kỳ test 2023–2026 vẫn sạch với cả R1 và R2.
