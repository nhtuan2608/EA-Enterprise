# Ma trận truy vết theo đặc tả v1.4, cập nhật 07/10/2026

Cập nhật `2026-10-05-traceability-v1-4.md` cho mọi thứ thêm sau 05/10 (G23–G59 trong `plans/2026-10-04-roadmap-after-merge.md`). Bản 05/10 vẫn là gốc cho các dòng không đổi; bản này ghi lại đầy đủ các dòng đã đổi và dòng mới. Căn cứ: code `main` (`89ae674`), tối thiểu 776 test Python đạt (07/10, sau G60; G61 thêm test), compile MetaEditor 0/0 ở lần deploy gần nhất (G60/G61 deploy 07/10 16:46 UTC), và trạng thái terminal demo (VTMarkets-Demo) ngày 07/10.

Mức bằng chứng (giữ nguyên định nghĩa 05/10):
- **RT**: đã quan sát chạy thật trên terminal demo (log, audit, file trạng thái).
- **CT**: có code, test Python (oracle hoặc kiểm tra mã nguồn) và compile; chưa thấy chạy thật.
- **MP**: một phần.
- **—**: chưa có.
- **NC** (mới): chỉ có ở nghiên cứu (`research/`), chưa nằm trong EA. Không tính là đã đáp ứng yêu cầu.

## 0. Trạng thái thật trên terminal demo (07/10)

| Mục | Giá trị | Nguồn |
|---|---|---|
| Controlled live | đã arm (`InpExecutionEnabled=true`, `InpLiveTradeArmed=true`), phiên **ACTIVE** tới 14/10/2026 11:57 UTC | `live_session.json`, `current/live_status.json` |
| Chính sách (trần phiên) | **CUSTOM**: ngày 5%, tổng 10%, phiên ký trần 1,5%/lệnh (`InpAccountPhase=EVALUATION`) | `policy_settings.json`, `live_session.json` |
| Rủi ro hiệu lực của EA | mỗi lệnh **0,5%** (người dùng đã hạ `InpEvalRiskPercent`), mở 2%, ngày 2%, tuần 4%; theo setup S04 0,325%, S06B 0,5%, T2 0,17% | khối `risk` của `current/live_status.json` (G60, RT từ 07/10 16:47 UTC) |
| Chế độ setup | S04 **LIVE**; S06B **LIVE** (chuyển 07/10); S02, S06, SCALP (trần), T2 **SHADOW** | `live_status.json` (khối `modes`) |
| T2 | LIVE-được trên `XAUUSD,BTCUSD` (`InpT2LiveSymbols`), chạy SHADOW; ngoài ra `XAGUSD,ETHUSD,USOUSD` (`InpT2OnlySymbols`, chỉ có engine T2) | `EnterpriseEA.mq5`, G49 |
| Lệnh thật | **chưa có lệnh nào** từ khi arm (không có `logs/trades.jsonl`, không có sự kiện lệnh trong audit) | G59 mục B |
| Test | ≥ 776 test Python đạt (07/10) | G60, G61 |

Hệ quả: mọi yêu cầu thuộc đường vào lệnh thật vẫn **CT**, kể cả khi S04 và S06B đang LIVE. LIVE nghĩa là đường vào lệnh đã mở, không phải là đã có lệnh.

Lệch giữa mặc định trong code và profile chart (cấu hình, không phải lỗi mã; khối `news` của `live_status.json` cho thấy giá trị thật): code mặc định `InpS06BMode=S06B_LIVE` (G60); danh sách bỏ qua mặc định trong code không còn `ISM Non-Manufacturing` (G57/G60) nhưng chart vẫn còn tên này; chart vẫn chạy `InpNewsAllowWhenUnknown=true` (code mặc định `false`). Hai điểm cuối chờ người dùng quyết (mục 5).

## 1. Thay đổi so với 05/10

Chuyển mức (đã đối chiếu với bản 05/10):

