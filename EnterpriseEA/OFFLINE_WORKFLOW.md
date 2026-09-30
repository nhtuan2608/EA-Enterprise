# Quy trình phát triển EA khi máy không có MT5

Tài liệu này áp dụng cho giai đoạn phát triển trên máy không được phép cài MT5 hoặc MetaEditor. Source MQL5 trong `EnterpriseEA/` vẫn là ứng dụng đích; Python trong `Tests/` chỉ tạo dữ liệu kiểm thử và đối chiếu kết quả, không trở thành engine giao dịch thứ hai.

## Việc có thể làm và bằng chứng cần giữ

| Bước | Công việc | Bằng chứng offline |
| --- | --- | --- |
| Phase 1 | Khóa schema/config, state/event, lý do từ chối, quy tắc lưu file và checkpoint khởi động. | Contract tests, fixture hợp lệ/không hợp lệ, kiểm tra không có API gửi lệnh trong shell. |
| Phase 2 | Định nghĩa một setup đầu tiên bằng state machine trên nến đã đóng; tạo chuỗi dữ liệu đúng, thiếu điều kiện, hết hạn và restart. | Input bars cố định, candidate/event kỳ vọng, so sánh từng transition và reason code. |
| Phase 3 | Viết các phép tính thuần cho FTMO 1-Step/2-Step, SL/TP theo invalidation/target, lot theo instrument spec và giới hạn portfolio. | Ví dụ số khóa trước, ca biên rollover/DST, volume step, conversion, lệnh tương quan và dữ liệu thiếu. |
| Phase 4+ | Mô phỏng lifecycle, news/AI timeout và dashboard state bằng fixture hoặc mock. | E2E trace có timestamp, config version, action/rejection và outcome kỳ vọng. |

Mỗi fixture phải nêu nguồn/giả định, input, output kỳ vọng và version. Test Python chỉ là oracle cho thiết kế; khi viết MQL5 phải đối chiếu output thực tế của EA với cùng fixture. Không dùng kết quả Python làm bằng chứng MQL5 đã biên dịch hoặc vận hành đúng.

## Cổng phải thực hiện trên môi trường có MT5

1. Biên dịch toàn bộ `.mq5/.mqh` bằng MetaEditor và lưu log không có lỗi compiler.
2. Chạy EA trong MT5 ở observer mode, xác nhận log, file sandbox, restart và trạng thái fail closed.
3. Chạy Strategy Tester với dữ liệu và broker specs mục tiêu; so khớp fixture, kiểm tra multi-symbol, thời gian, spread và chi phí.
4. Chỉ sau đó mới đánh dấu gate Paper; không phát lệnh live từ các kiểm thử offline.

Cổng này có thể chạy sau trên máy Windows khác hoặc môi trường được tổ chức cho phép. Việc chọn môi trường đó không thay đổi yêu cầu phải kiểm tra broker/account cụ thể trước Paper/Live.

## Thông tin cần khi đi tới các phase tương ứng

- Trước Phase 2: broker/server demo, danh sách broker symbol thực tế, setup đầu tiên và timeframe.
- Trước Phase 3: loại tài khoản hedging/netting, policy 1-Step/2-Step hoặc custom, vốn ban đầu, tiền tệ và các giới hạn risk nội bộ. Không cần chia sẻ thông tin đăng nhập.
- Trước News/AI integration: nguồn lịch tin, cách chạy bridge và provider được phép.

Trạng thái hiện tại: Phase 1 có source và contract tests; Phase 2 có module S02 Break Retest cô lập; Phase 3 có các phép tính thuần cho giá SL/TP, net reward/risk, headroom FTMO, ngân sách rủi ro trước sizing, volume, resolver symbol, gate dry run, ledger reset ngày và reducer rủi ro account-wide. Phase 4 có observer expected path, prototype vòng đời pending order, contract checkpoint restore và audit chain cô lập. Bộ kiểm thử offline hiện đạt 132/132. Một adapter runtime chỉ đọc cho account/symbol/positions/orders/deals đã được nối vào EA shell và MetaEditor build 6230 biên dịch sạch 0 lỗi/0 cảnh báo. Một isolated MT5 tester run đã tạo runtime JSON/audit thật và xác nhận snapshot account/symbol/positions/orders/deals trong cửa sổ bảy ngày, nên adapter đạt `RUNTIME_OBSERVED` và `BROKER_RECONCILED_BOUNDED` cho đúng tester scope. Lần chạy thứ hai cũng thực hiện fresh broker read thành công; tuy nhiên tester tái tạo Files sandbox nên chưa chứng minh checkpoint sống qua restart trong retained terminal sandbox, chưa so khớp toàn bộ output MQL với fixture và chưa đạt Paper.


