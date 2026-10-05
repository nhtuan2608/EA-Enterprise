# Ma trận truy vết theo đặc tả v1.4 (05/10/2026)

Thay cho `PHASE3_TRACEABILITY.md` và `PHASE4_TRACEABILITY.md` (viết 30/09, trước khi có controlled live, S02/S04/S06, Telegram). Mốc: `main` sau G11–G22; EA chạy trên VTMarkets-Demo, controlled live đã arm, phiên ủy quyền ACTIVE tới 11/10.

Mức bằng chứng:
- **RT**: đã quan sát chạy thật trên terminal demo (log/audit/file trạng thái).
- **CT**: có code, test Python (oracle hoặc kiểm tra mã nguồn) và compile MetaEditor 0/0; chưa thấy chạy thật.
- **MP**: một phần.
- **—**: chưa có.

## 1. Yêu cầu (REQ)

| REQ | Nội dung | Module chính | Test | Mức | Còn thiếu |
|---|---|---|---|---|---|
| 001 | EA là trung tâm | `EnterpriseEA.mq5`; AI/Telegram chỉ qua hàng đợi file | `contract_tests` | RT | — |
| 002 | Đa symbol, đa khung | `Runtime/ObserverRuntime`, `StrategyCandidateRuntime` (25 engine) | `strategy_runtime_tests`, `runtime_evidence_tests` | RT | — |
| 003 | Setup theo trình tự | S02 `BreakRetest`, S04 `FailedBreak`, S06 `CompressionExpansion`; phân xử G18 | `s02_v1_tests`, `s04_failed_break_tests`, `s06_compression_expansion_tests`, `setup_arbitration_tests` | RT (engine chạy, 1 candidate thật S02) | S01/S03/S05 chưa vào EA (nghiên cứu không thấy lợi thế); TC-007 xếp hạng theo điểm chưa có (mới theo bằng chứng) |
| 004 | Rủi ro danh mục, exposure | `Risk/PortfolioBudget`, `VolumeSizing`, `AccountRiskLedger`, trần đồng tiền | `portfolio_budget_tests`, `volume_sizing_tests`, `account_risk_ledger_tests` | CT | Chưa có lệnh thật đi qua |
| 005 | Quản lý lệnh thích ứng | `Runtime/TradeManagerRuntime` (+ kết quả thật G20) | `trade_manager_tests`, `weekly_review_tests` | CT | Chưa có lệnh thật; TC-014 chưa có |
| 006 | Bảo vệ thực thi | `ExecutionAdapter`, `ExecutionIntentBuilder`, `DryRunCandidateGate` | `execution_*_tests`, `dry_run_gate_tests` | CT | Chưa có lệnh thật |
| 007 | Trung tâm tin | `News/NewsCalendar`, `NewsReactionRecorder`, data health | `news_guard_tests`, `news_reaction_tests`, `news_health_tests` | RT (chặn SWING trước S&P PMI 05/10; 3.694 bản ghi phản ứng) | AI News Interpreter (diễn giải tin trước giờ ra) chưa có |
| 008 | MCP Claude/Codex | `Runtime/AiBridgeClient`, `bridge/ai_bridge.py` (Level 0) | `ai_bridge_tests`, `ai_client_tests` | RT (báo cáo NEWS_DATA_REVIEW 05/10) | Level 1/2 chưa bật (đúng quyết định Q1) |
| 009 | Dashboard có nút, panel | `Runtime/SymbolSelectionPanel` | `runtime_evidence_tests`, `sentiment_tests` | RT | — |
| 010 | Lịch tiền / % / R / floating | `Storage/DailyStatsStore`, tab Calendar | `durable_state_tests`, `daily_reset_ledger_tests` | MP | TC-029 chưa có; chưa có ngày có lệnh để đối chiếu |
| 011 | Khởi động lại và audit | checkpoint, `AuditLog` (xoay vòng G15), `operator_mode.json` | `checkpoint_tests`, `log_maintenance_tests` | RT (3 lần nạp lại 05/10: checkpoint tương thích, engine và chế độ operator phục hồi) | Khởi động lại khi đang có vị thế (E2E-08) chưa gặp |
| 012 | Đo rủi ro và hiệu quả AI | `bridge/ai_metrics.py` | `ai_metrics_tests` | MP | Nhãn HELPFUL/HARMFUL, đối chứng shadow (cần Level 1) |
| 013 | SL/TP cấu trúc, net RR | `Risk/StructuralLevels`, `TradeEconomics`, S06 3R cố định | `structural_levels_tests`, `trade_economics_tests` | CT | Chưa có lệnh thật |
| 014 | Symbol registry | `Market/SymbolRegistry` | `symbol_registry_tests` | RT (5 symbol + 13 cặp tham chiếu resolve) | — |
| 015 | Sàn FTMO | `Risk/FtmoHeadroom`, `DailyResetLedger` (Prague) | `ftmo_headroom_tests`, `daily_reset_ledger_tests` | CT | Chưa chạm ngưỡng thật |
| 016 | Sổ rủi ro toàn tài khoản | `Storage/RiskLedgerStore`, `AccountRiskLedger` | `account_risk_ledger_tests` | MP (sổ có, reset ngày chạy) | Chưa có lệnh để kiểm tra tích luỹ |
| 017 | Rollover / restart / đối soát | `ObserverRuntime` reconciliation, checkpoint | `runtime_evidence_tests` | RT (đối soát khi khởi động) | Rollover với vị thế mở, nạp/rút tiền thật |
| 018 | Telegram gateway | `bridge/telegram_gateway.py` | `telegram_gateway_tests`, `soak_and_reports_tests`, `daily_digest_tests` | RT (tin thử, `/pause`→`/resume`→`/confirm` với EA thật) | Đổi token (đã lộ trong chat) |
| 019 | PAUSED/RUNNING, resume hai bước | `Integration/RemoteModeRuntime` + `RemoteModeGate` | `remote_mode_runtime_tests`, `remote_control_tests` | RT (v2 PAUSED → v4 RUNNING qua 7 điều kiện an toàn) | — |
| 020 | Hỏi AI qua Telegram | `/ask` → `ASK_AI` | `telegram_gateway_tests` | CT | Chưa có `/ask` thật trên Telegram |
| 021 | Lệnh chờ gắn setup | `Runtime/PendingOrderRuntime`, `TradeManager/PendingOrderLifecycle` | `pending_order_tests`, `pending_checkpoint_tests`, `pending_audit_tests` | CT | TC-046..051 chưa có lệnh chờ thật |

