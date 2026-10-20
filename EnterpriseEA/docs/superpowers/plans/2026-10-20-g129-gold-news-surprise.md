# G129: vàng sau tin USD bất ngờ — kế hoạch đăng ký trước (20/10/2026)

## Vì sao

Mọi hướng tìm tín hiệu từ giá và volume trên vàng đã đóng (G121–G128). Nguồn thông tin còn chưa dùng là **tin kinh tế Mỹ có số thực tế và dự báo**. Vàng phản ứng mạnh với NFP, CPI, PCE, ISM, bán lẻ…

FX01 đã thử ý này cho EUR/GBP và thất bại: thị trường phản ánh xong trong chính nến tin. Với vàng thì chưa thử.

## Dữ liệu (MT5)

**Lịch tin:** lịch MT5 do EA xuất (`research/calendar`, định dạng 2, giờ server khớp nến như G54).
- Chỉ dùng tin **USD, mức HIGH**, có cả số thực tế và dự báo (có từ 2017).
- **Bỏ** "EIA Crude Oil Stocks Change": tồn kho dầu không có chiều rõ với USD hay vàng.

**Hướng bất ngờ cho USD:** thực tế > dự báo là tốt cho USD, trừ tên có "unemployment", "jobless", "claims" thì đảo chiều.
- Nhiều tin cùng giờ: cộng dấu lại; tổng = 0 thì bỏ.
- **Chiều vàng d = − hướng USD**.

**Độ lớn bất ngờ z:** (thực tế − dự báo) ÷ độ lệch chuẩn các lần bất ngờ **trước đó** của cùng tên tin (cần ≥ 8 lần trước). Nhiều tin cùng giờ thì lấy |z| lớn nhất.

**Nến:** XAUUSD **M30** từ 03/2018, giờ server.
- Nến tin = nến M30 chứa giờ ra tin.
- ATR14 M30 tính đến nến trước nến tin.

**Kỳ:**

| Kỳ | Thời gian |
|---|---|
| Train | 03/2018–2021 |
| Validate | 2022–2025 |
| Test | **2026, niêm phong**: chỉ mở cho biến thể được chọn |

**Chi phí khắt khe:**
- vào ở giá mở nến sau nến tin;
- trượt mỗi chiều = max(0,5 × spread trung vị; spread của nến vào), vì spread còn rộng ngay sau tin;
- phí $6/lot.

**Kiểm tra đồng hồ trước khi tính** (như G54):
- ≥ 95% NFP rơi vào 12:30 hoặc 13:30 UTC;
- biên độ nến M30 vàng chứa NFP ≥ 1,5 lần nến cùng giờ ở các thứ Sáu khác.

Một trong hai không đạt thì dừng, không có kết quả.

## Biến thể (tín hiệu ở lúc nến tin đóng)

| Mã | Tín hiệu |
|---|---|
| S | **Theo bất ngờ**: vào theo chiều d, bất kể nến tin đi đâu |
| C | **Theo bất ngờ có xác nhận**: nến tin đóng cùng chiều d, thân ≥ 50%, biên độ ≥ 1 ATR |
| B | **Theo nến tin**: nến tin có biên độ ≥ 1,5 ATR, thân ≥ 50%; vào theo chiều nến, bỏ qua số liệu |

- S và C có thêm hai mức độ lớn: mọi |z| | chỉ |z| ≥ 1.
- **Thoát**:

| Mã | Thoát |
|---|---|
| X1 | SL ở cực trị bên kia của nến tin ± 0,1 ATR; TP 2R; tối đa 8 nến (4 giờ) |
| X2 | cùng SL, không TP, đóng sau 16 nến (8 giờ) |

  Với S khi nến tin đi ngược d, SL dùng cực trị của nến tin theo phía ngược d.
- Tổng: (S, C) × 2 mức z × 2 thoát + B × 2 thoát = **10 biến thể**.

## Đối chứng

- **Xáo trộn dấu bất ngờ**: giữ nguyên thời điểm tin, hoán vị ngẫu nhiên dấu (và |z|) giữa các tin trong cùng kỳ, 500 lần. p = tỷ lệ lần xáo trộn có R ≥ thật. Cách này giữ đúng biến động quanh tin, chỉ bỏ thông tin.
- Với B (không dùng số liệu): đối chứng là cùng luật nến ≥ 1,5 ATR ở **cùng giờ server những ngày không có tin HIGH USD**.

## Chọn

Một biến thể được chọn khi đủ cả ba:
1. R/lệnh > 0 ở cả train và validate;
2. ≥ 40 lệnh mỗi kỳ;
3. p đối chứng < 0,05 ở validate.

Báo cáo **mua và bán riêng**. Không chọn biến thể chỉ sống nhờ một chiều mà không ghi rõ.

## Phần phụ — cùng chiều bộ lọc S07 (chỉ mô tả)

Với biến thể được chọn (hoặc S/X1 nếu không có): R/lệnh khi d cùng phía EMA200 H4 so với ngược phía, theo từng kỳ.

## Test 2026 (mở một lần)

- Biến thể được chọn chạy trên 2026.
- **Đạt** khi R/lệnh > 0 và cận dưới bootstrap 90% > 0.
- Không có biến thể nào được chọn thì 2026 vẫn niêm phong.

## Đầu ra

`research/long/g129_gold_news.py`, báo cáo `reports/2026-10-20-g129-gold-news-surprise.md`.
