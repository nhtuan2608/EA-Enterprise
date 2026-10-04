# Command queue và thao tác tay trên lệnh (G8, đặc tả 9.2)

Ngày 04/10/2026. Trạng thái: **IMPLEMENTED (G8)**. Người dùng chốt C1–C6 theo đề xuất.

Mã nguồn: `Runtime/CommandQueue.mqh`, `schemas/ea-command.schema.json`, tab Trades trong `Runtime/SymbolSelectionPanel.mqh`, test `Tests/command_queue_tests.py`.

Cách thao tác trên tab Trades: bấm vào tên symbol của lệnh EA để chọn dòng → thanh "Manual actions" hiện các nút → bấm Confirm trong 15 giây.

Nguồn: master specification v1.4 mục 9.1 (tab TRADES: "Action qua Command Queue và confirm"), 9.2 (CLOSE / PARTIAL / BE / TRAIL), REQ-005, REQ-006, REQ-011; `TELEGRAM_CONTROL_SPEC.md` (REQ-018–020, `schemas/remote-command.schema.json`, `Integration/RemoteModeGate.mqh`); Trade Manager v1; REQ-021.

---

## 1. Vấn đề

Tab Trades hiện **chỉ để xem**. Muốn đóng lệnh, chốt một phần, dời SL về hòa vốn hay bật trailing, người dùng phải thao tác trong MT5. Làm vậy có ba nhược điểm:

- thao tác không đi qua các cổng kiểm tra của EA (authorization, khoảng cách stop, volume, chống gửi trùng);
- không được ghi vào audit của EA;
- Trade Manager không biết người dùng vừa làm gì, nên có thể làm lại cùng một việc, ví dụ chốt một phần hai lần.

## 2. Đặc tả 9.2 yêu cầu gì

| Thao tác | Luồng bắt buộc |
|---|---|
| CLOSE | Bấm → xác nhận → **command queue** → engine kiểm tra → intent đóng lệnh → kết quả từ broker → cập nhật UI |
| PARTIAL | Chọn hoặc dùng sẵn khối lượng → kiểm tra volume min/step/phần còn lại → xác nhận → thực hiện |
| BE | Tính mức hòa vốn (kèm chi phí nếu policy yêu cầu) → kiểm tra stop/freeze level → dời SL |
| TRAIL | Chọn chế độ trail mà setup/profile cho phép → kiểm tra → đổi trạng thái |

**Command queue** là nơi mỗi thao tác được ghi thành một "lệnh điều khiển" có mã riêng, nguồn, thời điểm và hạn dùng, **trước khi** EA thực hiện. Nhờ vậy:

- **Bền:** gỡ EA ra rồi gắn lại không mất thao tác, và không có thao tác nào bị chạy hai lần.
- **Cùng cổng kiểm tra:** thao tác tay đi qua đúng các cổng như lệnh tự động.
- **Dùng lại được:** Telegram và các nguồn khác sau này dùng chung hàng đợi này, nên không phải làm thêm đường gửi lệnh riêng.

## 3. Phạm vi v1

| Thao tác | Áp cho | Ghi chú |
|---|---|---|
| `CLOSE` | Vị thế do EA mở | Đóng toàn bộ |
| `PARTIAL` | Vị thế do EA mở | Mặc định 50%, làm tròn theo volume step; phần đóng và phần còn lại đều phải ≥ volume min |
| `BE` | Vị thế do EA mở | SL = giá vào ± spread hiện tại; chỉ khi SL mới chặt hơn SL hiện tại và đủ khoảng cách stop/freeze |
| `TRAIL` | Vị thế do EA mở | Bật trailing theo profile (SCALP: ATR, SWING: cấu trúc 5 nến) ngay lập tức; chỉ siết SL, không bao giờ nới |
| `CANCEL` | Lệnh chờ do EA đặt (REQ-021) | Hủy lệnh chờ; phần đã khớp (nếu có) vẫn được Trade Manager quản lý |
| `CLOSE_ALL_EA` | Mọi vị thế và lệnh chờ của EA | Dùng khi khẩn cấp, cần xác nhận mạnh hơn (mục 6) |

**Không thuộc v1:**
- vị thế mở tay hoặc do EA khác mở. Những vị thế này vẫn hiển thị nhưng không có nút; người dùng xử lý trong MT5 như hiện tại (C1);
- dời SL hoặc TP tới một giá tùy ý;
- tăng volume;
- mở lệnh mới bằng tay.

## 4. Luồng xử lý

