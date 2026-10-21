# G126: chuỗi phiên Á–Âu–Mỹ và ADR trên vàng — kế hoạch đăng ký trước (20/10/2026)

## Vì sao

Người dùng hỏi hai kịch bản:
1. **Chuỗi phiên**: phiên Á + Âu đi > 0,5%, phiên Mỹ đẩy tiếp hoặc đảo — phiên kế tiếp diễn biến thế nào?
2. **ADR**: khi ngày đã đi gần hết biên độ trung bình (ADR), có canh bắt đáy / bán đỉnh an toàn được không, nhất là khi có xác nhận bằng chỉ báo?

Đã có (không làm lại):
- G113: dự báo kiểu ngày lúc 10:00 yếu (AUC 0,65), chọn setup theo kiểu ngày không có lãi.
- G84B: chờ quét ngược lúc giao phiên không tốt hơn vào ngay.
- G125 V2: lệnh OCO phá biên độ phiên âm.
- G109: quét & lấy lại vùng giá âm.
- MKT02: trên chỉ số, giá xa VWAP thì chạy tiếp.

G126 kiểm **điều kiện chuỗi phiên** và **mức đã dùng ADR**, đứng riêng và làm bộ lọc cho S07 / VHedge.

## Dữ liệu (MT5)

- XAUUSD **H1 và M30 thật từ 03/2018** (trước đó file chỉ là nến ngày), server time → UTC theo luật g67 (UTC+2, +3 mùa DST Mỹ).
- Ngày = ngày UTC.
- Phiên UTC:

| Phiên | Giờ UTC |
|---|---|
| Á | 00:00–07:00 |
| Âu | 07:00–13:00 |
| Mỹ | 13:00–21:00 |

**Kỳ:**

| Kỳ | Thời gian |
|---|---|
| Train | 03/2018–12/2021 |
| Validate | 2022–2025 |
| Test | **2026, niêm phong**: chỉ mở một lần ở cuối cho phần đã được chọn |

**Chi phí khắt khe:** spread của nến vào và ra, trượt 0,5 × spread trung vị mỗi chiều, phí $6/lot (0,06 giá).

**ATR ngày** = ATR14 của các ngày UTC trước đó. **ADR** = trung bình biên độ (cao − thấp) 10 ngày UTC trước.

## Phần A — chuỗi phiên (mô tả)

- **AE** = (giá đóng 13:00 − giá mở 00:00) ÷ giá mở. s = dấu của AE.
- **Nhóm theo |AE|**: < 0,5% (đối chứng) | 0,5–1% | ≥ 1%.
- **Phiên Mỹ so với AE**: q = s × (đóng 21:00 − đóng 13:00) ÷ |AE| (theo giá).

| q | Nhóm |
|---|---|
| ≥ 0,25 | **đẩy tiếp** |
| −0,25 đến 0,25 | **giằng co** |
| −0,75 đến −0,25 | **đảo nhẹ** |
| ≤ −0,75 | **đảo mạnh** |

**Kết quả đo** (theo chiều s, đơn vị ATR ngày):
- phiên Á hôm sau;
- phiên Âu hôm sau;
- phiên Mỹ hôm sau;
- cả ngày hôm sau;
- tỷ lệ hôm sau phá đỉnh (s = +1) hoặc đáy (s = −1) của hôm nay.

So với ngày |AE| < 0,5% và với mọi ngày.

**Ô đáng chú ý** khi: ≥ 30 ngày ở mỗi kỳ, kết quả trung bình cùng dấu và |t| ≥ 2 ở **cả** train và validate.

## Phần B — giao dịch theo chuỗi phiên

Chỉ với các ô đáng chú ý ở Phần A:
- Vào ở đầu cửa sổ kết quả theo chiều ô đó chỉ ra (theo s hoặc ngược s), ra ở cuối cửa sổ.
- SL bảo vệ 1 đơn vị. Đơn vị R = 0,5 × ATR ngày.
- **Chọn** khi R/lệnh sau chi phí > 0 ở cả train và validate.

## Phần C — đánh ngược khi đã dùng hết ADR (M30, 07:00–20:00 UTC)

**Tín hiệu bán** (mua đối xứng):
- Nến M30 đóng khi biên độ ngày (cao − thấp từ 00:00) ≥ k × ADR;
- và giá đóng nằm trong 20% trên của biên độ ngày.
- Mỗi ngày mỗi chiều chỉ tín hiệu đầu tiên.

**Biến thể:**

| Thành phần | Lựa chọn |
|---|---|
| k | 0,8 / 1,0 / 1,2 |
| E0 | vào ngay ở giá mở nến kế |
| E1 | chờ trong 4 nến một **nến từ chối**: đóng ngược chiều chạy và dưới đáy nến trước (mua: đóng trên đỉnh nến trước) |
| E2 | chỉ khi đỉnh ngày đã vượt đỉnh ngày trước (mua: đáy ngày dưới đáy ngày trước): chờ trong 4 nến một nến đóng lại dưới đỉnh ngày trước (**quét rồi lấy lại**) |

Tổng 3 × 3 = 9 biến thể.

**Lệnh:**
- SL = cực trị từ lúc tín hiệu đến lúc vào + 0,3 ATR14 M30.
- TP = giữa biên độ ngày lúc vào.
- Đóng lúc 21:00 UTC nếu chưa chạm SL/TP.
- Bỏ lệnh nếu RR < 1.

**Đối chứng công bằng** (bài học G112): mỗi lệnh được đặt lại cùng chiều, cùng khoảng SL/TP tính theo ATR, cùng giờ UTC, nhưng ở **một ngày khác** chọn ngẫu nhiên trong cùng kỳ. 200 lần. p = tỷ lệ lần ngẫu nhiên có R ≥ thật.

**Chọn:** biến thể có R/lệnh > 0 ở cả train và validate, ≥ 40 lệnh mỗi kỳ, và p < 0,05 ở validate. Báo cáo **mua và bán riêng**, không được để biến thể chỉ còn một chiều mà không nói rõ.

## Phần D — bộ lọc cho S07 và VHedge

Nhãn tại lúc vào lệnh của mỗi chân S07 (sổ G89/G107, thời gian UTC) và mỗi lệnh VHedge G119 (thời gian server → UTC):

| Mã | Nhãn |
|---|---|
| D1 | thiên hướng ngày: \|giá lúc vào − giá mở 00:00 UTC\| ≥ 0,5% và cùng chiều lệnh |
| D2 | ADR đã dùng (cao − thấp từ 00:00 ÷ ADR) < 0,8 |
| D3 | còn chỗ theo chiều lệnh: (giá mở + ADR theo chiều lệnh − giá vào) ≥ 1R của lệnh |

**Một nhãn được giữ** (như G79) khi nhóm giữ có R/lệnh cao hơn nhóm bỏ ở cả train và validate, và còn ≥ 40% số lệnh.
- VHedge chỉ có từ 05/2024, nên chỉ báo cáo, không chọn.

## Test 2026 (một lần)

- Biến thể / bộ lọc được chọn ở Phần B, C, D chạy trên 2026.
- **Đạt** khi R/lệnh > 0 và cận dưới bootstrap 90% > 0. Bộ lọc S07 đạt khi nhóm giữ > nhóm bỏ trên 2026.
- Không có gì được chọn thì không mở 2026.

## Đầu ra

`research/long/g126_session_adr.py`, báo cáo `reports/2026-10-20-g126-session-chain-adr.md`.