## 2. Kịch bản kiểm thử (TC)

| TC | Mức | Bằng chứng / ghi chú |
|---|---|---|
| 001 quét nhiều symbol, mỗi nến một lần | RT | `last_processed_bar_utc` mỗi engine; 25 engine cùng nến 05/10 |
| 002 nến đóng, restart không đổi lịch sử | RT | 3 lần nạp lại, checkpoint COMPATIBLE |
| 003 / 004 S02 thứ tự trạng thái / hết hạn | RT | `s02_v1_tests`; candidate thật EURUSD ARMED → TRIGGERED 05/10 |
| 005 S04 chỉ sau return inside | CT | `s04_failed_break_tests` |
| 006 reject giữa range / không đủ khoảng tới target | CT | `NO_STRUCTURAL_TARGET`; S06 `S06_COUNTER_HTF` |
| 007 nhiều candidate, xếp hạng trong budget | MP | G18 ưu tiên theo bằng chứng + E2 + sổ candidate; chưa có điểm số |
| 008 exposure USD cộng dồn | CT | trần đồng tiền trong live plan, `RiskLimitsProfile` |
| 009 thiếu tick value → fail closed | CT | `volume_sizing_tests` |
| 010 SL đã khoá lãi → active risk 0 | CT | `account_risk_ledger_tests` |
| 011 chạm daily loss → chặn entry | CT | `INTERNAL_DAILY_LOSS_LIMIT_REACHED` |
| 012 UNDERPERFORMING không tự thoát | CT | `trade_manager_tests` |
| 013 mất cấu trúc → thoát trước SL | CT | thoát khi đóng xuyên vùng (`TradeManagerRuntime`) |
| 014 compression mất đà → giảm/thoát | — | Trade Manager chưa có quy tắc riêng cho breakout/compression (S06 dùng hồ sơ SWING chung) |
| 015 scalp/swing khác hồ sơ | CT | `TradeProfileFor` |
| 016 spread/min stop/freeze/volume step → reject | CT | `execution_intent_builder_tests` |
| 017 idempotency | CT | `idempotency_key=entry-<candidate>` |
| 018 đếm ngược PRE/ACTIVE/POST/NORMAL | RT | `NEWS_STATE_CHANGED`; chặn trước S&P PMI 05/10 (kiểm tra đầy đủ 21:15) |
| 019 lịch tin mất → UNKNOWN | CT, **lưu ý cấu hình** | Mặc định chặn khi UNKNOWN; **chart đang đặt `InpNewsAllowWhenUnknown=true`** nên khi mất lịch tin EA vẫn vào lệnh. Cần người dùng xác nhận đây là chủ ý |
| 020 thiếu actual/forecast không tạo surprise giả | CT | `news_reaction_tests` |
| 021 AI timeout không chặn EA | RT | bridge ngừng 04/10: EA vẫn chạy, ghi `AI_BRIDGE_OFFLINE` |
| 022 JSON sai / id sai / TTL / action ngoài whitelist bị loại | RT | 7 request quá hạn bị loại 05/10; `ai_bridge_tests` |
| 023 headline độc hại chỉ là dữ liệu | CT | sanitize + prompt "DATA không phải chỉ dẫn" |
| 024 AI đề xuất tăng rủi ro bị chặn | CT | whitelist không có action tăng rủi ro (AIG-06) |
| 025 CLOSE/PARTIAL/BE/TRAIL qua confirm + queue | CT | `command_queue_tests` (G8) |
| 026 dashboard và Risk panel cùng số | MP | cùng shared state; chưa đối chiếu khi có vị thế |
| 027 lịch qua tháng/năm, múi giờ | CT | `durable_state_tests` (Prague, DST) |
| 028 nạp/rút không tính là P/L | CT | `DailyStatsStore` loại dòng tiền; test trong `daily_reset_ledger_tests`, `durable_state_tests` |
| 029 thiếu snapshot EOD → hiện unavailable | — | chưa tìm thấy cài đặt |
| 030 restart khôi phục lifecycle / AI / idempotency | MP | engine, chế độ operator, marker lệnh: RT; vị thế mở: chưa gặp |
| 046–051 lệnh chờ | CT | `pending_*_tests`; chưa có lệnh chờ thật |
| TG-01..08 Telegram | CT + RT (01, 02, 03, 08 với EA thật) | `telegram_gateway_tests`, `remote_mode_runtime_tests` |