| Mục | 05/10 | 07/10 | Lý do |
|---|---|---|---|
| REQ-003 Setup Engine | RT (S02, S04, S06) | RT, mở rộng thêm **S06B** (SHADOW rồi LIVE 07/10) và **T2** (SHADOW) | G26, G29, G39–G41, G49 |
| REQ-004 Rủi ro danh mục | CT | CT (thêm trọng số rủi ro theo setup, rủi ro đánh giá, CUSTOM) | G34, G42, G44 |
| REQ-005 Trade Manager | CT | CT (thêm hồ sơ POSITION cho T2, quản lý lệnh bồi) | G31, G40, G44 |
| REQ-007 Trung tâm tin | RT | RT, nhưng **dữ liệu giờ tin mùa đông ghi sai 1 giờ đã sửa** (chỉ bộ ghi phản ứng, News Guard live không bị) | G54 |
| REQ-015 FTMO | CT | CT, thêm mode CUSTOM dùng chung bộ luật `PolicyRules` | G34 |
| REQ-018 Telegram | RT | RT cho lệnh điều khiển; thêm `/edge`, `/week`, `/today`, `/soak`, `/ai`, `/status` đọc `live_status.json` (CT) | G37, G40, G22 |
| REQ-019 PAUSED/RUNNING | RT | RT, không đổi | — |
| Chuỗi tính năng mới không có REQ riêng | — | bảng 1b (X-01…X-17) | G29–G59 |
| TC-014 | — | — (vẫn thiếu; T2 có hồ sơ POSITION riêng nhưng đó là rule khác) | G59 mục C |
| TC-019 / E2E-07 | CT, lưu ý cấu hình | CT, lưu ý cấu hình **vẫn mở** (A3) | G59 |
| TC-029 | — | CT | G60: `Storage/DailyFloatingStore.mqh`, `current/daily_floating.json`, ngày chi tiết trong lịch hiện "floating EOD …/floating now …/floating EOD unavailable"; test `daily_floating_tc029_tests` |
| TC-007 | MP | MP | G33: điểm không dự đoán được, giữ ưu tiên theo bằng chứng |

Không có dòng nào đi lên RT mới vì lệnh thật. Các dòng đi lên hoặc mới có bằng chứng chạy thật (X-16 cũng RT): `live_status.json` ghi mỗi timer (RT, X-01); xuất lịch kinh tế 2010–2026 chạy trên EA thật (RT, X-11); phiên live CUSTOM ký lại 07/10 11:57 UTC (RT, X-09).

## 1b. Hạng mục thêm sau 05/10 (không có REQ riêng trong v1.4)

