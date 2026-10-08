# G66: diễn tập live trên demo (LIVE-03, PRE-08, REQ-004/005/006/013/015/016) — kế hoạch

08/10/2026, người dùng đồng ý ("làm phần 3"). Tài khoản VTMarkets-Demo (`real_account=false`), phiên CUSTOM ACTIVE tới 14/10,
S04 + S06B LIVE ở 0,5%/lệnh. Cấu hình live không đổi; mọi diễn tập tắt được và không chạy lại khi khởi động lại.

## D1 — lệnh thử đi trọn đường live

`Integration/DrillRuntime.mqh` (theo mẫu `S06BPyramidRuntime.mqh`): input `InpDrillEntry` (mặc định false),
`InpDrillNonce` (chuỗi; rỗng = tắt), `InpDrillSymbol` (EURUSD), `InpDrillDirection` (BUY). Khi bật, EA tạo đúng một
candidate `DRILL-<symbol>-<nonce>` (setup DRILL, profile SWING), dừng lỗ 1,0 × ATR14 H1 (0,3 quá sát so với luật spread ≤ 25% dừng lỗ), mục tiêu 1R, khối lượng = khối
lượng tối thiểu của broker, và cho đi qua cùng các bước như lệnh thật: phiên ủy quyền, News Guard, phân xử
(mỗi symbol + chiều + profile một lệnh), kế hoạch rủi ro, quyết định rủi ro, lưu, intent, audit ủy quyền, gửi lệnh, đối soát,
đăng ký Trade Manager. Mỗi nonce chạy một lần (`current/drill_state.json`).

Đạt khi: lệnh 0,01 lot mở với SL/TP đúng; `ORDER`/`EXECUTION` audit đủ; Trade Manager có lệnh; `live_status.drill` ghi
trạng thái; không có lệnh thứ hai cho cùng nonce.

## D2 — khởi động lại khi đang có lệnh (PRE-08, E2E-08, TC-030)

Lúc lệnh D1 còn mở: đóng MT5 bình thường, mở lại. Đạt khi: Trade Manager khôi phục lệnh (cùng ticket, cùng SL/TP),
đối soát không chặn (`recovery_blocked=false`), không gửi lệnh trùng (idempotency), D1 không chạy lại.

## D3 — dừng khẩn (O-12, REQ-019, LIVE-07)

`/pause` qua Telegram (người dùng gửi) lúc có lệnh D1: `live_status.operator_paused=true`, vào lệnh mới bị chặn
(`OPERATOR_PAUSED_ENTRIES`), Trade Manager vẫn quản lý lệnh. `/resume` + `/confirm` trả về RUNNING.

## D4 — chặn lỗ ngày/tuần (LIVE-03), offline

Lấy sổ rủi ro thật (`current/risk_ledger.json`) và giới hạn đang dùng (`live_status.risk`), cộng lỗ giả lập theo bậc và chạy
các oracle Python của EA (`ftmo_headroom_oracle`, `account_risk_ledger_oracle`, `dry_run_gate_oracle`): đạt khi lệnh mới bị
chặn đúng tại ngưỡng ngày 2% / tuần 4% nội bộ và trước sàn CUSTOM (ngày 5%, tổng 10%), kể cả khi tính rủi ro đang mở.

## Kết thúc

Lệnh D1 đóng bằng SL/TP hoặc lệnh tay; `trades.jsonl` có dòng kết quả (REQ-005 G20); lịch ngày có R (G64). Tắt
`InpDrillEntry`. Ghi kết quả từng bài vào roadmap (G66) và ma trận truy vết.