## Phase 3 FTMO headroom (offline)

Module Risk/FtmoHeadroom.mqh cung cấp phép tính floor/headroom cho policy FTMO 1-Step/2-Step với trạng thái headroom_status thuần chính sách. SUFFICIENT không phải quyền vào lệnh; kiểm tra reconcile, portfolio stress và internal limits chưa được thực hiện. Snapshot reset phải được caller xác thực theo Europe/Prague/DST; high-water 1-Step phải có dữ liệu persisted hợp lệ. Xem Risk/FTMO_HEADROOM_OFFLINE.md để biết giả định và giới hạn. Fixture chỉ dùng số tổng hợp. Oracle/test Python không chứng minh compile hoặc runtime MQL5.

`Risk/StructuralLevels.mqh` đề xuất giá SL/TP từ invalidation, target, buffer và tick size; kết quả không phải entry permission. Xem `Risk/STRUCTURAL_OFFLINE.md` để biết kiểm tra broker và chi phí còn thiếu.

`Risk/PortfolioBudget.mqh` lấy các giới hạn account-wide đã được caller reconcile để tính ngân sách rủi ro trước sizing. `Risk/VolumeSizing.mqh` dùng báo giá loss per lot, rồi yêu cầu báo giá lại lỗ và margin ở đúng volume cuối. Cả hai không cấp quyền vào lệnh; kiểm tra correlation, currency exposure, broker spec và reconcile thực tế vẫn cần adapter ở môi trường MT5.

`Market/SymbolRegistry.mqh` chỉ chấp nhận mapping canonical/broker đã lưu rõ ràng, đúng server và metadata fingerprint. `Risk/TradeEconomics.mqh` kiểm tra net reward/risk và khoảng trống đến target từ báo giá đã xác thực. Các module này chưa có adapter MT5.

`Integration/DryRunCandidateGate.mqh` ghép các kết quả theo thứ tự, kiểm tra identity, version, tiền tệ, độ mới và snapshot ID. Trạng thái tốt nhất là `REVIEWABLE_CANDIDATE`, không tạo order intent hoặc quyền vào lệnh. Xem `Integration/DRY_RUN_CANDIDATE_GATE_OFFLINE.md` để biết các giả định về nguồn evidence.

`Risk/DailyResetLedger.mqh` kiểm tra chuỗi snapshot reset ngày do nguồn ngoài xác nhận theo Europe/Prague, gồm hai mốc đổi giờ trong fixture. `Risk/AccountRiskLedger.mqh` cộng rủi ro từ snapshot vị thế/lệnh/deal được caller reconcile; nó không chứng minh dữ liệu broker đã đầy đủ hay rủi ro ban đầu của position được giữ bất biến qua các snapshot. Xem tài liệu offline của từng module để biết điều kiện fail closed.

## Checkpoint ledger và restart (offline)

`Storage/LedgerCheckpoint.mqh` định nghĩa checkpoint có version, identity tài khoản/epoch, sequence, timestamp và fingerprint cho lịch sử reset ngày cùng số tổng hợp rủi ro account-wide. Khi phục hồi, trạng thái reset vẫn `UNKNOWN` cho tới khi xác nhận lại ngày Prague hiện tại; ledger rủi ro vẫn `POLICY_DATA_UNKNOWN`, chặn lệnh mới cho tới khi đối soát broker account-wide mới. Cùng ngày có thể xác nhận lại snapshot bằng `EEA_ReattestRestoredDailyReset`; qua ngày mới phải áp dụng snapshot reset kế tiếp theo đúng thứ tự. Xem `Storage/LEDGER_CHECKPOINT_OFFLINE.md`.

Đây là contract/fixture cô lập: EA shell chưa đọc/ghi checkpoint này, chưa có serializer/parser MQL5, chưa lưu lineage từng position, chưa replay lịch sử broker và chưa kiểm chứng crash recovery. Test Python kiểm tra điều kiện hợp lệ và fail closed, không thay thế compile hoặc chạy trên MT5.

## Bổ sung đặc tả Telegram trước khi triển khai

Đặc tả v1.2 và `TELEGRAM_CONTROL_SPEC.md` đề xuất dùng Telegram Gateway để hỏi AI/MCP và nhận reply, đồng thời cho operator được xác thực tạm dừng hoặc yêu cầu bật lại entry mới. AI Level 0/1 chỉ trả lời và đề xuất; không tự bật bot. Bật lại cần xác nhận hai bước và EA kiểm tra lại toàn bộ safety gate. `PAUSED_ENTRIES` vẫn bảo vệ vị thế đang mở và không tác động nút AutoTrading toàn terminal.

