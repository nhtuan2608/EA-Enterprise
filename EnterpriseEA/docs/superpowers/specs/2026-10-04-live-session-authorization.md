# Ủy quyền theo phiên (Session Authorization)

Ngày 04/10/2026. Trạng thái: IMPLEMENTED, chưa deploy. Thay cho việc phải tạo một file `live_authorization.json` cho từng lệnh. File theo từng lệnh vẫn được giữ làm đường dự phòng khi không có phiên.

## 1. Ba lớp phải cùng mở thì EA mới gửi lệnh

| Lớp | Ai bật | Ở đâu |
|---|---|---|
| Input | Người vận hành, F7 | `InpObserverOnly=false`, `InpExecutionEnabled=true`, `InpLiveTradeArmed=true` |
| Phiên ủy quyền | Người vận hành, nút trên Settings → Authorization | `current/live_session.json` |
| Controller / kill switch | Ghi cùng lúc với phiên | `current/execution_controller_state.json` (kill OFF, scope `MARKET_AND_PENDING_ENTRY`, cùng khung giờ với phiên) |

## 2. Ký phiên

- Bấm **Authorize 24h** hoặc **Authorize 7 days**, sau đó bấm lần hai trong 10 giây để xác nhận.
- Trước khi ghi, EA kiểm tra lại:
  - runtime đang `OBSERVING`;
  - không có trạng thái thực thi chưa rõ và lệnh chờ không bị chặn;
  - đã chốt risk policy;
  - ledger đã biết vốn ban đầu;
  - có ít nhất một symbol đã resolve;
  - nếu là tài khoản REAL thì phải có `InpSessionAllowRealAccount=true`.
- Nội dung phiên:
  - gắn với account fingerprint, server, config version, margin mode và risk policy đang chốt;
  - danh sách broker symbol tại thời điểm ký;
  - rủi ro mỗi lệnh = `per_trade` của O-04;
  - lỗ ngày tối đa = `internal_daily` của O-04;
  - số lệnh mỗi ngày Prague = `InpSessionMaxEntriesPerDay` (mặc định 6);
  - hiệu lực tối đa 7 ngày.
- Mỗi lần ký ghi sự kiện audit `LIVE_SESSION_SIGNED`.

## 3. Trong phiên

- Với mỗi candidate đã qua Risk Kernel, EA sinh authorization riêng: `intent_id = <session_id>-<candidate_id>`. Execution adapter vẫn kiểm tra ràng buộc 1 authorization ↔ 1 intent như trước.
- EA từ chối và ghi lý do trong các trường hợp sau:
  - phiên hết hạn hoặc đã bị thu hồi;
  - đổi tài khoản, server, config hoặc policy;
  - đổi loại tài khoản giữa demo và real;
  - symbol không nằm trong danh sách;
  - đã đủ số lệnh trong ngày;
  - lỗ trong ngày (balance lúc reset − equity) chạm giới hạn;
  - không ghi được bộ đếm lệnh.
- Rủi ro của phiên chỉ có thể giảm rủi ro của plan, không bao giờ tăng.
- Bộ đếm lệnh lưu ở `current/live_session_usage.json` nên vẫn còn sau khi gỡ EA ra rồi gắn lại.

## 4. Thu hồi và hết hạn

- **Revoke now** có tác dụng ngay, không cần xác nhận:
  - đánh dấu phiên là `REVOKED`;
  - bật lại kill switch (controller tăng revision);
  - ghi audit `LIVE_SESSION_REVOKED`.
- Khi phiên đã bị thu hồi hoặc hết hạn, lệnh chờ của EA bị hủy ở nến đóng kế tiếp. Lệnh hủy vẫn được phép sau khi phiên kết thúc vì nó chỉ làm giảm exposure, và nó vẫn ràng buộc với phiên đã đặt lệnh đó.
- Vị thế đang mở giữ nguyên SL/TP. Thu hồi không đóng vị thế.
