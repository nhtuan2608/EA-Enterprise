# Kế hoạch triển khai vòng đời lệnh chờ theo setup

Ngày 30/09/2026. Trạng thái: **bước 3 có prototype offline cô lập; chưa triển khai gửi/hủy lệnh thật**. Nguồn yêu cầu: [PENDING_ORDER_LIFECYCLE_SPEC.md](PENDING_ORDER_LIFECYCLE_SPEC.md), REQ-021 và TC-046 đến TC-051. Telegram tạm dừng theo yêu cầu người dùng. Máy phát triển hiện tại không có MT5/MetaEditor, nên các bước offline chỉ tạo contract và đối chiếu thiết kế.

| Thứ tự | Phase và đầu ra cần có | Tiêu chí hoàn thành | Phụ thuộc |
| --- | --- | --- | --- |
| 1 | Phase 0/2: bảng profile thời hạn cho từng setup/style/symbol/session/order type; quy tắc setup invalidation và drift; version config | SCALP/SWING có mốc UTC, số nến tối đa, điều kiện hủy sớm và source evidence riêng; các giá trị chưa đo được để trạng thái OPEN | Chọn broker demo, symbol, timeframe và setup ưu tiên |
| 2 | Phase 3: contract risk cho pending remainder và broker capability map | Risk reservation bao gồm phần đã fill và phần còn chờ; không giải phóng remainder khi chỉ gửi cancel hoặc đồng hồ local hết hạn; fail closed khi capability/quote/reconcile thiếu | Account ledger, instrument spec và chính sách FTMO 1-Step/2-Step đã xác nhận |
| 3 | Phase 4 offline: state machine thuần + fixture/oracle cho BUY/SELL LIMIT và STOP | TC-046–051: expiry theo UTC/nến, invalidation sớm, partial fill, cancel/fill race, duplicate, restart, không có nến mới; không có OrderSend; các transition có reason/audit | Bước 1–2 có contract tối thiểu |
| 4 | Phase 4 MT5 adapter: đọc order/deal/history, broker ACK, timer, OnTradeTransaction, checkpoint | Tái dựng trạng thái sau restart; xác nhận order đã hủy/hết hạn và volume còn lại; không mất fill xảy ra trong lúc cancel; đối chiếu timezone/DST và time-in-force của broker | Máy MT5 được phép, broker demo và compile MQL5 |
| 5 | Strategy Tester và Paper: đo độ trễ hủy, fill race, broker reject, thị trường đóng và mất kết nối | Lưu trace theo ticket, candidate, setup/config version và UTC; risk/account ledger khớp broker sau mỗi ca; profile được hiệu chuẩn và khóa | Bước 4 qua runtime gate |
| 6 | Live gate | Chỉ xem xét sau Paper đạt, chính sách FTMO/account và broker cụ thể được duyệt; chưa có lịch bật live | Bằng chứng từ bước 5 |

Tiến độ bước 3: `TradeManager/PendingOrderLifecycle.mqh` và fixture/oracle Python đã mô tả các transition chính. `Storage/PendingOrderCheckpoint.mqh` v1.1 giữ exposure, mang audit-tail anchor và chặn entry mới khi restore; `Storage/PendingOrderAudit.mqh` kiểm tra chuỗi transition và evidence đối soát ở mức contract. Xem [ranh giới vòng đời](TradeManager/PENDING_ORDER_LIFECYCLE_OFFLINE.md), [checkpoint](Storage/PENDING_ORDER_CHECKPOINT_OFFLINE.md) và [audit](Storage/PENDING_ORDER_AUDIT_OFFLINE.md). Chưa hoàn thành profile đã hiệu chuẩn, serializer/file persistence, audit JSONL thực và replay toàn chuỗi, broker adapter hay đối chiếu MQL runtime. Bước 1–2 vẫn cần dữ liệu broker và policy cụ thể trước Paper.

## Quy tắc kiểm soát phạm vi

- Hoàn thành đặc tả và plan trước khi nối module giao dịch. Prototype ảo nếu viết ở bước 3 phải cô lập khỏi EA shell và không được coi là MT5 đã vận hành.
- STOP LIMIT chưa thuộc bước 3 vì có trigger và lệnh LIMIT thứ cấp cần hai thời hạn, broker fixture riêng.
- Không tự đặt lại order sau hủy/hết hạn. Candidate và order intent mới cần setup, quote, risk và audit mới.
- Bước 4 không được kết luận `CANCELLED` chỉ từ kết quả gửi request; phải có broker order/deal evidence. Khi evidence chưa đủ, block entry mới và giữ quản lý vị thế đã fill.

## Việc cần chốt trước Paper

1. Profile TTL, max closed bars và drift theo setup/style/symbol/session; chọn giá trị từ dữ liệu quan sát thay vì một TTL toàn cục.
2. Broker demo, loại account, symbol thực, hỗ trợ expiration của từng loại pending order, timezone/DST và quy tắc ngày giao dịch.
3. Policy remainder sau partial fill và hành vi khi cancel bị reject hoặc không thể reconcile.
4. Chỉ số nghiệm thu paper: thời gian từ `CANCEL_REQUIRED` đến broker confirmed, số fill sau yêu cầu hủy, sai lệch volume/risk sau restart và số case unknown chưa được reconcile.