Đã thêm `Integration/RemoteModeGate.mqh` và ba JSON schema cho command, câu hỏi AI và reply, kèm fixture/oracle Python. Module thuần chỉ trả `VALIDATED_PENDING_COMMIT`, không gửi Telegram, không lưu state, không được EA shell gọi và không cấp quyền giao dịch. Xem `Integration/REMOTE_MODE_GATE_OFFLINE.md` để biết trust boundary. Theo yêu cầu hiện tại, **tạm dừng phát triển Telegram**; gateway xác thực thực, lưu bền vững và đối soát MT5 vẫn là việc của phase sau khi tiếp tục nhánh này.

## Phase 4 Expected Trade Path (offline)

`TradeManager/ExpectedPath.mqh` theo dõi một trade sau fill giả lập do caller xác nhận, chỉ nhận nến đã đóng liên tục và ghi MFE/MAE theo R, bar đầu đạt 0.5R/1R/2R, giai đoạn PROVING/WORKING/MATURE và reason để review khi chậm tiến triển, invalidation hoặc chạm stop. Nếu một nến chạm stop, thứ tự intrabar không biết được nên module không tự suy ra fill/exit. Ngưỡng 3/8/15 bars trong fixture chỉ là seed nghiên cứu, không phải policy giao dịch. Xem `TradeManager/EXPECTED_PATH_OFFLINE.md` và `PHASE4_TRACEABILITY.md`.

Bộ kiểm thử offline của phần đã triển khai hiện đạt 111/111. Broker quote/cost, authoritative fill/exit, persistence/replay và MQL5 compile/runtime chưa được thực hiện; EA shell vẫn observer-only.

## Vòng đời LIMIT/STOP theo setup: cập nhật đặc tả và plan

[Đặc tả REQ-021](PENDING_ORDER_LIFECYCLE_SPEC.md) yêu cầu mỗi lệnh chờ có TTL riêng theo setup/style/symbol/session, số nến đóng chờ tối đa và điều kiện hủy sớm khi setup, risk, news hoặc premise thị trường không còn hợp lệ. Partial fill giữ vị thế đã khớp, đồng thời hủy phần còn treo khi hết hạn; risk reservation của phần treo chỉ giải phóng sau khi broker xác nhận hủy/hết hạn. Timer phải kiểm tra deadline ngay cả khi không có nến mới. Fill xuất hiện trong lúc cancel phải được reconcile và ghi risk.

[Kế hoạch triển khai](PENDING_ORDER_LIFECYCLE_PLAN.md) chia các gate từ profile và contract offline đến broker adapter, Strategy Tester và Paper. `TradeManager/PendingOrderLifecycle.mqh` đã có prototype thuần cùng fixture/oracle synthetic cho deadline, số nến chờ, guard update giữa nến, partial fill, cancel confirmation và race; xem [tài liệu ranh giới](TradeManager/PENDING_ORDER_LIFECYCLE_OFFLINE.md). Các con số TTL/closed bars cho SCALP và SWING, broker expiration capability và policy remainder sau partial fill vẫn OPEN trước Paper. Nhánh Telegram tiếp tục tạm dừng; chưa có code gửi/hủy lệnh chờ trong EA shell.

`Storage/PendingOrderCheckpoint.mqh` bổ sung hợp đồng khôi phục sau restart. Checkpoint hợp lệ chỉ giữ lại deadline, volume và risk đã ghi rồi chuyển sang `PENDING_RACE_UNKNOWN`, chặn entry mới cho tới khi đối soát active order/deal history; checksum bao gồm cả envelope. Không có serializer/file I/O, replay broker hoặc xác nhận MT5. Xem [tài liệu checkpoint offline](Storage/PENDING_ORDER_CHECKPOINT_OFFLINE.md).

`Storage/PendingOrderAudit.mqh` bổ sung contract audit cho `SEED_ACCEPTED` và các transition sau đó, gồm identity, state trước/sau, reason, volume/risk, sequence liên tục và fingerprint nối chuỗi. Checkpoint v1.1 mang audit-tail anchor; kiểm tra khớp final record sau restore vẫn chặn entry. `RECONCILE_EVIDENCE` chỉ ghi nhận evidence ID/fingerprint, không xác nhận broker đã đối soát. Chưa có JSONL append bền vững, serializer MQL hoặc replay toàn chuỗi; xem [tài liệu audit offline](Storage/PENDING_ORDER_AUDIT_OFFLINE.md).