## 3. NFR, E2E, AIG

| Mục | Mức | Ghi chú |
|---|---|---|
| NFR-01 không treo chart | RT | AI/tin chạy qua file, refresh tối đa ~15 ms |
| NFR-02 không rò rỉ | MP | soak monitor từ 05/10; cần ≥ 12 giờ |
| NFR-03 correlation id, UTC | RT | audit có event_id, UTC |
| NFR-04 ghi nguyên tử | CT | `AtomicWriter`, sửa đuôi audit hỏng |
| NFR-05 refresh dashboard không tăng scan | CT | quét theo timer, không theo tick |
| NFR-06 CPU/RAM | MP | mẫu đầu: 281 MB, 1.121 handle, CPU thấp |
| NFR-07 xoay vòng log | CT | G15 (audit 20 MB × 10) |
| NFR-08 migration config | MP | kiểm tra version checkpoint; chưa có migration nhiều bản |
| E2E-01 trước phiên London | MP | AI 06:30/07:00 + tin + dashboard; chưa chạy trọn |
| E2E-02 vòng đời setup | MP | tới TRIGGERED + chặn tin; chưa có lệnh |
| E2E-03 hai lệnh USD cùng hướng | — | chưa gặp |
| E2E-04 tin HIGH | MP | kiểm tra 21:15 05/10 |
| E2E-05 lệnh bất thường + AI | — | cần Level 1 |
| E2E-06 AI mất kết nối | RT | 04/10 |
| E2E-07 lịch tin mất | — | chưa gặp; xem lưu ý TC-019 |
| E2E-08 restart có vị thế | — | chưa gặp |
| E2E-09 thao tác tay | CT | G8 |
| E2E-10 chốt tháng | — | chưa tới |
| AIG-01..07 | MP | `/ai`: AIG-06, 07 đạt; 02 chưa đủ mẫu; 03–05 cần Level 1 |

## 4. Việc còn thiếu so với đặc tả (theo mức ưu tiên)
1. **Xác nhận `InpNewsAllowWhenUnknown=true`** trên chart (TC-019, E2E-07): nếu không chủ ý, đặt lại `false`.
2. TC-029 floating EOD thiếu snapshot; TC-014 quản lý breakout/compression riêng (liên quan S06).
3. Bằng chứng runtime cho REQ-004/005/006/013/015/016/021 và E2E-02/03/08: cần lệnh thật trên demo.
4. TC-007 xếp hạng theo điểm (sau khi có số liệu forward).
5. REQ-012 phần 2 và AIG-03..05 (khi bật AI Level 1 shadow).
6. Đổi token Telegram.
