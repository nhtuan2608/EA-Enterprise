# G169: bộ lọc "Score" đa khung kiểu LFX cho lệnh lướt M15 / M5 — báo cáo (17/11/2026)

[Kế hoạch](../plans/2026-11-17-g169-mtf-score-filter.md) · script `research/long/g169_score_filter.py` · kết quả `research/long/results/g169/summary.json`

## Kết luận

**KHÔNG ĐẠT** ở cả hai bộ kích hoạt.
- **Score có sắp xếp được lệnh:** nhóm ≥ 70 tốt hơn nhóm < 50.
- Với T2, tỷ lệ TP1 tăng đơn điệu ở cả hai kỳ và hơn bản chỉ lọc D1.
- **Nhưng mọi nhóm đều âm sau chi phí.**
  - Hình học lướt kiểu LFX (SL 1,1 ATR M15 ≈ 5–8 USD, TP 1,5 / 2,5 R) có tỷ lệ chạm TP1 chỉ 35–39 %.
  - Chi phí (spread + trượt giá + phí) chiếm ~0,1 R mỗi lệnh.
- Không có setup mới.

**Kiểm code:** Score ứng viên đầu tính tay = 54,55 = engine.

## Kết quả (vàng; M15 07/2021 → 17/11/2026, bỏ 06/2026)

**T1 (mỗi giờ, cả hai chiều): R TB / tỷ lệ TP1.**

| Nhóm | Kỳ chọn 2021–23 | Kỳ kiểm 2024–26 | Lệnh / tuần |
|---|---|---|---|
| **Score ≥ 70** | −0,211 / 35,5 % | **−0,081** / 38,5 % | ~39 |
| Score 50–69 | −0,260 / 33,9 % | −0,144 / 36,0 % | ~22 |
| Score < 50 | −0,262 / 33,8 % | −0,146 / 36,1 % | ~40 |
| Chỉ D1 | −0,242 / 34,1 % | −0,074 / 38,3 % | ~39 |
| Không lọc | −0,243 / 34,3 % | −0,114 / 37,2 % | ~90 |

CI 97,5 % của R TB nhóm ≥ 70: [−0,170; −0,111].

**T2 (nến từ chối M15): R TB / tỷ lệ TP1.**

| Nhóm | Kỳ chọn | Kỳ kiểm | Lệnh / tuần |
|---|---|---|---|
| **Score ≥ 70** | −0,282 / 33,1 % | **−0,114** / 37,6 % | ~8 |
| Score 50–69 | −0,291 / 32,9 % | −0,212 / 33,6 % | ~4 |
| Score < 50 | −0,318 / 31,5 % | −0,224 / 33,1 % | ~10 |
| Chỉ D1 | −0,291 / 32,7 % | −0,127 / 36,8 % | ~9 |
| Không lọc | −0,305 / 32,1 % | −0,181 / 34,8 % | ~22 |

CI 97,5 % của R TB nhóm ≥ 70: [−0,245; −0,132].

**Độ nhạy M5 (05/2024 →), R TB nhóm ≥ 70:**
- T1: −0,073 (chỉ D1: −0,070);
- T2: −0,122 (chỉ D1: −0,094).

## Tiêu chí

| # | Tiêu chí | T1 | T2 |
|---|---|---|---|
| 1 | Tỷ lệ TP1 tăng đơn điệu theo Score, hai kỳ | trượt (kỳ kiểm: 50–69 ≈ < 50) | **đạt** |
| 2 | Nhóm ≥ 70 dương hai kỳ, CI > 0 | trượt | trượt |
| 3 | Nhóm ≥ 70 hơn chỉ D1, hai kỳ | trượt (kỳ kiểm −0,081 so với −0,074) | **đạt** |
| 4 | Hai chiều ≥ −0,05 | trượt | trượt |
| 5 | Chi phí × 1,5 > 0 | trượt | trượt |
| 6 | M5 dương | trượt | trượt |
| 7 | ≥ 1 lệnh / tuần | đạt | đạt |

## Đọc kết quả

1. **Score của LFX là một tín hiệu xếp hạng thật nhưng yếu.**
   - Nhóm ≥ 70 so với < 50 tốt hơn ~0,05–0,1 R / lệnh.
   - Nhưng lợi thế này **gần như trùng với lọc D1 đơn giản** ở T1.
   - Tách 64 % / 17 % trong 37 kèo của LFX là do mẫu nhỏ; trên dữ liệu dài, cách biệt chỉ 2–5 điểm %.
2. **Hình học lướt (SL ~1 ATR M15, TP 1,5 R / 2,5 R) âm trên vàng sau chi phí** dù lọc thế nào.
   - Để hòa vốn cần ~42 % chạm TP1; thực tế 35–39 %.
   - Điều này khớp với G125 / G154: lướt vàng đóng.
3. **Kỳ kiểm (2024–2026) đỡ hơn kỳ chọn** ở mọi nhóm, kể cả "không lọc". Đó là do thị trường (vàng tăng mạnh, biến động lớn), không phải do bộ lọc.

## Hệ quả

- **Không đưa Score / bot lướt kiểu LFX vào EA.**
- Nếu muốn dùng Score, chỉ nên dùng như **thước đo rủi ro** cho setup đã có lợi thế (ví dụ ghi nhật ký Score lúc S07 vào lệnh), và phải kiểm riêng.
- **Ghi vào sổ cái:** 2 phép thử, 0 đạt.