```
Panel (bấm nút) ─► thanh xác nhận (tóm tắt, 15 giây) ─► Confirm
   ─► ghi command vào current/commands/<command_id>.json   (COMMAND_QUEUED)
   ─► EA xử lý ngay trong cùng sự kiện và mỗi lần timer:
        1. Kiểm tra lệnh: nguồn được phép, còn hạn (TTL 60 giây), chưa từng xử lý (command_id)
        2. Kiểm tra trạng thái: vị thế/lệnh chờ còn tồn tại, cùng ticket; volume và SL
           vẫn khớp lúc bấm (expected_volume, expected_sl); EA đang armed
        3. Kiểm tra theo thao tác: volume min/step (PARTIAL), mức hòa vốn và stop/freeze
           level (BE), chế độ trail của profile (TRAIL), lệnh chờ do EA theo dõi (CANCEL)
        4. Thực hiện qua đúng hàm adapter hiện có (close / modify / cancel), với
           authorization bảo vệ của phiên và khóa chống gửi trùng "cmd-<command_id>"
        5. Ghi kết quả vào journal + audit; cập nhật Trade Manager; báo kết quả trên panel
```

- **Hết hạn:** command quá 60 giây chưa xử lý (ví dụ EA vừa gỡ ra và gắn lại) bị đánh dấu `COMMAND_EXPIRED` và **không bao giờ** được thực hiện sau đó.
- **Một command, một lần thực hiện:** mã `command_id` đi qua cơ chế đánh dấu chống gửi trùng (idempotency index) đã có.
- **Trạng thái đã thay đổi thì từ chối.** Nếu vị thế đã đổi giữa lúc bấm và lúc thực hiện (Trade Manager vừa chốt một phần, SL vừa dời...), lệnh bị từ chối với `COMMAND_STATE_CHANGED`. Người dùng xem lại trạng thái rồi bấm lại.

## 5. Quyền và an toàn

- **Chỉ thao tác giảm rủi ro.** Mọi thao tác v1 đều giảm hoặc giữ nguyên rủi ro, nên được phép cả khi phiên ủy quyền đã bị thu hồi hoặc hết hạn, giống phần bảo vệ của Trade Manager. EA dùng authorization bảo vệ gắn với phiên đã mở lệnh.
- **Cần EA armed** (input execution enabled + armed, C3). Khi EA chỉ quan sát, các nút bị khóa và hiện "Use MT5 directly".
- **Nguồn:**
  - v1 chỉ nhận `PANEL`.
  - `TELEGRAM` sau này chỉ được `PAUSE_ENTRIES` / `RESUME` theo đặc tả Telegram; muốn mở thêm CLOSE / BE qua Telegram cần đặc tả và gate riêng.
  - `AI` **không bao giờ** được gửi command ở v1; AI Level 2 về sau chỉ có REDUCE / BLOCK qua gate riêng.
- **Kill switch không chặn thao tác bảo vệ.** Kill switch đang bật vẫn cho phép CLOSE / BE / CANCEL, vì đây là thao tác khẩn cấp.
- **Không đụng vị thế ngoài EA.** EA không có lineage rủi ro cho vị thế mở tay, và gate sẽ từ chối các lệnh không có lineage.

## 6. Giao diện

- **Tab Trades:**
  - mỗi dòng **vị thế của EA** có các nút nhỏ `Close`, `½`, `BE`, `Trail`;
  - mỗi dòng **lệnh chờ của EA** có nút `Cancel`;
  - dòng của vị thế không thuộc EA ghi "external" và không có nút.
- **Thanh xác nhận** thay cho dòng "MANUAL ACTIONS" hiện nay, ví dụ:
  `Close XAUUSD #123456 · 0.10 lot · P/L +12.40 USD · SL 2651.20` với hai nút **Confirm** và **Cancel**. Thanh tự hủy sau 15 giây.
- **`CLOSE_ALL_EA`:** nút riêng ở cuối tab, cần **hai bước xác nhận**:
  - bước 1: thanh xác nhận liệt kê số vị thế và lệnh chờ sẽ bị đóng hoặc hủy;
  - bước 2: nút đổi thành "Confirm close all (n)", bấm lần hai trong 10 giây.
- **Kết quả:** toast và một dòng "Last command" trên tab Trades, ví dụ `APPLIED` hoặc `REJECTED: COMMAND_STATE_CHANGED`.

## 7. Liên kết với Trade Manager

