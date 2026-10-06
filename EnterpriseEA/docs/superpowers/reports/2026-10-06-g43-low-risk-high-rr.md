# G43: rủi ro thấp, RR cao — kết quả (06/10/2026)

Kế hoạch: `docs/superpowers/plans/2026-10-06-g43-low-risk-high-rr.md`. Chỉ dữ liệu MT5. Mọi lựa chọn trên 2010–2016; 2017–2020 và 2021–2025 chỉ để kiểm chứng. Script: `research/long/g43_low_risk.py` (A, B, C1–C2), `g43_reversal.py` (C3, F), `g43_oos.py` (ngoài mẫu), `g43_scalp.py` + `g43_scalp_gated.py` (E), `g43_final.py` (ghép + căng thẳng). Số liệu đầy đủ trong `research/long/results/g43_*.md`.

## Kết luận

**Phương pháp chọn (G4):** S04 + S06B (lọc USD, bồi +1R) + T2, với

1. **Rủi ro theo setup = kỳ vọng ÷ phương sai** ước trên 2010–2016: S04 0,98×, S06B 1,51×, T2 0,51× mức nền (nền 0,3%: S04 0,29%, S06B 0,45%, T2 0,15%);
2. **T2 chỉ nhận tín hiệu có "nến đà"** (nến tín hiệu hoặc nến trước đóng ở 1/4 trên/dưới của biên ≥ 1 ATR theo chiều lệnh);
3. **T2 bồi 1 lệnh ở +1R** (cùng rủi ro tiền; dừng của lệnh bồi đặt tại giá vào của lệnh đầu, lệnh đầu giữ dừng/trail của nó — đính chính 06/10: lúc bồi có thể có tới 2 đơn vị rủi ro mở cho tới khi trail kéo lệnh đầu qua hòa vốn).

Toàn kỳ 2010–2025 ở nền 0,3%: **+4,9%/năm, DD 4,3%, RR 3,7**, 15/16 năm dương (chỉ 2010 −1,5%), tháng tệ nhất −1,4%. Ở 0,5%/lệnh (CUSTOM): +7,4%/năm, DD 5,5%.

**Dự phòng thận trọng (G1):** chỉ bước 1 (trọng số). Ổn định nhất qua 3 kỳ (điểm 0,27 / 0,46 / 0,60), DD 3,2%, tuần dương 42%, RR 2,0.

Thêm một quy tắc có căn cứ: **T2 không chạy trên FX** (EURUSD/GBPUSD/USDJPY yếu 2010–2025, và 12 cặp FX ngoài mẫu −0,27R so với +0,17R trên kim loại/crypto/dầu/chỉ số). Bỏ T2 trên FX nâng điểm cả G1 (0,47 → 0,59) lẫn G4 (0,49 → 0,52). Danh sách T2 LIVE hiện tại (XAU, BTC) đã theo quy tắc này.

## Kết quả theo hướng

