# Phân xử giữa các setup và sổ candidate (05/10/2026)

Trạng thái: **IMPLEMENTED (G18)**. Liên quan: đặc tả v1.4 TC-007 (nhiều candidate cùng lúc, Risk Kernel chỉ cấp risk trong budget), S06 v1 (`2026-10-05-s06-compression-expansion-v1-design.md`).

## 1. Vấn đề
Các setup (S02, S04, S06) phát hiện tín hiệu độc lập rồi đi chung một cổng vào lệnh. Trước thay đổi này:
- Thứ tự vòng lặp (S02 trước S04 trước S06) quyết định ai được vào khi có xung đột, không theo bằng chứng.
- Hai setup có thể mở hai lệnh cùng ý tưởng (cùng symbol, cùng chiều, cùng khung), rủi ro gấp đôi.
- Kết quả từng setup chỉ có cho lệnh đã vào. Candidate bị chặn (quota, trùng, ngược chiều, tin, sentiment) mất dấu, nên không đo được giá trị của từng bộ lọc và setup đứng sau bị thiếu mẫu.
- SHADOW chỉ ghi kế hoạch lệnh lúc trigger, không có kết quả.

## 2. Quyết định
| # | Điểm | Chốt |
|---|---|---|
| A1 | Phát hiện tín hiệu | Giữ độc lập theo setup (không đổi) |
| A2 | Ưu tiên (B) | Khi nhiều candidate cùng lượt, duyệt theo bằng chứng G10: **S06 SWING → S04 SWING → S02 SWING → S04 SCALP → S02 SCALP** (SWING trước SCALP, trong cùng khung S06 → S04 → S02). Mỗi lượt timer vẫn tối đa 1 lệnh |
| A3 | Trùng lặp (E2) | Mỗi **symbol + chiều + khung** chỉ 1 lệnh (vị thế hoặc lệnh chờ) của EA, mọi setup. SCALP và SWING cùng chiều được phép cùng tồn tại. Lý do chặn `DUPLICATE_SAME_SIDE` |
| A4 | Chồng SCALP lên SWING | Lệnh SCALP vào khi đã có SWING cùng symbol, cùng chiều: rủi ro × `InpScalpRiskWithSwingSameSide` (mặc định **0,5**; 1,0 = tắt). Chọn mặc định thận trọng vì người dùng chưa chốt |
| A5 | Sổ candidate | Mọi candidate TRIGGERED (và lệnh LIMIT S02 đã đặt) được ghi một dòng vào `logs/candidates.jsonl` khi có kết cục cuối: vào lệnh hoặc lý do cuối cùng khiến nó không vào |
| A6 | Kết quả ảo | Tính offline bằng `research/g10/candidates_eval.py` với mô hình Trade Manager "tm" của G10 (đã khớp replay của EA), không mô phỏng trong EA |

## 3. Sổ candidate (`logs/candidates.jsonl`)
Mỗi dòng (một candidate):

| Trường | Ý nghĩa |
|---|---|
| `candidate_id`, `setup`, `profile`, `symbol`, `timeframe`, `direction` | Danh tính |
| `bar_time` | Giờ server mở nến trigger (khớp cột `time` của `research/bars_*.csv`) |
| `extreme`, `zone_low`, `zone_high`, `signal_atr`, `key_level` | Đủ để dựng lại kế hoạch lệnh offline |
| `mode` | LIVE / SHADOW |
| `disposition` | `EXECUTED` hoặc `NOT_EXECUTED` |
| `reason` | Lý do cuối: ví dụ `DUPLICATE_SAME_SIDE`, `OPPOSITE_SETUP_ACTIVE`, `NEWS_PRE_NEWS_…`, `S06_COUNTER_HTF`, `LIVE_SESSION_…_LIMIT`, `SHADOW_MODE`, `LIVE_NOT_ARMED`, `NOT_EVALUATED:<lý do toàn cục>` |
| `entry_kind` | MARKET / STOP / LIMIT khi đã vào |
| `first_seen_utc`, `closed_utc` | Lần đầu thấy và lúc chốt kết cục |

