# G132: các manh mối đảo chiều intraday trên vàng — kiểm tra và so sánh

Kế hoạch: `plans/2026-10-20-g132-reversal-leads.md`. Chi phí khắt khe (spread + trượt 0,5 × spread trung vị mỗi chiều + $6/lot). R = lời/lỗ ÷ khoảng SL. Mua và bán báo cáo riêng.

## Bảng so sánh chung

| # | Manh mối | Khung | Lịch sử (đã dùng để chọn) | Kiểm tra sạch | Trạng thái |
|---|---|---|---|---|---|
| A | Nến V quay về EMA200: EMA xòe ngược chiều V + ADX < 25 + V phá ngược dốc EMA200 (G118 ứng viên A) | M30 | 211 nhóm, **+0,42U/nhóm, dương 9/9 năm** (2018–2026); vào ngẫu nhiên +0,14U | không còn kỳ kín | **mạnh nhất trên lịch sử**, cần shadow forward |
| B | Đánh ngược cú giật sau tin USD HIGH | M15 | train −0,13 đến −0,31; validate −0,03 đến +0,04 | 2026 vẫn kín (không biến thể nào qua bước chọn) | **loại**. Cú giật do tin quay về nhiều hơn cú giật thường (đối chứng −0,24 đến −0,35), nhưng chi phí sau tin ăn hết |
| C | Vàng tăng khi USD cũng tăng + phá đỉnh 20 ngày thất bại + phiên London/NY (G99), bán | H1 | train +0,32R (44), validate +0,34R (52) | **test 07/2025–06/2026: −0,55R (17)**, thua đối chứng (−0,12) | **loại**: đẹp trên lịch sử, gãy khi test. Chiều mua quá ít lệnh |
| D | Bán ở đỉnh thấp hơn tại vùng cản (G80 LH) | M30 | validate +0,28 đến +0,29R, test +0,05 đến +0,30R (ít lệnh) | không còn kỳ kín | yếu, cần forward |
| E | Limit đảo chiều khi giá test mức (G111, nhóm AFIB) | M15 | **có spread thật**: train +0,07R (219), validate +0,09R (443); ngẫu nhiên −0,05. **Spread = 0**: +0,21 / +0,22R | không còn kỳ kín | có lợi thế **trước chi phí**, nhưng mức giả cho kết quả như mức thật (lãi đến từ cơ chế khớp limit). Phụ thuộc mạnh vào spread |

## B — đánh ngược cú giật sau tin USD HIGH (M15)

Nến tin: 1683. Đối chứng: nến giật cùng giờ server ở ngày không có tin USD HIGH trong ±1 giờ.

| k ATR | Mục tiêu | Train | Validate | Mua (train · val) | Bán (train · val) | Đối chứng train · val | Chọn? |
|---|---|---|---|---|---|---|---|
| 2 | hồi 50% | 163 / -0.191 | 97 / +0.037 | 79 / -0.021 · 43 / +0.100 | 84 / -0.351 · 54 / -0.013 | 225 / -0.319 · 193 / -0.240 |  |
| 2 | 2R | 163 / -0.132 | 97 / -0.027 | 79 / +0.034 · 43 / -0.043 | 84 / -0.288 · 54 / -0.014 | 225 / -0.346 · 193 / -0.352 |  |
| 3 | hồi 50% | 97 / -0.314 | 48 / +0.040 | 44 / -0.203 · 18 / +0.117 | 53 / -0.406 · 30 / -0.006 | 59 / -0.120 · 39 / -0.250 |  |
| 3 | 2R | 97 / -0.258 | 48 / -0.028 | 44 / -0.162 · 18 / -0.192 | 53 / -0.339 · 30 / +0.071 | 59 / -0.344 · 39 / -0.256 |  |

Không biến thể nào được chọn → **2026 vẫn niêm phong** cho ý này.

## C — lệch USD + phá đỉnh/đáy 20 ngày thất bại (H1), thành lệnh (SL 2 ATR, TP 6 ATR)

| Chiều | Train 2018–21 | Validate 2022–06/2025 | **Test 07/2025–06/2026** | Cận dưới 90% test | Đối chứng nền (test) | Đạt? |
|---|---|---|---|---|---|---|
| Bán (F11+F12+F17) | 44 / +0.315 | 52 / +0.342 | 17 / -0.554 | -1.007 | 172 / -0.122 | không |
| Mua (đối xứng) | 18 / +0.078 | 9 / -0.573 | 5 / +0.535 | -0.268 | 175 / +0.352 | không |

## Kết luận

- **Hai manh mối test sạch được đều không đạt.**
  - B (đánh ngược tin): âm.
  - C (lệch USD + phá đỉnh thất bại): rất đẹp ở 2018–06/2025 nhưng âm ở kỳ test 07/2025–06/2026. Đây là ví dụ điển hình của chuỗi điều kiện chọn sau khi xem dữ liệu.
- **Ba manh mối còn lại không còn kỳ kín**, chỉ xác nhận được bằng **shadow forward** trên dữ liệu mới:
  - **A** (nến V M30) mạnh nhất: dương 9/9 năm, hơn ngẫu nhiên khoảng +0,28U.
  - **E** (limit tại mức M15) dương nhẹ có spread, phụ thuộc chi phí.
  - **D** (đỉnh thấp hơn) yếu.
- **Đảo chiều intraday có lợi thế thật** chỉ thấy ở kiểu **nến V quay về EMA200 khi thị trường nén** (VHedge G119 trên M5; A trên M30). Các kiểu khác (quá mua/bán, quét đỉnh/đáy, tin tức, ADR, cạn đà) đều không qua được kiểm tra sạch.