| ID | Nội dung | Module trong EA / công cụ | Test | Mức | Còn thiếu / ghi chú |
|---|---|---|---|---|---|
| X-01 | Trạng thái live cho người ngoài EA (G40, G46) | `current/live_status.json` ghi mỗi timer, kèm chế độ từng engine và lý do strategy runtime; Telegram `/status` đọc file này (`bridge/telegram_gateway.py`) | `t2_live_g40_tests` (ghi theo timer, không theo tick; nêu lý do chặn; file cũ/thiếu) | RT (file có và đọc được trên terminal 07/10) | Script `tools/verify_live_readiness.ps1` đã sửa ở G60 (X-16) |
| X-02 | **S06B**: hộp 24 nến, vào ngay ở nến phá, không lọc HTF, 3R (G26) | `Setups/CompressionExpansion.mqh` (biến thể ngay), `Runtime/StrategyCandidateRuntime.mqh`; input `InpS06BMode` | `setup_modes_g26_tests` (slot, checkpoint, "release triggers at once", mode theo engine), `s06_compression_expansion_tests` | engine RT (SHADOW rồi LIVE 07/10; chưa có tín hiệu nào được ghi nhận từ khi LIVE); đường vào lệnh CT | Chưa có lệnh thật. G58: ở 1,5%/lệnh DD p90 13–19% > sàn 10% (xem mục 4, ưu tiên 1) |
| X-03 | **Dòng USD** làm bộ lọc S06B (G27, G29) | `Market/UsdFlow.mqh` (EURUSD, GBPUSD, USDJPY so với EMA50 H1, nến đã đóng); `InpS06BRequireUsdFlow=true` chặn `S06B_COUNTER_USD`, `S06B_USD_FLOW_UNKNOWN`; ghi `usd_flow`/`usd_alignment` vào log shadow và `logs/candidates.jsonl` | `usd_flow_pyramid_g29_tests` (khớp chỉ số nghiên cứu, dấu alignment, cổng LIVE, không giao dịch) | CT | Chưa có lệnh S06B thật để thấy cổng chặn/cho qua |
| X-04 | **Bồi lệnh S06B** (G28, G29, G31) | `Integration/S06BPyramidRuntime.mqh`; `InpS06BPyramidLive=false` (TẮT); bồi 1 lần ở +1R, dừng lỗ = hòa vốn của lệnh đầu, đi qua đủ cổng như lệnh thường; Trade Manager không hòa vốn lại/không chốt một phần/trail từ 2R | `s06b_pyramid_g31_tests` (mặc định tắt, thứ tự sau lượt vào lệnh, không chạy khi PAUSED/recovery, cùng đường rủi ro, `add_candidate` lưu bền) , `usd_flow_pyramid_g29_tests` (mô phỏng ảo: `research/g10/pyramid.py`) | CT | TẮT, chỉ bật sau khi shadow khớp. Bồi lệnh T2: `InpT2PyramidLive=false`, test `g4_in_ea_g44_tests` (`test_t2_add`), cũng chưa bật |
| X-05 | **T2 Donchian POSITION** (G38–G41) | `Setups/DonchianTrend.mqh` (Donchian 60 trên H4, phía EMA200 D1); quét trong `StrategyCandidateRuntime.mqh`; input `InpT2Mode` (OFF/SHADOW/LIVE), `InpT2LiveSymbols=XAUUSD,BTCUSD`; log `t2_shadow.jsonl` (`ControlledLiveRuntime.mqh`); Trade Manager hồ sơ **POSITION** (trail 3 ATR, không hòa vốn/chốt một phần/thoát cấu trúc), TP sàn 20R, theo luật SWING cho tin/sentiment/phiên/chi phí (`Runtime/TradeManagerRuntime.mqh`); cổng dry-run nhận T2 | `t2_donchian_tests` (mirror research), `t2_live_g40_tests` (hồ sơ POSITION, trail chỉ siết sau hòa vốn, SWING/SCALP không đổi, T2 không có thoát cấu trúc, mode theo symbol), `t2_oracle.py` | engine RT (SHADOW, 0 tín hiệu); LIVE CT | Mirror khớp nghiên cứu 99,8–100% trên dữ liệu thật (G39). Chưa có lệnh T2 thật nào; LIVE chỉ XAU/BTC (G41) |
| X-06 | **Lọc nến đà T2** (G44) | `InpT2MomentumFilter=true` trong `StrategyCandidateRuntime` | `g4_in_ea_g44_tests` (`test_momentum_close`, `test_filter_only_removes_signals`, `test_engine_filter`; khớp nghiên cứu ≥ 95% trên XAUUSD, EURUSD) | CT | Chỉ tính candidate T2 từ lúc deploy G44 (06/10 16:36 UTC) để không trộn tín hiệu chưa lọc |
| X-07 | **T2-only symbols** (G49) | `InpT2OnlySymbols=XAGUSD,ETHUSD,USOUSD`: chỉ có engine T2, thêm vào danh sách chọn của panel khi T2 không OFF; T2 LIVE vẫn chỉ XAU/BTC nên 3 tài sản mới ghi SHADOW | `t2_only_symbols_g49_tests` | CT; chạy thật từ 07/10 13:09 UTC (người dùng chọn trong panel, theo G57), chưa có tín hiệu | Điều kiện LIVE đăng ký trước: khớp tín hiệu ≥ 95% và ≥ 20 lệnh ảo forward/tài sản không phá monitor. Dữ liệu D1: 679/949/679 nến, đủ EMA200 |
| X-08 | **Trọng số rủi ro theo setup** (G43, G44) | `Risk/RiskLimitsProfile.mqh` (`EEA_SetupRiskWeight`), input `InpRiskWeightS04=0.65`, `InpRiskWeightT2=0.34` (S06B 1,00); chỉ giảm; dùng ở `Integration/ControlledLiveRuntime.mqh` và `S06BPyramidRuntime.mqh` | `g4_in_ea_g44_tests` (`test_risk_weights_only_lower_the_risk`, `test_weights_keep_the_research_ratios`, `test_inputs_and_defaults`) | CT | Tỉ lệ trọng số lấy từ nghiên cứu G43; chưa có lệnh để xác nhận lot thật |
| X-09 | **Rủi ro vòng thi và mode CUSTOM** (G34, G42) | `Risk/PolicyRules.mqh` (bộ luật chung), `Risk/RiskLimitsProfile.mqh`; input `InpAccountPhase` (EVALUATION/FUNDED), `InpEvalRiskPercent` (mặc định 1,5, trần 1,5), `InpCustomDailyLossPercent`, `InpCustomOverallLossPercent`, `InpCustomTrailingFloor`, `InpCustomDailyFromEquity`; ngày/tuần/mở theo 4×/4×/8×, chặn ở 80% giới hạn policy; phiên live ký cả số CUSTOM (`Runtime/LiveSessionAuthorization.mqh`) | `custom_policy_g34_tests` (sàn cố định/trượt, mốc equity/balance, thiếu mẫu equity thì fail closed, phiên ký số CUSTOM), `eval_risk_g42_tests`, `live_session_tests` | phiên CUSTOM ACTIVE: RT (07/10); chặn theo ngưỡng thật: CT | Chưa chạm ngưỡng thật. Rủi ro hiệu lực 1,5%/lệnh lớn hơn mức G58 an toàn cho sàn 10% (xem mục 4) |
| X-10 | **News Guard: danh sách bỏ qua và sửa giờ lịch** (G30, G31, G54, G57) | `InpNewsIgnoreKeywords` (mặc định 10 tên tin yếu, `EnterpriseEA.mq5`) vào `News/NewsCalendar.mqh`; `EEA_NewsCalendarUtc` = giờ lịch − độ lệch hôm nay; bộ ghi phản ứng đánh dấu `time_rule=calendar_now_offset` (`News/NewsReactionRecorder.mqh`), backfill v1.2.0 | `news_guard_tests` (`test_ignore_list_is_empty_by_default_and_case_insensitive`: khi cấu hình rỗng thì không bỏ qua; kiểm tra khớp không phân biệt hoa thường), `calendar_clock_g54_tests` (NFP mùa đông/hè, dòng cũ đo lại), `news_reaction_tests`, `s06b_pyramid_g31_tests` (mặc định từ G30) | CT; dữ liệu đã sửa: RT (EA xuất lịch format 2 và ghi lùi lại) | G57 (`research/long/news_keywords_check.py`): **ISM Non-Manufacturing** ×1,46 vẫn trong danh sách bỏ qua, đề xuất bỏ, **chưa được người dùng xác nhận**. Giá trị nằm trong profile chart, đổi bằng hộp input |
| X-11 | **Xuất lịch kinh tế MT5 từ 2010** (G53) | `Runtime/CalendarExport.mqh` (chỉ đọc), input `InpResearchExportCalendar=true`, `research/calendar/calendar_<NĂM>.csv`, trạng thái `calendar_export` trong `live_status.json`, format 2 có `time_calendar` | `calendar_export_g53_tests`, `calendar_clock_g54_tests` | RT (EA xuất 2010–2026 trong khoảng 9 phút ngày 07/10; kiểm đồng hồ NFP đạt 100% sau sửa G54) | Phục vụ nghiên cứu, không điều khiển giao dịch |
| X-12 | **Monitor lợi thế** (G37, G46) | `research/g10/edge_monitor.py` (CUSUM giảm, sụt giảm, R trung bình; các luồng S04, S06B, T2 có/không XAU+BTC, có/không bồi), `research/long/edge_calibrate.py`; `current/edge_monitor.json`; Telegram `/edge` và kiểm tra hằng ngày chỉ nhắn khi xấu hơn | `edge_monitor_tests` (mọi luồng đều hiệu chỉnh, luồng dùng tham số có sẵn, T2 trước G44 không tính, tham số có lọc khác nghiên cứu chưa lọc), `telegram_gateway_tests` (tắt `notify.edge` trong harness) | CT (công cụ ngoài EA; chưa có lệnh thật để nó theo dõi) | Theo dõi chỉ trên lệnh ảo + lệnh thật; hiệu chỉnh XAU/BTC lạc quan vì chọn sau (G46) |
| X-13 | **Khớp tín hiệu EA ↔ nghiên cứu** (G48, G48b, G49) | `research/g10/signal_parity.py` (so `logs/candidates.jsonl` và sổ shadow với bộ sinh tín hiệu nghiên cứu: khớp / EA bỏ sót / EA thừa / lúc EA tắt; `--live` lấy nến trực tiếp từ MT5; "nhịp tim" khi chưa có tín hiệu; mọi symbol EA chọn; symbol T2-only tính từ `SYMBOL_START`); replay lịch sử bằng `Runtime/SetupReplay.mqh` (`setup_replay.jsonl`) | `signal_parity_g48_tests` | RT (chạy 07/10 trên dữ liệu thật: S04/S06B/T2 EA 0, nghiên cứu 0 từ lúc theo dõi, khớp); replay S04 SWING 30/30, S02 SWING 31/31, S02 SCALP 497/497, S04 SCALP 352/353 | Lệch 1/353 (GBPUSD 04/02 13:55) chưa chứng minh nguyên nhân, candidate bị loại `RR_TOO_LOW`, không có lệnh. Vì chưa có tín hiệu forward, khả năng bắt lệch thật chưa được thử |
| X-14 | **Đánh giá tuần** (G20, G50) | `research/g10/weekly_review.py` (luôn hiện S04_SWING/S06B_SWING/T2_POSITION kèm chế độ từ `live_status.json`; mục monitor lợi thế, soak, khớp tín hiệu, AI); Telegram `/week`; `TRADE_EXITED` + `logs/trades.jsonl` do Trade Manager ghi | `weekly_review_tests`, `trade_manager_tests` | CT (công cụ chạy được; phần lệnh thật rỗng vì chưa có lệnh) | Dùng cho G5 (10–11/10) |
| X-16 | **Tự kiểm cấu hình hiệu lực** (G60) | `current/live_status.json` có thêm khối `risk` (rủi ro hiệu lực mỗi lệnh/mở/ngày/tuần/theo setup) và `news` (cấu hình tin hiệu lực), kiểm được không cần profile chart; sửa câu log khởi tạo; `tools/verify_live_readiness.ps1` đọc `live_session`/`live_status` (observer `new_entries_blocked` là chặn vào lệnh theo thiết kế) | `live_status_g60_tests` | RT (khối mới có từ 07/10 16:47 UTC; script chạy ra READY_FOR_MANUAL_REVIEW 07/10) | Bản 07/10 trước đó ghi script báo sai và câu log gây hiểu nhầm: đã sửa |
| X-17 | **Monitor lợi thế có luồng S06B thật** (G61) | `research/g10/edge_monitor.py` thêm các luồng S06B từ lệnh/candidate thật | `edge_monitor_tests` | CT | Chưa có lệnh S06B thật để luồng có dữ liệu |
| X-15 | **Nghiên cứu chưa vào EA** | S01/S03/S05 (không thấy lợi thế); SCALP M5 mọi setup âm (G55, G58); G38 T3–T5; G45 vùng/OB/FVG; G47 Fibonacci OTE (4/5 tiêu chí, ngoài mẫu âm); G56 SW1/SC1 (walk-forward âm); G35 H4; G36 8 cặp mới; G33 điểm dự đoán | `long_history_tests`, `factor_atlas_g56_tests`, `factor_setups_g56_tests` | **NC** | Không có gì trong số này đang chạy trong EA, ngoài SHADOW của S02/S06/SCALP |