| Hướng | Kết quả | Quyết định |
|---|---|---|
| A mốc | M5 + T2 (5 symbol) +5,3%/năm, DD 5,6%, dương 3 kỳ. "M5 + T2 XAU/BTC" trông tốt hơn nhưng có nhìn trước (G41 chọn sau khi thấy kết quả; XAU/BTC không có dữ liệu train) | mốc = 5 symbol |
| B1 phân bổ theo setup | kỳ vọng/phương sai: điểm tốt hơn ở **cả 3 kỳ** (0,27/0,46/0,60 so với 0,17/0,33/0,22), DD 5,6% → 3,2%, tháng tệ nhất −2,8% → −1,7%; nghịch đảo độ lệch cải thiện ít | **giữ** |
| B2 giảm rủi ro khi sụt | mọi ngưỡng đều xấu hơn; không hơn giảm rủi ro ngẫu nhiên (p ≈ 0,97) | loại |
| B3 lọc theo đường vốn | không hơn bỏ lệnh ngẫu nhiên (p 0,11–0,92), xấu ở train/validate | loại |
| B4 trần rủi ro mở | 1,2% hiện tại hợp lý; nới không thêm gì | giữ nguyên |
| C1 dừng lỗ/trail T2 | dừng 1,5 ATR tốt hơn trên 5 symbol (p = 0,001 so với ngẫu nhiên) nhưng **xấu hơn ngoài mẫu** (FX −0,37 so với −0,27); trail 4–5 âm ở validate | giữ 2 ATR / trail 3 |
| C2 bồi T2 | +1R: MAR tốt hơn cả 3 kỳ, RR 2,0 → 3,6; DD và tỷ lệ tuần dương xấu hơn khi đứng một mình | giữ trong G4 |
| C3 thoát khi đảo chiều | EMA20, EMA20 sau +1R, kênh ngược 30, nến nhấn chìm ngược: đều xấu hơn (cắt lệnh thắng lớn), không hơn thoát ngẫu nhiên | loại |
| F mô hình nến | chỉ "nến đà" trên T2 tốt hơn cả 3 kỳ (p = 0,03; chưa qua hiệu chỉnh 12 phép thử) và **cải thiện cả hai nhóm ngoài mẫu** (FX −0,27 → −0,22, tài sản xu hướng +0,17 → +0,25). Nhấn chìm/pin bar/inside bar và mọi mô hình trên S04/S06B: không | giữ "nến đà" cho T2 |
| E SCALP M15 | E1 hồi EMA, E3 phá đỉnh/đáy ngày: âm 3 kỳ và ngoài mẫu; E2 co hẹp → bung ≈ 0 | không có SCALP đạt |
| E2 SCALP chỉ khi T2 mở cùng chiều | E2: 15/24 bộ dương 3 kỳ, +0,27/+0,21/+0,08R, p < 0,001, phí ×2 vẫn +0,06; **ngoài mẫu ≈ 0** (tài sản xu hướng +0,02R n=74, FX −0,11R) | theo dõi shadow, chưa đưa vào |

## Kiểm tra căng thẳng (toàn kỳ, nền 0,3%)

| Kiểm tra | G4 %/năm / DD | G1 %/năm / DD |
|---|---|---|
| gốc | +4,91% / 4,3% | +4,24% / 3,2% |
| phí ×2 + trượt 0,1R/lệnh | +3,46% / 6,1% | +2,42% / 4,6% |
| bỏ 10 lệnh lời nhất | +3,16% / 7,0% | +3,05% / 4,2% |
| bỏ từng symbol (tệ nhất) | +3,23% (bỏ BTC) | +2,76% (bỏ BTC) |
| không T2 trên FX | +3,93% / 2,7% | +3,74% / 2,7% |
| 0,5%/lệnh | +7,41% / 5,5% | +5,97% / 5,2% |

## Lợi nhuận theo tuần/tháng/năm

Ở nền 0,3%, G4: 52% tháng dương, tháng p10 −0,9%, tháng tệ nhất −1,4%; 36% tuần dương (ít lệnh, lệnh thắng lớn). 15/16 năm dương; năm tốt nhất 2022 +12,8%. SCALP không cải thiện được độ đều theo tuần vì không có SCALP nào dương sau phí; độ đều đến từ đa dạng hóa (3 setup gần độc lập) và trọng số theo rủi ro.

## Hạn chế

- Trọng số ước trên 2010–2016 với 46–325 lệnh mỗi setup; sai số lớn. Không ước lại trên dữ liệu sau.
- "Nến đà" và bồi T2 làm điểm validate (2017–2020) thấp hơn G1; G4 hơn G1 chủ yếu nhờ 2021–2025.
- Chưa có forward thật cho S06B và T2 (đang SHADOW).

## Bước tiếp đề xuất (cần người dùng chốt trước khi LIVE)

1. EA: input hệ số rủi ro theo setup (mặc định 0,98 / 1,51 / 0,51), áp trong cùng trần rủi ro hiện có.
2. EA: lọc "nến đà" cho T2 và bồi +1R cho T2 (dùng lại cơ chế bồi của S06B), ở SHADOW trước.
3. Theo dõi E2-trong-T2 ở shadow; chỉ xét lại khi có ≥ 100 lệnh forward.
