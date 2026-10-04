# Trade Manager v1 (REQ-005)

Ngày 04/10/2026. Trạng thái: IMPLEMENTED, các ngưỡng là seed PROPOSED. Nguồn: master specification v1.4 mục 6, TC-012 đến TC-015, CHK-TM-01/02. Code: `Runtime/TradeManagerRuntime.mqh`.

## 1. Phạm vi

- Chỉ quản lý vị thế do EA mở. Mỗi lệnh được đăng ký ngay khi broker xác nhận lệnh vào, kèm toàn bộ lineage của candidate, rồi gắn với vị thế qua deal vào lệnh. Lệnh tay và lệnh của EA khác không bao giờ bị đụng tới.
- Mọi thao tác (dời SL, đóng một phần, đóng toàn bộ) đi qua đúng các cổng như khi vào lệnh: authorization, khóa chống gửi trùng (`manage-<candidate>-…`), gate, audit.
- Trạng thái lưu ở `current/trade_<ticket>.json` nên vẫn còn sau khi gỡ EA ra rồi gắn lại.

## 2. Vòng đời và số liệu

- Vòng đời: `ENTERED → PROVING` (nến đóng đầu tiên) `→ WORKING` (MFE ≥ 0,5R) `→ MATURE` (MFE ≥ 1R hoặc đã trail) `→ EXITED`.
- Mỗi nến đóng của khung thời gian setup, EA lưu MFE/MAE theo R và số nến tới 0,5R, 1R, 2R. Các mốc này cùng với mọi thay đổi trạng thái và mọi thao tác đều được ghi audit (`EA_TRADE_MANAGER`).

## 3. Profile (SCALP và SWING không dùng chung tham số)

| | SCALP (M5) | SWING (H1) |
|---|---|---|
| Chốt một phần | 50% tại 1,0R | 33% tại 1,5R |
| Dời SL về hòa vốn (break-even) | MFE ≥ 1,0R | MFE ≥ 1,0R |
| Trail | ATR: close − 1×ATR14, bắt đầu từ 1,5R | Structure: đáy/đỉnh 5 nến gần nhất ± 0,1×ATR, bắt đầu từ 2,0R |
| Cờ UNDERPERFORMING (chỉ ghi nhận, TC-012) | nến 8 mà MFE < 0,5R | nến 15 mà MFE < 0,5R |
| Time stop (khi chưa trail) | 36 nến (3 giờ) | 120 nến (5 ngày) |

- **Break-even** = giá vào ± spread hiện tại.
- **Trail** không bao giờ đưa SL lùi về sau mức hòa vốn, và chỉ dời khi SL tiến thêm ≥ 0,1R.
- **SL chỉ được siết, không bao giờ nới.** SL mới phải cách giá ít nhất stops level / freeze level của broker.
- **Chốt một phần** chỉ chạy khi cả phần đóng và phần còn lại đều ≥ volume min; nếu không đủ thì bỏ qua và ghi lý do.
- **Structure invalidation (TC-013):** trước khi dời SL về hòa vốn, nếu một nến đóng cửa vượt ngược qua mép xa của vùng thì đóng lệnh ngay, không chờ SL.
- Lệnh đóng chưa thành công (structure hoặc time stop) được lưu lại và EA thử gửi lại cho tới khi broker xác nhận.

## 4. Khi phiên bị thu hồi hoặc hết hạn

- Thu hồi phiên **không đóng vị thế**.
- Vị thế nào **đang lời** thì EA chỉ dời SL về hòa vốn, một lần, khi khoảng cách tới giá đủ cho broker chấp nhận.
- Ngoài việc đó, EA không chốt một phần, không trail, không đóng lệnh theo time stop hay structure.
- Vị thế đang lỗ giữ nguyên SL/TP ban đầu.

## 5. Khôi phục sau restart

Kết quả không rõ (`EXECUTION_UNKNOWN`) của thao tác quản lý lệnh hoặc hủy lệnh chờ không chặn việc vào lệnh mới khi khởi động lại; vị thế hoặc lệnh liên quan được runtime riêng của nó đối soát. Chỉ lệnh vào có kết quả không rõ mới chặn.
