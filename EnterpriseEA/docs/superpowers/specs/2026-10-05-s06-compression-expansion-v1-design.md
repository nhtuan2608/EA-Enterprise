# S06 Compression Expansion v1 (05/10/2026)

Trạng thái: **IMPLEMENTED (G12)**. Gồm `Setups/CompressionExpansion.mqh`, nhánh S06 trong `Runtime/StrategyCandidateRuntime.mqh` và `Integration/ControlledLiveRuntime.mqh`, oracle `Tests/s06_oracle.py`, test `Tests/s06_compression_expansion_tests.py`.

## 1. Căn cứ
Báo cáo G10 phần 3 (`reports/2026-10-05-g10-parameter-study.md`): S06 SWING trên H1 là setup duy nhất dương ở cả ba giai đoạn 2024 / 2025 / 2026 (+0,10R mỗi lệnh, 550 lệnh, tỷ lệ thắng 51%, t ≈ 1,8). Các tham số lân cận đều dương. Lợi thế nhỏ, chưa chắc chắn về thống kê.

## 2. Quyết định của người dùng (05/10)
| # | Điểm | Chốt |
|---|---|---|
| D1 | Chế độ | **LIVE** (`InpS06Mode=S06_LIVE`), tài khoản demo |
| D2 | Symbol | Cả 5 symbol, gồm BTCUSD (nghiên cứu −0,07R) |
| D3 | Thoát lệnh | Như nghiên cứu: SL ở mép xa của hộp, TP cố định 3R, Trade Manager SWING như live |
| D4 | Rủi ro | Như S02/S04: cùng % rủi ro, News Guard, sentiment, giới hạn lỗ ngày/tuần, tính chung giới hạn SWING/ngày |

## 3. Quy tắc (khớp `research/g10/setups.py::s06`, cấu hình box 12, max_box_atr 3, contraction 0,85, mode confirm, sl far)
- **Khung:** chỉ SWING, vào lệnh trên H1, cấu trúc HTF từ H4. Một engine S06 cho mỗi symbol.
- **Hộp:** 12 nến H1 đã đóng ngay trước nến đang xét. Hộp đủ điều kiện khi cao − thấp ≤ 3 × ATR(14) của nến trước và ATR đó ≤ 0,85 × ATR 48 nến trước.
- **Nến thoát (RELEASED):** biên độ ≥ 1 ATR, đóng ngoài mép hộp hơn 0,10 ATR, thân cùng chiều ≥ 50% biên độ. Xét chiều lên trước.
- **Nến xác nhận (TRIGGERED):** nến kế tiếp đóng ngoài mép hộp theo cùng chiều. Không xác nhận → EXPIRED; nến xác nhận không bao giờ mở một lần thoát mới.
- **Vào lệnh:** MARKET ngay sau nến xác nhận, chỉ khi giá còn ngoài hộp và chưa chạy quá 0,5 ATR so với giá đóng nến xác nhận. Candidate chỉ sống trong một nến H1.
- **Lọc HTF:** chỉ cùng chiều cấu trúc H4 (NEUTRAL được tính là cùng chiều), ngược chiều bị từ chối (`S06_COUNTER_HTF`), không giảm rủi ro như S02.
- **SL:** mép xa của hộp ± max(0,10 × ATR nến xác nhận; 1,5 × spread). **TP:** entry ± 3 × khoảng SL.
- **Trade Manager:** hộp được giao như "vùng" của S02/S04.

## 4. Kiểm chứng
- Oracle Python khớp prototype nghiên cứu trên dữ liệu tổng hợp và trên toàn bộ H1 thật của 5 symbol (754/754 tín hiệu trước lọc HTF).
- 487 test Python đạt; compile MetaEditor 0 lỗi, 0 cảnh báo.

## 5. Giới hạn
- Replay lịch sử (`SetupReplay.mqh`) chưa gồm S06; số liệu lịch sử nằm ở nghiên cứu G10.
- S06 dùng chung khóa "symbol + H1" với S02/S04 SWING khi kiểm tra lệnh chờ đang mở: một lệnh chờ S02 SWING trên cùng symbol chặn S06 tới khi lệnh đó kết thúc.
- Kỳ vọng khoảng 4 lệnh mỗi tuần cho cả 5 symbol; cần vài tháng forward mới đủ mẫu để đánh giá.
