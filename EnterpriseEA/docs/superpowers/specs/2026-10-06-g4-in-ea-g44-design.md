# G44: đưa phương pháp G4 (G43) vào EA (06/10/2026)

Người dùng đồng ý 06/10. Nghiên cứu: `reports/2026-10-06-g43-low-risk-high-rr.md`.

## Thay đổi

| Phần | EA | Input (mặc định) |
|---|---|---|
| Trọng số rủi ro theo setup | `EEA_SetupRiskWeight` nhân vào rủi ro một lệnh và trần tiền một lệnh (lệnh mới và lệnh bồi). Kẹp trong [0, 1]: trọng số **chỉ giảm** rủi ro, theo nguyên tắc của `RiskLimitsProfile` | `InpRiskWeightS04=0.65`, `InpRiskWeightS06B=1.00`, `InpRiskWeightT2=0.34` (S02/S06 = 1) |
| Lọc "nến đà" cho T2 | `EEA_T2MomentumClose` + `momentum_mask` trong `EEA_T2ProcessClosedBar`: tín hiệu chỉ nhận khi nến tín hiệu hoặc nến trước có biên ≥ ATR của nó và đóng ở 1/4 theo chiều lệnh; nếu không: `T2_NO_MOMENTUM_CLOSE`. Áp cho cả SHADOW và LIVE | `InpT2MomentumFilter=true` |
| Bồi lệnh T2 ở +1R | Cơ chế bồi của S06B (G31) mở rộng cho T2: nến H4 đóng ≥ +1R → 1 lệnh MARKET cùng rủi ro tiền (× trọng số T2), dừng tại giá vào của lệnh đầu, cùng TP trần 20R, Trade Manager profile POSITION (trail 3 ATR), qua mọi cổng như lệnh thường (phiên, headroom, ngân sách, tin, kinh tế) | `InpT2PyramidLive=false` |
| Kết quả ảo | `candidates_eval.py`: T2 có thêm `r_add` (cùng lệnh với bồi +1R, `pyramid.run`) | — |

Trọng số G43 (kỳ vọng ÷ phương sai, 2010–2016) là S04 0,98, S06B 1,51, T2 0,51; chia cho 1,51 để lớn nhất = 1. Điểm chọn (p10 ÷ DD p90, MAR) không đổi theo tỷ lệ; lợi nhuận tuyệt đối thấp hơn tương ứng, có thể bù bằng mức rủi ro nền (G42 `InpEvalRiskPercent`).

## Khác với S06B khi bồi

S06B chỉ bồi khi lệnh đầu đã về hòa vốn (rủi ro cặp ≤ 1 đơn vị). T2 bồi như nghiên cứu: lệnh đầu giữ dừng ATR của nó, nên lúc bồi có thể mở tới 2 đơn vị × 0,34; trần rủi ro mở và ngân sách danh mục vẫn kiểm cho lệnh bồi.

## Hiệu lực hiện tại

S04 LIVE (trọng số 0,65 áp ngay khi nạp lại), S06B và T2 SHADOW (trọng số, bồi T2 chỉ có tác dụng khi chuyển LIVE). Lọc nến đà áp ngay cho tín hiệu T2 shadow.

## Kiểm chứng

`Tests/g4_in_ea_g44_tests.py`: oracle nến đà, lọc chỉ bớt tín hiệu, **khớp nghiên cứu trên dữ liệu thật** (XAUUSD 2021–2023, EURUSD 2015–2017, ≥ 95% trùng tín hiệu), kiểm nguồn MQL cho trọng số / lọc / bồi / input, kết quả ảo `r_add`. Cập nhật 2 test cũ theo chữ ký mới. 64 file test đạt, compile MetaEditor 0/0.
