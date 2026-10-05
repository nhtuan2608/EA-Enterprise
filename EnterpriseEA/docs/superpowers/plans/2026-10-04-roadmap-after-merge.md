# Lộ trình sau merge (04/10/2026)

Mốc: `main` đã có `9d0b9ea` (merge `feature/ui-redesign-v2`). Terminal demo chạy `fc4ec26`; phiên ủy quyền 7 ngày đang ACTIVE; tuần chạy thử S02 bắt đầu từ thứ Hai 05/10.

Cập nhật 05/10: `main` = `107b8db` (merge G7–G10), đã push GitHub. 469 test Python đạt, compile 0/0. Terminal demo (VTMarkets-Demo) chạy bản `c3caba0`; file `.ex5` trên đĩa đã là `main` (chỉ khác phần xuất nghiên cứu chạy tiếp), có hiệu lực khi gắn lại EA. Phiên ủy quyền ACTIVE tới 11/10 09:34 (giờ VN).

## 1. Hiện trạng theo đặc tả v1.4

| Nhóm | Trạng thái |
|---|---|
| REQ-001/002/004/006/009/010/011, REQ-013–017 | Xong (observer, risk kernel O-04 / FTMO, execution gate, dashboard, calendar, restart, ledger) |
| REQ-003 Setup Engine | 1/6 họ setup: **S02 Break Retest v1**. Còn S01 Asian Range Break, S03 PDH/PDL Break, S04 Failed Break, S05 Trend Pullback, S06 Compression Expansion. Đặc tả mục S2 ưu tiên **S04** ngay sau S02 để kiểm tra hai chuỗi đối lập |
| REQ-005 Trade Manager | Code xong (v1). Chờ lệnh thật để kiểm chứng |
| REQ-021 Lệnh chờ | Code xong. Chờ lệnh thật (TC-046..051) |
| REQ-007 News | News Guard đỏ/vàng, bộ ghi phản ứng, gộp cụm: xong. Chưa kiểm chứng trên tin thật; AI News Interpreter chưa có |
| REQ-008 / REQ-012 AI | Đã có thiết kế (`2026-10-04-ai-bridge-and-news-review-design.md`); chưa code |
| Đặc tả 9.2 Thao tác tay trên lệnh | Chưa có; tab Trades đang chỉ để xem |
| REQ-018–020 Telegram | Chưa có |
| Kiểm chứng S02 (bước 6) | Forward 1 tuần đang chạy; Strategy Tester chưa chạy |

## 2. Thứ tự triển khai

| # | Hạng mục | Vì sao ở vị trí này | Ra kết quả |
|---|---|---|---|
| P1 | **Replay News Guard trên tin và giá từ 01/01/2026** | Kiểm chứng News Guard bằng dữ liệu lịch sử, không phải chờ tin thật | Mỗi bản ghi phản ứng có thêm đánh giá "News Guard có che được nhịp biến động không"; có thống kê theo cụm tin |
| P1b | **Market sentiment từ đường giá và cặp chéo** (`2026-10-04-market-sentiment-design.md`) | Người dùng yêu cầu dùng cho thực thi; chỉ giảm rủi ro, không tăng | Sức mạnh 8 đồng tiền, risk regime, điểm xác nhận cho từng lệnh, hệ số rủi ro hoặc chặn SWING |
| P2 | **Tự động kiểm tra số liệu tin** (AI design mục 7) | Chạy được ngay, không cần AI; bắt lỗi dữ liệu trước khi AI đọc | `news_data_health.json` + dòng Data health trên tab News |
| P3 | **AI Bridge v1, Level 0** | Tự động hóa việc đọc số liệu mà người dùng đang làm tay | Báo cáo AI hằng ngày, giải thích từng cụm tin, chẩn đoán EA, nút ASK AI |
| P4 | **Command queue + thao tác tay** CLOSE / PARTIAL / BE / TRAIL (đặc tả 9.2) | Cần trước khi có nhiều lệnh thật; cũng là nền cho Telegram và AI Level 2 | Nút trên tab Trades, có xác nhận, đi qua cùng các cổng kiểm tra |
| P5 | **S04 Failed Break** | Setup thứ hai theo ưu tiên của đặc tả; chuỗi ngược với S02 | Engine S04 + risk path dùng chung, test theo TC-005 |
| P6 | **Kiểm chứng S02** bằng Strategy Tester + báo cáo tuần forward | Khóa tham số PROPOSED | Báo cáo kiểm chứng S02 |
| P7 | S01 / S03 / S05 / S06 | Sau khi S02 và S04 đã có số liệu | Từng setup một, cùng khuôn với S02 |
| P8 | Telegram (REQ-018–020) | Dùng lại command queue (P4) và AI bridge (P3) | Điều khiển và hỏi AI qua Telegram |

