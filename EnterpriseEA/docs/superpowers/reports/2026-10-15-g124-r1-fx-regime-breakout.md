# G124 R1: FX co hẹp → bung ra, chỉ đánh khi có xu hướng — kết quả

Ngày 15/10/2026.
- Kế hoạch: `docs/superpowers/plans/2026-10-15-g124-fx-regime-breakout.md` (commit `2966f0c`).
- Script: `research/long/g124_fx_regime.py`.
- Bảng: `research/long/out/g124_r1.csv`. Log: `out/g124_r1_log.txt`.

## Kết luận ngắn

**Không biến thể nào đạt.** Kỳ test 2023–10/2026 **vẫn kín**.

**Bộ lọc độ thẳng ER60** (ý chính của R1: chỉ đánh khi D1 "thẳng") **không giúp**. Nó còn làm kém hơn bản chỉ lọc theo chiều.

Phát hiện có ích nằm ở **đối chứng G1**:
- G1 chỉ đánh theo chiều lợi nhuận 120 ngày, không xét ER.
- G1 tốt hơn G0 (không lọc) ở **cả 4 ô K × thoát**, ở cả train và validate, hơn khoảng +0,04 đến +0,14R/lệnh.
- Tức là **chiều của động lượng chậm mang lợi thế**. Còn điểm vào co hẹp → bung ra gần như không thêm gì.

## Dữ liệu

| Mục | Chi tiết |
|---|---|
| Rổ | 6 cặp chính thật trong terminal: EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDJPY |
| Khung | H4 + D1, 2010 → 10/2026 |
| Chi phí | Spread của nến H4 (MT5 lưu spread **nhỏ nhất** trong nến, nên có thêm cột "+1 pip" để thử chi phí khắt khe) + phí 6 USD/lot |
| Swap | Theo mức hiện tại, báo riêng |
| Ngưỡng ER60 (train, gộp 6 cặp) | Trung vị 0,110; phân vị 2/3 là 0,159 |

## Kết quả (rổ 6 cặp; số lệnh / R mỗi lệnh)

| K | Thoát | Cổng | Train | Validate | +1 pip (tra / val) | Cận dưới 90% (tra+val) | Đối chứng ngẫu nhiên (val), p | Đạt |
|---|---|---|---|---|---|---|---|---|
| 12 | TP 3R | G0 | 1.029 / −0,090 | 419 / −0,024 | | | | đối chứng |
| 12 | TP 3R | G1 | 743 / +0,045 | 328 / +0,042 | | | | đối chứng |
| 12 | TP 3R | **G2** | 395 / +0,014 | 183 / −0,091 | −0,02 / −0,14 | −0,11 | p 0,75 | không |
| 12 | TP 3R | **G3** | 261 / −0,005 | 124 / +0,063 | −0,03 / +0,01 | −0,09 | p 0,27 | không |
| 12 | trail | G0 | 1.281 / −0,056 | 567 / −0,033 | | | | đối chứng |
| 12 | trail | G1 | 910 / −0,019 | 404 / +0,039 | | | | đối chứng |
| 12 | trail | **G2** | 475 / −0,081 | 212 / +0,023 | | −0,12 | p 0,57 | không |
| 12 | trail | **G3** | 310 / −0,122 | 141 / +0,084 | | −0,14 | p 0,23 | không |
| 24 | TP 3R | G0 | 490 / +0,070 | 223 / +0,077 | | | | đối chứng |
| 24 | TP 3R | **G1** | **323 / +0,126** | **149 / +0,172** | +0,07 / +0,11 | **+0,04** | ngẫu nhiên +0,06, **p 0,18** (train p 0,05) | (đối chứng) |
| 24 | TP 3R | **G2** | 171 / +0,021 | 81 / −0,112 | | −0,15 | p 0,76 | không |
| 24 | TP 3R | **G3** | 108 / +0,128 | 49 / −0,027 | | −0,10 | p 0,63 | không |
| 24 | trail | G0 | 606 / −0,072 | 272 / +0,053 | | | | đối chứng |
| 24 | trail | **G1** | 367 / +0,030 | 172 / +0,190 | | | ngẫu nhiên +0,04, p 0,085 (train p 0,39) | (đối chứng) |
| 24 | trail | **G2** | 185 / −0,078 | 87 / +0,133 | | −0,11 | p 0,34 | không |
| 24 | trail | **G3** | 116 / −0,010 | 49 / +0,211 | | −0,08 | p 0,24 | không |

**Tổng R theo năm, ô tốt nhất K24 / TP 3R / G1 (train + validate):**

| 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| +6,5 | −6,9 | −4,5 | +14,5 | +15,3 | +7,2 | +5,6 | +4,4 | −1,3 | +1,4 | +10,4 | +19,2 | −5,4 |

- Tổng R theo cặp: EUR +34, GBP +28, CAD +10, AUD +1, JPY 0, NZD −6.
- Không có hơn 2 năm âm liên tiếp. Cặp lớn nhất chiếm 47% tổng R.

## Đọc kết quả

1. **ER60 cắt nhầm lệnh tốt.** Cổng G2/G3 bỏ khoảng một nửa đến hai phần ba số lệnh của G1, nhưng R/lệnh không tăng mà còn giảm.
   - Độ "thẳng" 60 ngày đo trên D1 không phân biệt được giai đoạn tốt và xấu cho điểm vào H4.
2. **Chiều động lượng 120 ngày giúp đều ở mọi ô**, hơn G0 từ +0,04 đến +0,14R/lệnh. Đây đúng là hiệu ứng mà hướng R2 (rổ động lượng chậm) nhắm tới.
3. **Ô K24 / TP 3R / G1 trông khá:**
   - +0,13 và +0,17R/lệnh, cận dưới +0,04, thêm 1 pip chi phí vẫn dương.
   - Nhưng nó là **đối chứng** trong kế hoạch, và ở validate chỉ thắng vào ngẫu nhiên với p 0,18.
   - Phần lớn lợi thế đến từ chính chiều động lượng: vào ngẫu nhiên theo đúng chiều đó cũng được +0,06R ở validate.
   - Theo luật đã đăng ký thì không chọn được.
4. **Swap theo mức hiện tại** làm giảm khoảng 0,05–0,07R/lệnh, nặng ở các lệnh mua EUR/GBP và bán USDJPY. Với swing giữ nhiều ngày, swap là chi phí đáng kể.

## Bước tiếp

- **R2 (rổ động lượng chậm)** là hướng hợp lý tiếp theo: R1 cho thấy lợi thế nằm ở chiều 120 ngày, không nằm ở điểm vào bung ra.
- Kỳ test 2023–2026 vẫn sạch để kiểm R2.
- Nếu R2 không đạt, có thể đăng ký riêng một ô "K24 / TP 3R / theo chiều 120 ngày" để mở test một lần. Nhưng cần ghi rõ ô này được chọn sau khi đã thấy train và validate.
