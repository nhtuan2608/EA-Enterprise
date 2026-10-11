# G103: giữ lệnh theo cấu trúc giá (không EMA), stop dương chống quét, bồi lệnh có xác nhận râu

Ngày 11/10/2026. Script: `research/long/g103_structure_hold.py`. Luật vào lệnh: G100 V2 (M15). Kỳ:
- Train: 07/2021–2023.
- Validate: 2024–06/2025.
- Test: vẫn kín.

## Thiết kế

**Bảo vệ ban đầu:** stop cứng tại đỉnh/đáy 16 nến M15 ± 0,1 ATR. Không còn thoát sớm theo EMA100 M15 trước khi lãi 1R.

**Stop dương chống quét:**
- Lệnh chỉ đóng khi **nến H1 đóng** vượt mốc + 0,25 ATR H1.
- Có thêm stop cứng ở mốc + 1,5 ATR H1, và stop cứng chỉ được siết vào.

**Các cách đặt mốc (bán; mua đối xứng):**

| Mã | Cách đặt mốc |
|---|---|
| REF | EMA55 H1 sau khi lãi 1R (để so) |
| SW1 | đỉnh swing H1 gần nhất nằm dưới giá vào, áp dụng từ +1R |
| SW2 | đỉnh swing thứ hai (rộng hơn) |
| BE2 | từ +2R khóa ở giá vào − 0,5R, sau đó theo SW1 |
| BOX | mép trên của hộp nghỉ H1 gần nhất (8 nến, rộng ≤ 2,5 ATR) mà giá đã đóng phá xuống, áp dụng từ +1R |

**Bồi lệnh có xác nhận (+A):**
- Lệnh gốc đã hết rủi ro (mốc đã qua giá vào).
- Có nến H1 rút râu: râu ≥ 50% biên độ, đóng ở nửa theo chiều lệnh, râu không vượt mốc.
- Nến H1 sau đóng phá đáy/đỉnh của nến râu → vào ở giá mở kế tiếp.
- Stop của lệnh bồi: sau râu + 0,25 ATR.
- Tối đa 2 lệnh bồi, cách nhau ≥ 4 nến H1.

**Tỉ lệ bị quét:** lệnh thoát ở stop/mốc, rồi trong 24 giờ giá chạy tiếp ≥ 2R theo chiều lệnh.

## Kết quả (R/lệnh và tổng R)

| Chiều | Cách giữ | Train | Validate | Bị quét (train / validate) |
|---|---|---|---|---|
| Bán | REF | −0,02 (−4) | −0,06 (−4) | 27% / 31% |
| Bán | SW1 | −0,06 (−11) | −0,09 (−8) | 23% / 24% |
| Bán | BE2 | +0,02 (+3) | −0,14 (−10) | 20% / 24% |
| Bán | **BOX** | **+0,09 (+12)** | −0,14 (−9) | **19%** / 24% |
| Bán | BOX + bồi | +0,33 (+46) | −0,22 (−14) | 19% / 24% |
| Mua | REF | +0,22 (+39) | +0,63 (+84) | 32% / 23% |
| Mua | SW2 | +0,23 (+47) | +0,41 (+63) | 28% / 26% |
| Mua | **BOX** | **+0,27 (+44)** | **+0,67 (+80)** | 28% / 23% |
| Mua | **BOX + bồi** | **+0,36 (+59)** | **+1,02 (+121)** | 28% / 23% |

**Ví dụ bán 12/03:**
- BOX: +19,1R (thoát 25/03 ở 4.484).
- SW1/SW2/BE2: chỉ +3,5R, bị đóng ở nhịp nén 16–17/03 vì đỉnh swing quá gần.

## Kết luận

1. **Giữ theo hộp nghỉ (BOX)** là cách giữ theo cấu trúc tốt nhất: chỉ dời stop sau khi giá phá khỏi một vùng nghỉ, và đóng theo nến H1.
   - So với EMA55 H1, nó tốt hơn ở 3/4 ô (riêng bán validate kém hơn: −0,14 so với −0,06).
   - Tỉ lệ bị quét thấp hơn với bán ở train (19% so với 27%).
   - Dời stop theo từng đỉnh swing thì quá sát, hay bị đóng ở các nhịp nén.
2. **Bồi lệnh có xác nhận râu** giúp rõ cho mua (validate từ +0,67 lên +1,02R/lệnh). Với bán, nó giúp ở train (+0,33R/lệnh) nhưng làm validate tệ hơn.
3. **Bán vẫn chưa dương ở validate** với mọi cách giữ, dù bỏ thoát sớm đã giúp bản EMA55 H1 từ −0,14 (G100) lên −0,06R/lệnh.