## 3. Quyết định mặc định khi chưa có ý kiến khác

- **AI (Q1–Q6 trong thiết kế AI):** áp dụng các đề xuất. Chỉ bật Level 0 (AI chỉ báo cáo, không có quyền nào trên lệnh), nên không ảnh hưởng tới giao dịch. Người dùng đổi được bất cứ lúc nào.
- **Replay từ đầu năm:** chỉ đo và đánh giá, không đổi tham số News Guard.

## 4. Quy trình mỗi hạng mục

1. Thiết kế (spec) → người dùng chốt các điểm ảnh hưởng tới giao dịch.
2. Code + test (oracle Python khi có logic tính toán) + compile MetaEditor.
3. Deploy: kiểm tra target khớp bản đang chạy → backup → deploy → người dùng gắn lại EA → kiểm tra log.
4. Commit trên `feature/ui-redesign-v2`; merge vào `main` theo từng mốc.

## 5. Mục tiêu và trạng thái (cập nhật 05/10/2026)

| Goal | Nội dung | Trạng thái |
|---|---|---|
| G1 | Replay News Guard từ 01/01/2026 (P1) | ✅ Đang backfill; tin tháng 1–5 dùng nến M5 do MaxBars=100000 (`497fcc3`) |
| G2 | Market sentiment, chỉ giảm rủi ro (P1b, M1–M6) | ✅ Đã deploy `a7d7591`; 13/13 cặp tham chiếu, broker không có chỉ số chứng khoán Mỹ |
| G3 | Kiểm chứng trên tin thật: cụm PMI/ISM thứ Hai 05/10, NFP tháng 11 | ⏳ Chờ thị trường |
| G4 | Kiểm chứng lệnh thật: lệnh chờ REQ-021 (TC-046..051), Trade Manager, sentiment khi vào lệnh | ⏳ Chờ FX mở cửa thứ Hai |
| G5 | Đánh giá tuần chạy thử S02 (forward 1 tuần) | ⏳ Cuối tuần 10–11/10 |
| G6 | Tự động kiểm tra số liệu tin (P2) | ✅ Deploy cùng `G6` (news data health) |
| G7 | AI Bridge v1 Level 0 (P3) với các đề xuất Q1–Q6 | ✅ Đã deploy; bridge chạy tay bằng `run_bridge.ps1` (Windows) hoặc systemd (Ubuntu). 05/10: bridge đã dừng từ 04/10 ~15:00 (OAuth `claude` hết hạn), 7 request tồn (đều quá hạn, bị loại `AI_REQUEST_EXPIRED`); chạy lại 09:49 trong cửa sổ PowerShell riêng, cần mở lại sau khi khởi động lại máy |
| G8 | Command queue + CLOSE / PARTIAL / BE / TRAIL (P4, đặc tả 9.2) | ✅ Đã deploy; kiểm chứng với lệnh thật từ thứ Hai |
| G9 | S04 Failed Break (P5) | ✅ LIVE cùng S02 theo yêu cầu người dùng 04/10 (InpS04Mode=S04_LIVE); replay S02/S04 từ 01/01 để theo dõi |
| G10 | Kiểm chứng S02 bằng Strategy Tester (P6) | 🔬 05/10: chỉ S06 SWING (H1) có lợi thế dương ổn định (+0,10R, 550 lệnh 2024–2026); đề xuất đưa vào EA ở SHADOW. Sweep chạy lại trên dữ liệu xuất 05/10 (`5eecfb1`: sweep chỉ tính MARKET), có phí: kết luận không đổi. **Người dùng giữ S02/S04 LIVE trên demo** dù kết quả nghiên cứu âm, để lấy số liệu tuần chạy thử (G5) |
| G11 | Sentiment: dòng tóm tắt trên Overview + replay sentiment theo từng tin | ✅ 05/10: Overview (`6c7ecd8`); replay theo tin (`research/g11/sentiment_news.py`, 2.456 bản ghi 2026): sentiment **không** dự báo hướng phản ứng (48–53%, CI chứa 50%; ngang mức own momentum). Có tương tác: bất ngờ cùng chiều sentiment đi tiếp +0,21 ATR/60', ngược chiều −0,20 ATR. Regime khớp trú ẩn: RISK_OFF vàng +0,39, USDJPY −0,96; RISK_ON vàng −0,89 ATR. Không đổi tham số; sentiment vẫn chỉ giảm rủi ro |
| G12 | S01 / S03 / S05 / S06 (P7), Telegram (P8) | 🟡 05/10: **S06 Compression Expansion SWING đã code, LIVE theo yêu cầu người dùng** (`2026-10-05-s06-compression-expansion-v1-design.md`, `862db1e`), chờ deploy. S01/S03/S05 mới có prototype; Telegram chưa có |
| G13 | Push `main` lên GitHub | ✅ 05/10 (`107b8db`) |
| G14 | REQ-012 đánh giá AI: nhãn HELPFUL/HARMFUL/NEUTRAL/UNATTRIBUTABLE, báo cáo tuần, cổng AIG-01..07 | 🟡 05/10 phần 1: `bridge/ai_metrics.py` đo vận hành AI theo đặc tả 13.1 (sẵn sàng, độ trễ, hợp lệ, an toàn, nguồn, provider) và trạng thái AIG-01..07; xem bằng `/ai` và mục AI trong báo cáo tuần. Ngưỡng đề xuất AIG-02: ≥ 95% câu trả lời hợp lệ trên ≥ 20 lần gọi. Số liệu đầu tiên: 11 request / 7 ngày, chỉ 18% được trả lời (bridge ngừng 04/10) → độ sẵn sàng là việc cần cải thiện trước. Phần 2 (nhãn HELPFUL/HARMFUL, đối chứng shadow) chờ AI Level 1 |
| G15 | NFR-07 xoay vòng log: `audit.jsonl` tăng ~1,3 MB/ngày (chủ yếu `RUNTIME_REFRESHED` mỗi 30 s), `news_reactions.jsonl` 5,8 MB | ✅ 05/10 (`582fcb4`): `audit.jsonl` > 20 MB → `audit-<UTC>.jsonl`, giữ 10 bản; `news_reactions.jsonl` là dữ liệu nên không xoay. Chờ deploy |
| G16 | `news_state.json` chỉ ghi khi trạng thái tin đổi nên `last_success_utc` trên đĩa có thể cũ vài giờ; bên đọc ngoài EA (AI bridge) dễ hiểu nhầm là lịch tin cũ | ✅ 05/10 (`582fcb4`): ghi lại sau mỗi lần refresh thành công. Chờ deploy |
| G21 | Độ sẵn sàng của các dịch vụ ngoài EA (AI chỉ trả lời 18% request trong 7 ngày vì bridge chạy tay bị dừng) | ✅ 05/10: `bridge/supervisor.py` + `start_all.ps1` chạy lại AI bridge, gateway, soak monitor khi dừng, có backoff, tạm dừng khi chết liên tục, báo Telegram trực tiếp |
| G22 | Báo cáo theo phiên (đặc tả 13.3) | ✅ 05/10: Telegram gửi tóm tắt ngày lúc 23:30 (lệnh, candidate theo kết cục, News Guard, sự kiện hệ thống, AI, supervisor, soak) và `/today`. Candidate thật đầu tiên: EURUSD S02 SWING trigger 11:00 UTC, bị News Guard chặn đúng (`NEWS_PRE_BLOCK_SWING`, trước S&P PMI 13:45 UTC) |
| G23 | Kiểm định lịch sử dài 2010–2025 (`reports/2026-10-05-g23-long-history-validation.md`) | ✅ 05/10: S02 −0,32R (SWING, 949 lệnh) và SCALP mọi setup âm; **S04 SWING +0,12R ổn định 3 giai đoạn**; S06 live ≈ 0R trên 16 năm (biến thể hộp 24 vào ngay +0,24..0,31R, mẫu nhỏ). Đề xuất S02 → SHADOW, SCALP → SHADOW, S06 hiện tại → SHADOW; chờ người dùng quyết định |
| G26 | Bước 1 sau G23–G25 (người dùng đồng ý 05/10): chỉ S04 SWING vào lệnh thật | ✅ code 05/10: `InpScalpMode` (mặc định SHADOW, chặn trên cho mọi engine SCALP), chế độ theo engine cho live/shadow/sổ candidate; S06B (hộp 24, vào ngay, không lọc HTF, 3R) ở SHADOW; mặc định S02 SHADOW, S06 SHADOW, S04 LIVE; AI không xếp lại review tin mỗi lần EA khởi động lại; rủi ro cố định 0,3% giữ nguyên. Chờ nạp lại EA và đặt `InpS02Mode=SHADOW`, `InpS06Mode=SHADOW` trên chart (chart giữ giá trị cũ) |
| G27 | Bước 3: bộ lọc liên thị trường/chế độ thị trường, chọn theo "trung đạo" (đều, ít rủi ro) | ✅ nghiên cứu 05/10 (`research/long/filters.py`, `middle_way.py`, báo cáo `2026-10-05-g27-filters-middle-way.md`): chỉ `USD_FLOW` trên S06B cải thiện đều cả 3 giai đoạn; S04 + S06B lọc USD ≈ +1,1%/năm, DD 2,5%, 11/16 năm dương; S02/S06 cũ không cứu được bằng lọc. Đề xuất: ghi cờ USD vào shadow S06B, forward rồi mới quyết LIVE |
| G28 | Gồng lệnh, bồi lệnh, hành vi đám đông, chuỗi thua (chỉ dữ liệu MT5) | ✅ nghiên cứu 06/10 (`research/long/exits.py`, `crowd.py`, tick volume qua `convert_raw.py --tickvol`, báo cáo `2026-10-06-g28-exits-pyramiding-crowd.md`): TM hiện tại giữ nguyên; bồi lệnh S06B ở +1R cải thiện đều 3 giai đoạn (tài khoản +1,08% → +1,49%/năm, DD 2,7%, 14/16 năm dương); bộ lọc đám đông (tick volume, đuổi giá, chuỗi nến, RSI) không ổn định; thắng/thua độc lập nên không đổi lot theo chuỗi. Đề xuất: bồi lệnh S06B ở SHADOW trước |
| G17 | NFR-02 soak test, NFR-06 đo CPU/RAM | 🟡 05/10: `bridge/soak_monitor.py` chạy nền từ 15:xx (mẫu 5 phút, `logs/soak.jsonl`), xem bằng `/soak`; kết luận ở buổi G5 cuối tuần |
| G18 | Phân xử giữa các setup (TC-007) và sổ candidate (`2026-10-05-setup-arbitration-and-candidate-ledger-design.md`): ưu tiên S06 → S04 → S02, SWING trước SCALP; mỗi symbol + chiều + khung 1 lệnh; SCALP chồng lên SWING cùng chiều rủi ro × 0,5 (`InpScalpRiskWithSwingSameSide`); `logs/candidates.jsonl` + `research/g10/candidates_eval.py` cho kết quả ảo của candidate không vào lệnh | ✅ 05/10 code xong, chờ deploy cùng G12/G15/G16 |
| G19 | Telegram (REQ-018–020, `2026-10-05-telegram-gateway-v1-design.md`): gateway long polling, `/status`, `/ask`, `/pause`, `/resume` + `/confirm` hai bước; chế độ vào lệnh của operator trong EA (`operator_mode.json`); thông báo lệnh, cảnh báo, báo cáo AI, tin HIGH | ✅ 05/10, kiểm chứng đầu cuối với EA thật (pause/resume/confirm) |
| G20 | Công cụ đánh giá tuần (cho G5): Trade Manager ghi kết quả thật khi đóng lệnh (tiền = tổng profit/commission/swap/fee các deal của vị thế; R = tiền / rủi ro tại SL ban đầu; chưa thấy deal đóng thì ghi chưa rõ) vào `TRADE_EXITED` và `logs/trades.jsonl`; `research/g10/weekly_review.py` so lệnh thật, mô hình trên lệnh đã vào, candidate bị chặn theo lý do, như chạy một mình và số nghiên cứu; Telegram báo R khi đóng lệnh | ✅ 05/10. Cách dùng cuối tuần: `python research/g10/weekly_review.py` (nến được xuất lại tự động vào thứ Bảy) |

**Deploy và nạp lại 05/10 14:24 (giờ VN):** EA chạy bản `main` `23dd3eb` (G11–G20). Được người dùng cho phép, MT5 được đóng bình thường (profile lưu EA cùng input live: `InpObserverOnly=false`, `InpExecutionEnabled=true`, `InpLiveTradeArmed=true`) rồi mở lại; input mới lấy mặc định `InpS06Mode=S06_LIVE`, `InpScalpRiskWithSwingSameSide=0.5`. Kiểm chứng: runtime OBSERVING; `operator_mode.json` tự tạo RUNNING; 5 engine S06 chạy; vòng Telegram `/pause` → `/resume` → `/confirm` chạy thật với EA (v2 PAUSED → v4 RUNNING, 3 tin trả lời đã gửi). Backup: `Terminal/EnterpriseEA-backup-20261005-124756` (EA), `Terminal/Profiles-backup-20261005-142358` (profile chart).

**Mốc chờ thị trường:** G3 S&P Services PMI 20:45 và ISM 21:00 tối 05/10 (giờ VN); G4 lệnh thật (TC-046..051, Trade Manager TC-012..015); G5 đánh giá tuần chạy thử 10–11/10.
