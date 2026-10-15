# G121: cung–cầu từ tick (dòng lệnh) và volume profile — kết quả train / validate

Ngày 15/10/2026. Kế hoạch: `docs/superpowers/plans/2026-10-15-g121-orderflow-profile.md` (đăng ký trước, commit `6d505f2`).
Script: `research/long/g121_ticks.py` (dựng dữ liệu), `research/long/g121_study.py` (nghiên cứu). Bảng đầy đủ: `research/long/out/g121_study.csv`.

## Kết luận ngắn

**Không ô nào đạt.** Cả 6 tín hiệu (A1 hấp thụ, A2 kiệt sức, A3 lực chủ động, B1 luật 80%, B2 từ chối ở cạnh, B3 qua vùng mỏng) đều âm hoặc ≈ 0 ở train. Không ô nào thắng đối chứng ở validate.
Theo kế hoạch, **kỳ test 2026 vẫn kín**. Không có gì để mở, cũng không có gì để so tiếp với S07 hay VHedge.

## Dữ liệu

- **Nguồn:** tick thật XAUUSD-VIP của terminal, 20/02/2024 → 14/10/2026. Gồm 187.872 nến M5 và 66 file theo tháng.
- **Cách dựng:** nến OHLC và spread dựng thẳng từ tick. Lý do: terminal chỉ giữ khoảng 100 nghìn nến M5, tức từ 05/2025 trở đi, không đủ cho kỳ train.
- **Đối chiếu:** với nến M5 của MT5 (tháng 06/2025), OHLC lệch 0,000, spread khớp, số tick khớp tick volume (tương quan 1,0).
- **Ngưỡng d = delta / số tick, lấy từ train:**

  | Ngưỡng | Giá trị |
  |---|---|
  | 1/3 cao nhất | ≥ 0,035 |
  | 1/3 thấp nhất | ≤ −0,027 |
  | 1/10 cao nhất | ≥ 0,106 |
  | 1/10 thấp nhất | ≤ −0,099 |

## Kết quả (R/lệnh, đã tính spread)

| Tín hiệu | Thoát | Train: lệnh | Train: R | Train: mua / bán | Validate: lệnh | Validate: R | Validate: mua / bán | Đối chứng | p |
|---|---|---|---|---|---|---|---|---|---|
| A1 hấp thụ (đánh ngược) | TP 2R | 413 | −0,22 | −0,11 / −0,34 | 72 | −0,52 | −0,41 / −0,68 | −0,11 | 0,98 |
| A1 | TP 3R | 411 | −0,22 | | 72 | −0,64 | | −0,13 | 0,99 |
| A1 | cấu trúc | 408 | −0,13 | | 72 | −0,56 | | −0,09 | 0,98 |
| A2 kiệt sức (phân kỳ CVD) | TP 2R | 3.997 | −0,16 | −0,12 / −0,21 | 1.553 | −0,07 | 0,00 / −0,15 | −0,12 | 0,11 |
| A2 | TP 3R | 3.774 | −0,16 | −0,09 / −0,24 | 1.440 | +0,01 | +0,09 / −0,09 | −0,09 | 0,06 |
| A2 | cấu trúc | 4.029 | −0,15 | | 1.534 | −0,02 | | −0,07 | 0,28 |
| A3 lực chủ động (đánh theo) | TP 2R | 281 | +0,005 | −0,03 / +0,03 | 16 | +0,58 | | — | — |
| A3 | TP 3R | 276 | −0,13 | | 16 | +0,67 | | — | — |
| A3 | cấu trúc | 278 | −0,10 | | 16 | +0,10 | | — | — |
| B1 luật 80% | mức | 111 | −0,36 | −0,51 / −0,23 | 53 | −0,32 | | +0,04 | 0,90 |
| B2 từ chối ở cạnh | mức | 194 | −0,28 | −0,42 / −0,11 | 63 | −0,23 | +0,44 / −0,81 | −0,17 | 0,61 |
| B3 qua vùng mỏng | mức | 161 | −0,27 | −0,35 / −0,17 | 75 | −0,54 | | +0,03 | 0,94 |

"Đối chứng" là trung vị R/lệnh của 200 lần chạy:
- A: vào ngẫu nhiên cùng giờ, cùng chiều.
- B: dùng mức giả, dịch ±1–3 lần độ rộng vùng giá trị.

"p" là tỉ lệ lần chạy đối chứng bằng hoặc tốt hơn tín hiệu thật.

## Đọc kết quả

- **A1 hấp thụ thua đối chứng rất rõ** (−0,5R so với −0,1R ở validate).
  - Bán ngược sau một nến mua chủ động mạnh ở đỉnh là đứng trước lực đang chạy.
  - Trên dữ liệu này, "hấp thụ" nhìn từ tick không phải dấu hiệu đảo chiều.
  - Đảo chiều tín hiệu sau khi đã thấy kết quả là chọn theo dữ liệu, nên không làm ở đây.
- **A2 kiệt sức:** ở train là −0,16R trên gần 4.000 lệnh.
  - Ở validate, bản TP 3R nhích lên +0,01R, p = 0,06.
  - Nhưng bản này không đạt tiêu chí 1 (train phải > 0) và chỉ mua mới dương. Không đạt.
- **A3 lực chủ động:** ở train ≈ 0 (+0,005R với TP 2R).
  - Ở validate chỉ có 16 lệnh, vì sang nửa cuối 2025 delta theo tick ít khi chạm ngưỡng 1/10 của train.
  - Quá ít lệnh để kiểm định. Không đạt.
- **B (volume profile của ngày trước):** cả ba đều âm ở cả hai kỳ.
  - Hai trong ba còn thua mức giả, tức các mức VAH/VAL/POC/LVN hôm qua không tốt hơn một đường bất kỳ.
  - Stop 0,5–1 ATR M5 quá gần so với nhiễu trong ngày của vàng.

## Vì sao "dòng lệnh" ở đây yếu

XAUUSD trên MT5 là CFD, không có khối lượng khớp lệnh thật. "Tick" là số lần **giá chào** thay đổi, "delta" là số lần giá bid nhích lên trừ số lần nhích xuống.

Đây là số đo nhịp báo giá của broker, không phải lực mua/bán thật như footprint trên sàn tương lai (GC). Đó là giới hạn của dữ liệu MT5. Theo quy ước nghiên cứu, chỉ dùng dữ liệu MT5, không tải nguồn ngoài.

## So với các bot đang có

Vì không ô nào đạt, chưa có đường vốn để so cùng kỳ ở 1,5%/lệnh (INITIAL). Mốc tham chiếu từ G120 (cùng cửa sổ, 1,5%/lệnh):

| Bot | Kết quả | DD |
|---|---|---|
| S07 | 39.613 USD | 6,1% |
| VHedge G119 | 58.613 USD | 13,8% |

Các tín hiệu G121 tốt nhất chỉ quanh 0R/lệnh trước chi phí thời gian, nên không có cửa đóng góp.

## Đã sửa trong lúc làm

- Lệnh bán dính stop ban đầu bị trừ spread hai lần (stop đã kích hoạt bằng giá ask). Đã sửa rồi chạy lại. Bảng trên là sau khi sửa: phía bán tốt lên khoảng 0,05–0,13R, kết luận không đổi.
- A2 dùng phân kỳ CVD theo cách thường gặp: CVD tại đỉnh mới thấp hơn CVD tại đỉnh 24 nến trước đó. Kế hoạch ghi "tổng delta của nhịp lên"; hai cách gần tương đương.