| Thao tác tay | Trade Manager ghi nhận |
|---|---|
| `PARTIAL` | `partial_done=true` (không tự chốt thêm lần nữa) |
| `BE` | `be_done=true` |
| `TRAIL` | `trail_active=true`; các lần trail sau vẫn theo profile và chỉ siết |
| `CLOSE` | Vị thế biến mất → `EXITED` với lý do `MANUAL_CLOSE` (gắn `command_id`) |
| `CANCEL` | Tracker REQ-021 chuyển `CANCEL_REQUESTED`, chờ broker xác nhận như bình thường |

## 8. Lưu trữ và audit

- **Hàng đợi:** `current/commands/<command_id>.json`. Command đã xử lý được chuyển sang `current/commands/done/`.
- **Journal:** `logs/commands.jsonl`, mỗi command một dòng kết quả gồm `command_id`, nguồn, thao tác, ticket, trạng thái trước → sau, kết quả broker, lý do.
- **Audit:** `COMMAND_QUEUED`, `COMMAND_APPLIED`, `COMMAND_REJECTED` (kèm lý do), `COMMAND_EXPIRED`.
- **Schema:** `schemas/ea-command.schema.json` (`ea-command-v1.0.0`), gồm:
  - `command_id`, `source`, `action`, `ticket_kind` (`POSITION` / `ORDER`), `ticket`;
  - `expected_volume`, `expected_sl`, `partial_fraction`;
  - `issued_at_utc`, `expires_at_utc`;
  - `account_fingerprint`, `config_version`, `operator_id`.

## 9. Kiểm thử

| ID | Kịch bản → kết quả mong đợi |
|---|---|
| TC-CQ-01 | Close vị thế EA → command QUEUED → APPLIED; Trade Manager ghi `MANUAL_CLOSE`; audit đủ ba bước |
| TC-CQ-02 | Cùng `command_id` gửi hai lần → chỉ thực hiện một lần |
| TC-CQ-03 | Command quá 60 giây (ví dụ gắn lại EA giữa chừng) → `COMMAND_EXPIRED`, không thực hiện |
| TC-CQ-04 | Volume đã đổi giữa lúc bấm và lúc thực hiện → `COMMAND_STATE_CHANGED` |
| TC-CQ-05 | Partial 50% với 0,01 lot → từ chối vì phần đóng hoặc phần còn lại < volume min |
| TC-CQ-06 | BE khi giá quá gần hoặc SL hiện tại đã chặt hơn → từ chối, không gửi lệnh |
| TC-CQ-07 | Trail không bao giờ nới SL |
| TC-CQ-08 | Vị thế mở tay → không có nút; command giả cho ticket đó bị từ chối `COMMAND_NOT_EA_POSITION` |
| TC-CQ-09 | Phiên đã thu hồi + kill switch bật → CLOSE / BE / CANCEL vẫn được; EA chưa armed → bị khóa |
| TC-CQ-10 | `CLOSE_ALL_EA` cần hai bước xác nhận; đóng mọi vị thế EA và hủy mọi lệnh chờ EA, mỗi lệnh có kết quả riêng |
| TC-CQ-11 | Kiểm tra tĩnh: nguồn `AI` bị từ chối; không có thao tác tăng rủi ro trong whitelist |

## 10. Kế hoạch triển khai

1. Schema + module thuần `Runtime/CommandQueue.mqh` (kiểm tra, TTL, idempotency, kiểm tra trạng thái) + oracle Python (TC-CQ-02..08, 11).
2. Thực hiện qua adapter (close / modify / cancel) với authorization bảo vệ; liên kết với Trade Manager và tracker REQ-021 (TC-CQ-01, 09).
3. Panel: nút trên từng dòng, thanh xác nhận, `CLOSE_ALL_EA` hai bước, dòng "Last command" (TC-CQ-10).
4. Compile, test, deploy; kiểm chứng trên demo khi có lệnh thật (thứ Hai trở đi).

## 11. Quyết định cần người dùng chốt

| ID | Câu hỏi | Đề xuất |
|---|---|---|
| C1 | Áp cho vị thế nào | **Chỉ vị thế và lệnh chờ do EA mở.** Vị thế ngoài EA không có nút |
| C2 | Có nút đóng tất cả khẩn cấp không | **Có** (`CLOSE_ALL_EA`), xác nhận hai bước |
| C3 | Khi EA chưa armed | **Khóa nút**, người dùng thao tác trong MT5 |
| C4 | Khối lượng partial | **50%** mặc định; bấm `½` lần nữa trên thanh xác nhận để đổi 25% / 50% / 75% |
| C5 | Thời gian xác nhận | Thanh xác nhận 15 giây; command hết hạn sau 60 giây |
| C6 | Trail tay | Bật trail theo profile **ngay lập tức** (không chờ 1,5R / 2R), chỉ siết SL |