## 2. Yêu cầu (REQ)

Chỉ ghi lại các dòng có thay đổi so với 05/10 hoặc có thêm bằng chứng. Các dòng không nhắc: không đổi so với bản 05/10.

| REQ | Nội dung | Module chính (có đổi) | Test | Mức | Còn thiếu |
|---|---|---|---|---|---|
| 003 | Setup theo trình tự | S02 `Setups/BreakRetest.mqh`, S04 `FailedBreak.mqh`, S06/S06B `CompressionExpansion.mqh`, T2 `DonchianTrend.mqh`; phân xử `Integration/SetupArbitration.mqh` (ưu tiên S06 → S04 → S02, SWING trước SCALP, G18); sổ `CandidateLedger.mqh` | `s02_v1_tests`, `s04_failed_break_tests`, `s06_compression_expansion_tests`, `t2_donchian_tests`, `setup_arbitration_tests`, `candidate_ledger_tests`, `setup_modes_g26_tests` | RT (engine S02/S04/S06/S06B/T2 chạy; 1 candidate thật S02 05/10); đường LIVE S04, S06B: CT | S01/S03/S05 chỉ prototype, nghiên cứu không thấy lợi thế (G23, G56). S02 không đạt (G23, G55): giữ SHADOW. **S04 chỉ THEO DÕI** (+0,05R gộp, mỏng dần, G55) mà đang LIVE |
| 004 | Rủi ro danh mục, exposure | `Risk/PortfolioBudget`, `VolumeSizing`, `AccountRiskLedger`, `RiskLimitsProfile` (trọng số setup G44, rủi ro đánh giá G42), `PolicyRules` (CUSTOM G34) | `portfolio_budget_tests`, `volume_sizing_tests`, `account_risk_ledger_tests`, `g4_in_ea_g44_tests`, `eval_risk_g42_tests`, `custom_policy_g34_tests` | CT | Chưa có lệnh thật đi qua; rủi ro 1,5%/lệnh vượt mức an toàn của G58 cho sàn 10% |
| 005 | Quản lý lệnh thích ứng | `Runtime/TradeManagerRuntime.mqh` (SWING, SCALP, **POSITION** cho T2; lệnh bồi theo luật nghiên cứu) | `trade_manager_tests`, `t2_live_g40_tests`, `s06b_pyramid_g31_tests`, `weekly_review_tests` | CT | Chưa có lệnh thật; TC-014 chưa có |
| 006 | Bảo vệ thực thi | `Runtime/ExecutionAdapter`, `ExecutionGate`, `ExecutionIntentBuilder`, `Integration/DryRunCandidateGate` (nhận T2) | `execution_*_tests`, `dry_run_gate_tests`, `t2_live_g40_tests` | CT | Chưa có lệnh thật |
| 007 | Trung tâm tin | `News/NewsCalendar` (+ danh sách bỏ qua), `NewsReactionRecorder` (sửa giờ G54), `NewsState` | `news_guard_tests`, `news_reaction_tests`, `news_health_tests`, `calendar_clock_g54_tests` | RT | AI News Interpreter chưa có; xác nhận bỏ "ISM Non-Manufacturing" (G57) |
| 013 | SL/TP cấu trúc, net RR | `Risk/StructuralLevels`, `TradeEconomics`; S06/S06B 3R cố định; T2 TP sàn 20R + trail ATR | `structural_levels_tests`, `trade_economics_tests`, `t2_live_g40_tests` | CT | Chưa có lệnh thật. G33: siết/nới dừng lỗ không tốt hơn dừng cấu trúc hiện tại |
| 015 | Sàn FTMO / policy | `Risk/FtmoHeadroom`, `DailyResetLedger` (Prague), `PolicyRules` (CUSTOM), `Runtime/LiveSessionAuthorization` | `ftmo_headroom_tests`, `daily_reset_ledger_tests`, `custom_policy_g34_tests`, `live_session_tests` | CT (phiên CUSTOM ACTIVE: RT) | Chưa chạm ngưỡng thật. G32: phiên ký 1-Step chặn mọi lệnh khi policy đã là 2-Step (`LIVE_SESSION_POLICY_CHANGED`), xử lý bằng ký lại |
| 016 | Sổ rủi ro toàn tài khoản | `Storage/RiskLedgerStore`, `AccountRiskLedger` (mẫu equity lúc reset cho sàn ngày CUSTOM) | `account_risk_ledger_tests`, `custom_policy_g34_tests` | MP | Chưa có lệnh để kiểm tra tích luỹ |
| 018 | Telegram gateway | `bridge/telegram_gateway.py`: `/status` (đọc `live_status.json`), `/trades`, `/soak`, `/ai`, `/today`, `/week`, `/edge`, `/ask`, `/pause`, `/resume`, `/confirm`; `bridge/supervisor.py` | `telegram_gateway_tests`, `edge_monitor_tests`, `t2_live_g40_tests`, `daily_digest_tests`, `soak_and_reports_tests`, `supervisor_tests` | RT (điều khiển PAUSED/RUNNING); lệnh báo cáo mới: CT | Đổi token (đã lộ trong chat 05/10); chưa có `/ask` thật |
| 021 | Lệnh chờ gắn setup | `PendingOrderRuntime` | `pending_*_tests` | CT | Sửa SL/TP lệnh chờ bị từ chối an toàn (`PENDING_RUNTIME_NOT_IMPLEMENTED`), đúng phạm vi đã ghi |