Quy tắc:
- Một candidate có thể bị chặn ở lượt này rồi vào lệnh ở lượt sau (ví dụ hết cửa sổ tin): chỉ kết cục cuối được ghi.
- Lý do của từng candidate được lấy từ chính lượt xét của nó (không phải lý do toàn cục của vòng lặp).
- Candidate chưa từng được xét (vòng lặp dừng sớm vì đã gửi một lệnh, controller chặn, chưa arm) ghi `NOT_EVALUATED:<lý do toàn cục>`.
- Giới hạn: sổ giữ candidate đang mở trong bộ nhớ; EA khởi động lại giữa chừng thì candidate đang mở lúc đó không được ghi (tối đa một nến của mỗi engine).

## 4. Kết quả ảo và báo cáo
`python research/g10/candidates_eval.py [--since YYYY-MM-DD]`:
1. Đọc `logs/candidates.jsonl`, dựng context nghiên cứu (`context.build`) cho từng symbol/khung, tìm nến trigger theo `bar_time`.
2. Dựng candidate theo định dạng `replay.evaluate`: điểm cấu trúc và HTF lấy từ context tại nến đó.
3. Đánh giá bằng mô hình "tm" có chi phí, không lọc HTF và tin (bộ lọc đã thể hiện ở `reason`): S06 TP cố định 3R; S02/S04 TP cấu trúc.
4. In bảng theo setup/khung × nhóm kết cục (EXECUTED, mỗi nhóm lý do chặn, SHADOW), cột n, kỳ vọng R, tỷ lệ thắng; và cột "như chạy một mình" (tất cả candidate). Ghi `results/candidates_eval.json`.

Candidate chưa có đủ nến sau trigger được báo `NO_BARS_YET`. Nến nghiên cứu được xuất lại khi gắn lại EA và lần xuất cũ đã hơn 7 ngày (hoặc xoá `research/bars_meta.json` rồi gắn lại EA).

Giới hạn của kết quả ảo: không có trượt giá, giá vào là giá đóng nến trigger, trong một nến chạm SL được tính trước TP. Chỉ dùng để so sánh giữa setup và đo giá trị bộ lọc, không thay số liệu lệnh thật.

## 5. Kiểm chứng
- Oracle Python của thứ tự ưu tiên khớp hàm MQL.
- Test mã nguồn: vòng lặp đi theo thứ tự ưu tiên; kiểm tra E2 trước khi dựng kế hoạch; hệ số chồng SCALP; ghi lý do theo từng candidate; ghi sổ khi vào lệnh và khi candidate rời TRIGGERED.
- Test bộ đánh giá trên context tổng hợp: tính R, nhóm theo kết cục, báo `NO_BARS_YET`.
- Toàn bộ test Python và compile MetaEditor 0/0 trước khi deploy.

## 6. Kế hoạch triển khai
1. `Integration/SetupArbitration.mqh`: thứ tự ưu tiên (thuần, không phụ thuộc broker).
2. `Integration/ControlledLiveRuntime.mqh`: duyệt theo thứ tự ưu tiên; `EEA_ControlledLiveSameSideActive` (E2); `EEA_ControlledLiveApplyStackRisk` (A4); lý do theo từng engine.
3. `Runtime/CandidateLedger.mqh`: sổ candidate và ghi `logs/candidates.jsonl`.
4. `EnterpriseEA.mq5`: input `InpScalpRiskWithSwingSameSide`, nối sổ candidate vào `OnTimer` sau lượt vào lệnh.
5. `research/g10/candidates_eval.py`: kết quả ảo và báo cáo.
6. Test: `Tests/setup_arbitration_tests.py`, `Tests/candidate_ledger_tests.py`.
7. Deploy cùng S06 (G12), G15, G16; người dùng gắn lại EA; kiểm tra log; merge `main` và push.
