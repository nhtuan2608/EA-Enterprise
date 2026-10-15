# G104: TP tại vùng thanh khoản / đáy cũ cho lệnh swing (trên nền giữ lệnh BOX của G103)

Ngày 11/10/2026. Script: `research/long/g104_liquidity_tp.py`.
- Luật vào lệnh: G100 V2 (M15).
- Giữ lệnh: G103 BOX (đóng lệnh theo nến H1 đóng vượt mốc, stop cứng xa hơn).
- Train: 07/2021–2023. Validate: 2024–06/2025. Test: vẫn kín.

## Vùng TP

Vùng được cố định ngay lúc vào lệnh, chỉ dùng đáy/đỉnh đã xác nhận trước đó, và chọn vùng gần nhất cách giá vào ≥ 3R.

| Mã | Vùng (bán; mua đối xứng) |
|---|---|
| H4S | đáy swing H4 |
| D1S | đáy swing D1 |
| EQL | đáy bằng nhau: 2 đáy H4 trong 60 ngày cách nhau ≤ 0,25 ATR D1 |
| ORG | gốc nhịp tăng trước: đáy thấp nhất 30 ngày trước đỉnh 20 ngày |

**Cách chốt:**
- FULL: chốt hết tại vùng.
- HALF: chốt 50% tại vùng, phần còn lại giữ theo BOX.

Không tìm được vùng thì lệnh giữ theo BOX như thường.

## Kết quả (R/lệnh; tổng R trong ngoặc)

| Chiều | TP | Có vùng | Khoảng cách trung vị | Train | Validate |
|---|---|---|---|---|---|
| Bán | không TP (BOX) | — | — | +0,09 (+12) | −0,14 (−9) |
| Bán | H4S, chốt hết | 90–100% | 3,1R | −0,01 | −0,11 |
| Bán | D1S, chốt 50% | 90–100% | 3,5–4,6R | +0,01 | −0,09 |
| Bán | EQL, chốt hết | 60–80% | 3,4R | −0,04 | −0,09 |
| Bán | ORG, chốt hết | 50–80% | 7–9R | −0,04 | −0,13 |
| Mua | không TP (BOX) | — | — | **+0,27 (+44)** | **+0,67 (+80)** |
| Mua | H4S, chốt hết | 64–89% | 3,1R | +0,01 | +0,36 |
| Mua | D1S, chốt 50% | 65–90% | 3,5–3,9R | +0,16 | +0,52 |
| Mua | ORG, chốt 50% | ~50% | 7–12R | +0,27 | +0,63 |

**Ví dụ bán 12/03 (giá vào 5.152):**

| Vùng | Giá vùng | Khoảng cách | Kết quả |
|---|---|---|---|
| Đáy cũ gần nhất (H4S / EQL / D1S) | 5.047 / 5.033 / 5.015 | 3–4R | chốt hết +3–4R; chốt 50% khoảng +11R |
| **Gốc nhịp tăng trước (ORG)** | **4.403** | **21,4R** | **chốt hết +21,4R** (chạm 23/03), cao hơn giữ BOX không TP (+19,1R) |

## Kết luận

1. **Đáy cũ gần nhất quá gần** (khoảng 3–4R). Chốt ở đó cắt mất các lệnh chạy dài: bán ở train từ +0,09 xuống khoảng 0, mua giảm mạnh ở cả hai kỳ. Với bán ở validate, chốt ở đó chỉ bớt lỗ một chút (từ −0,14 lên −0,09 / −0,11).
2. **Gốc nhịp tăng trước (ORG)** là vùng TP có ý nghĩa cho swing: xa 7–12R. Với mua thì gần như không làm giảm kết quả. Ở ví dụ 12/03 nó đúng là vùng giá tìm tới (4.403, đáy thật 4.099). Nhưng trên toàn bộ dữ liệu, bán vẫn âm ở validate.
3. Nếu dùng TP cho swing, nên đặt ở **gốc nhịp tăng/giảm trước đó**, không đặt ở đáy/đỉnh cũ gần nhất. Hoặc chốt một phần ở đó và giữ phần còn lại.