Các REQ khác (001, 002, 008, 009, 010, 011, 012, 014, 017, 019, 020): giữ nguyên bản 05/10. Chú ý REQ-002: số engine tăng vì S06B và T2 (kể cả 3 symbol T2-only), số cụ thể đọc ở `current/live_status.json`, chưa kiểm lại trong báo cáo này.

## 3. Kịch bản kiểm thử (TC)

Chỉ các dòng đổi hoặc mới. Dòng không nhắc giữ nguyên bản 05/10.

| TC | Mức | Bằng chứng / ghi chú |
|---|---|---|
| 007 nhiều candidate, xếp hạng | MP | G33: điểm logistic/LightGBM không thắng bỏ ngẫu nhiên; giữ ưu tiên theo bằng chứng (`setup_arbitration_tests`) |
| 014 quản lý riêng breakout/compression | — | S06B dùng SWING + bồi (G28/G31); T2 có hồ sơ POSITION, nhưng không phải rule cho compression |
| 018 đếm ngược PRE/ACTIVE/POST/NORMAL | RT | như 05/10 |
| 019 lịch tin mất → UNKNOWN | CT, **lưu ý cấu hình chưa xác nhận** | code mặc định chặn khi UNKNOWN; chart đang `InpNewsAllowWhenUnknown=true` (G59 A3) |
| 020 thiếu actual/forecast không tạo surprise giả | CT | như 05/10; G54: giờ tin mùa đông trong `news_reactions.jsonl` đã sai 1 giờ trước sửa, đã ghi lại |
| S06B chỉ vào khi cùng dòng USD | CT | `usd_flow_pyramid_g29_tests::test_s06b_live_gate_and_logs` |
| Bồi lệnh S06B một lần, mỗi lệnh chỉ một add, qua đủ cổng | CT | `s06b_pyramid_g31_tests` |
| Hồ sơ POSITION: trail chỉ siết, không hòa vốn lại | CT | `t2_live_g40_tests::test_trail_tightens_only_past_break_even` |
| T2 chỉ LIVE trên symbol trong `InpT2LiveSymbols`, còn lại SHADOW | CT | `t2_live_g40_tests::test_engine_mode_caps_unlisted_symbols`, `t2_only_symbols_g49_tests` |
| Trọng số rủi ro chỉ giảm | CT | `g4_in_ea_g44_tests::test_risk_weights_only_lower_the_risk` |
| Rủi ro vòng thi bị chặn ở trần 1,5% và 80% giới hạn policy | CT | `eval_risk_g42_tests` |
| CUSTOM: sàn ngày từ equity lúc reset, thiếu mẫu thì fail closed | CT | `custom_policy_g34_tests` |
| Khớp tín hiệu EA ↔ nghiên cứu | RT (0 tín hiệu cả hai phía) | `signal_parity_g48_tests`, chạy `signal_parity.py --live` 07/10 |
| 029 thiếu snapshot EOD → "unavailable" | CT | G60: `Storage/DailyFloatingStore.mqh`, `current/daily_floating.json`, `daily_floating_tc029_tests`; chưa có ngày có lệnh để thấy số thật |
| 046–051 lệnh chờ | CT | vẫn chưa có lệnh chờ thật |
| TG-01..08 Telegram | CT + RT (01, 02, 03, 08) | như 05/10 |

