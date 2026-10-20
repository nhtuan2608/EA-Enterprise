# G132: kiểm tra và so sánh các manh mối đảo chiều intraday trên vàng — kế hoạch đăng ký trước (20/10/2026)

## Vì sao

Rà lại các nghiên cứu cũ để tìm cách đánh đảo chiều scalp / intraday, cũng như swing nếu giữ được. Có 5 manh mối.

Người dùng muốn **test tất cả và so sánh một lần**. Kế hoạch này ghi rõ manh mối nào còn test sạch được và manh mối nào chỉ còn xác nhận bằng forward.

| # | Manh mối | Nguồn | Còn kỳ kín? |
|---|---|---|---|
| A | Nến V M30: EMA xòe ngược chiều V + ADX < 25 + V phá ngược dốc EMA200 | G118 ứng viên A | **không** (G118 đã tính cả 2026) → so sánh số lịch sử, cần shadow forward |
| B | **Đánh ngược cú giật sau tin USD HIGH** | G95 F7 (mô tả, 37 mẫu) | **có**: 2026 chưa dùng cho ý này |
| C | **Lệch USD + phá đỉnh 20 ngày thất bại + phiên London/NY** (F11 + F12 + F17), bán; đối xứng cho mua | G99 | **có**: 07/2025–06/2026 vẫn kín |
| D | Bán ở đỉnh thấp hơn tại vùng cản, M30 | G80 | **không** (test đã xem) → so sánh số lịch sử |
| E | Limit đảo chiều khi giá test một mức | G111 / G113 | chỉ phụ thuộc chi phí → tính spread hòa vốn từ số sẵn có (spread thật và spread 0) |

**Chi phí khắt khe** cho mọi phần chạy mới: spread nến vào/ra + trượt 0,5 × spread trung vị mỗi chiều + $6/lot. Báo cáo **mua và bán riêng**.

## B — đánh ngược cú giật sau tin (M15)

- **Tin**: mọi tin USD mức HIGH trong lịch MT5 (giờ server, như G129). Không cần số dự báo.
- **Nến tin** = nến M15 chứa giờ ra tin.
- **Cú giật** = |đóng − mở| của nến tin ≥ k × ATR14 M15 (ATR tới nến trước).
- **Lệnh**: vào **ngược** chiều cú giật ở giá mở nến M15 kế.
  - SL = cực trị cú giật + 0,25 ATR (spread còn rộng).
  - Đóng sau tối đa 8 nến (2 giờ).

**Biến thể**:

| Thành phần | Lựa chọn |
|---|---|
| k | 2 / 3 |
| Mục tiêu | hồi 50% thân nến tin / 2R |

Tổng 4 biến thể.

**Kỳ:**

| Kỳ | Thời gian |
|---|---|
| Train | 08/2021–2023 |
| Validate | 2024–2025 |
| Test | **2026, mở một lần** |

**Đối chứng:** cùng luật áp cho nến giật ≥ k ATR **ở cùng giờ server, ngày không có tin USD HIGH trong ±1 giờ**, cùng kỳ. Câu hỏi: cú giật do tin có quay về nhiều hơn cú giật thường không?

**Chọn:** R/lệnh > 0 ở cả train và validate, ≥ 20 lệnh mỗi kỳ, và hơn đối chứng ở validate. Chọn biến thể có min(train, validate) cao nhất.

**Test:** R/lệnh > 0, cận dưới bootstrap 90% > 0.

## C — lệch USD + phá đỉnh thất bại (H1), thành lệnh

**Bán**, dùng nguyên định nghĩa G99:
- F11: phiên London/NY;
- F12: có đỉnh 20 ngày mới trong 48 nến, nay đóng lại dưới đỉnh 20 ngày cũ;
- F17: vàng tăng 120 nến trong khi chỉ số USD (EURUSD + USDJPY) cũng tăng;
- nền "bán lỏng": đóng dưới EMA21 H1 và DI− > DI+;
- mỗi cụm 24 nến chỉ một lần.

**Mua (đối xứng):**
- phiên London/NY;
- đáy 20 ngày mới trong 48 nến, nay đóng lại trên đáy 20 ngày cũ;
- vàng giảm 120 nến trong khi USD cũng giảm;
- đóng trên EMA21 và DI+ > DI−.

**Lệnh:** vào ở giá mở nến H1 kế. SL 2 ATR H1, TP 6 ATR (3R), tối đa 120 nến. Đúng nhãn BIG6 của G99, chuyển thành lệnh.

**Kỳ** (như G99): train 03/2018–2021, validate 2022–06/2025, **test 07/2025–06/2026, mở một lần**.
- Chuỗi này đã được chọn trên train + validate ở G99, nên ở đây chỉ báo cáo hai kỳ đó và **quyết định bằng test**.

**Đối chứng:** cùng lệnh ở các nến H1 có cùng nền (bán lỏng / mua lỏng) nhưng **không** có chuỗi điều kiện, cùng kỳ test.

**Đạt (từng chiều):** test R/lệnh > 0, cận dưới bootstrap 90% > 0, hơn đối chứng.

## A, D, E — so sánh số đã có

- Lấy đúng số trong báo cáo G118, G80, G111/G113.
- Ghi rõ đã dùng kỳ nào và còn thiếu gì.
- Không chạy lại để "tìm" thêm.

## Đầu ra

`research/long/g132_reversal_leads.py`, báo cáo `reports/2026-10-20-g132-reversal-leads.md`, có bảng so sánh chung cả 5 manh mối.