## 4. NFR, E2E, AIG

| Mục | Mức | Ghi chú |
|---|---|---|
| NFR-01 không treo chart | RT | `live_status.json` ghi theo timer, không theo tick (`t2_live_g40_tests`) |
| NFR-02 không rò rỉ | MP | `bridge/soak_monitor.py` từ 05/10; kết luận ở buổi G5 |
| NFR-07 xoay vòng log | CT | G15; `logs/candidates.jsonl`, `t2_shadow.jsonl`, `news_reactions.jsonl` là dữ liệu nên không xoay |
| NFR-08 migration config | MP | các input mới (G26–G53) đều chỉ thêm; checkpoint có `test_config_identity` (`setup_modes_g26_tests`) |
| E2E-02 vòng đời setup | MP | S02 tới TRIGGERED + chặn tin; S04/S06B/T2 chưa có tín hiệu nào đi tới lệnh |
| E2E-03 hai lệnh USD cùng hướng | — | chưa gặp |
| E2E-08 restart có vị thế | — | chưa gặp |
| E2E-10 chốt tháng | — | chưa tới |
| Các mục còn lại | như 05/10 | |

Chưa có mục nào lên RT nhờ lệnh thật.

## 5. Việc còn thiếu so với đặc tả và quyết định đang chờ (theo mức ưu tiên)

1. **Rủi ro mỗi lệnh (G59 A1)**: G58 cho DD p90 (xáo tháng) 13–19% ở 1,5%, 8,5–9,7% ở 0,75%, 4,4–6,5% ở 0,5% so với sàn tổng 10%. EA hiện đã chạy 0,5%/lệnh (khối `risk` của `live_status.json`); phiên vẫn ký trần 1,5%. Còn lại là xác nhận 0,5% là chủ ý và có giữ trần phiên 1,5% hay ký lại thấp hơn.
2. **Xác nhận `InpNewsAllowWhenUnknown=true` trên chart (TC-019, E2E-07)**: nếu không chủ ý, đặt `false`. Còn mở (khối `news` của `live_status.json`).
3. **Bỏ "ISM Non-Manufacturing" khỏi `InpNewsIgnoreKeywords` trên chart (G57)**: mặc định trong code đã bỏ, profile chart chưa; đổi trong hộp input (F7), sau đó kiểm lại qua khối `news`.
4. **Chưa có lệnh thật (G59 B)**: chờ tín hiệu S04/S06B, hoặc một phép thử đầu-cuối có kiểm soát trên demo (một lệnh, khối lượng tối thiểu, qua đúng đường rủi ro). Cần người dùng đồng ý. Đây là điều kiện để nâng CT lên RT cho REQ-004/005/006/013/015/016/021, TC-046..051 và E2E-02/03/08.
5. **S04 đang LIVE nhưng bảng điểm G55 xếp THEO DÕI**; S06B lọc USD đạt TIN CẬY. Đề xuất G58: V2 (S04 + S06B), sau đó V3 (thêm T2 XAU/BTC LIVE) khi khớp tín hiệu forward có tín hiệu đầu tiên. T2 LIVE trên XAG/ETH/USO cần khớp ≥ 95% và ≥ 20 lệnh ảo/tài sản.
6. **TC-014** (quản lý riêng cho breakout/compression): ưu tiên thấp.
7. **TC-007** (xếp hạng candidate theo điểm): không làm, G33 cho thấy không có tín hiệu điểm dự đoán được.
8. **REQ-007 AI News Interpreter**; **REQ-012 phần 2, AIG-03..05**: cần AI Level 1 shadow.
9. **Đổi token Telegram** (đã lộ trong chat 05/10): người dùng `/revoke` rồi đặt lại biến môi trường.
10. Lỗi nhỏ không ảnh hưởng giao dịch: lệch replay S04 SCALP 1/353 (G59 mục E). Hai mục khác của G59 mục E đã xử lý ở G60 (X-16).
11. Điều kiện đo lại đăng ký trước: G51/G52 (T2 trước tin HIGH) khi có ≥ 100 lệnh T2; hiện BE giữ nguyên (G53b trên 957 lệnh nghiên cứu: trail 1,5 ATR không vượt BE theo tiêu chí).
