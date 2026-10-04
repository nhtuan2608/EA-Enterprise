# Thông tin thị trường trong phân tích và vào lệnh; thiết kế News Guard

Ngày 04/10/2026. Trạng thái: **IMPLEMENTED** (`News/NewsState.mqh`, `News/NewsCalendar.mqh`; nối vào vòng live, REQ-021 và Trade Manager) theo D1–D5 người dùng chốt ở mục 11. Còn chờ kiểm chứng trên terminal qua một tin HIGH thật (mục 12). Từ bản này, O-16 (`NEWS_UNAVAILABLE_ACCEPTED`) được thay bằng News Guard. Mục 1–2 mô tả hiện trạng của bản `29f9a5d`, trước khi có News Guard. Mục 3 trở đi là thiết kế News Guard theo các quyết định đã chốt.

Nguồn: master specification v1.4 mục 7 (News Center), 7.4 (news risk state machine), REQ-007, TC-018 đến TC-020, CHK-NEWS-01/02, quyết định O-16; S02 v1 design; Trade Manager v1; REQ-021.

---

## 1. Hiện trạng: hệ thống chỉ phân tích bằng giá

EA chỉ dùng dữ liệu giá, phiên và broker. Tin kinh tế, lịch sự kiện và AI có trong đặc tả nhưng chưa được xây. Việc chạy live khi chưa có News Center được chấp nhận theo O-16.

| Bước | Dữ liệu giá dùng | Ảnh hưởng tới quyết định |
|---|---|---|
| Vùng giá quan trọng | Nến D1 (đỉnh/đáy ngày trước), W1 (đỉnh/đáy tuần trước), đỉnh/đáy các phiên Á/London/NY, swing H1/H4 | Chỉ khi ≥ 2 nguồn level trùng nhau trong 0,25×ATR mới thành vùng giao dịch. Không có vùng thì không có setup. |
| Xu hướng khung lớn | 2 đỉnh và 2 đáy xác nhận gần nhất trên H1 (SCALP) hoặc H4 (SWING) | Cùng xu hướng thì rủi ro ×1,0; ngược xu hướng thì ×0,5. Hệ thống không cấm đánh ngược xu hướng, chỉ giảm rủi ro. |
| Trình tự setup | Nến M5/H1 đã đóng cửa và ATR14 | Phá vùng → giữ được → retest → nến xác nhận. Mọi ngưỡng tính theo ATR nên tự co giãn theo độ biến động của từng symbol. |
| Chọn kiểu lệnh | Giá hiện tại so với mép vùng và nến xác nhận | Còn xa vùng thì đặt LIMIT; đã phá vỡ xác nhận thì vào MARKET; chưa xác nhận thì đặt STOP; giá đã chạy quá 0,5×ATR thì bỏ, không đuổi giá. |
| SL/TP | Đáy/đỉnh của nhịp retest, các level cấu trúc | SL đặt sau cấu trúc; TP là level cấu trúc gần nhất cách ≥ 1R. Không có TP cấu trúc thì bỏ lệnh. |
| Chặn khi thị trường bất thường | Spread hiện tại, median spread 288 nến M5, tuổi của báo giá | Spread > 2× bình thường, hoặc > 25% khoảng SL, hoặc báo giá quá 30 giây thì không vào lệnh. |
| Khối lượng lệnh | Tick value, contract size, ký quỹ, commission/swap học từ lịch sử deal | Lot tính sao cho chạm SL thì lỗ đúng mức rủi ro cho phép, kể cả phí. |
| Quản lý lệnh | Nến đóng cửa và ATR | Dời SL hòa vốn, trail, chốt một phần, time stop, đóng khi cấu trúc gãy. |

## 2. Thông tin thị trường: đặc tả đã lên kế hoạch nhưng chưa có

- **News Center (REQ-007, mục 7):** gán trạng thái `PRE NEWS / ACTIVE / POST NEWS / NORMAL / UNKNOWN` cho từng symbol dựa trên lịch kinh tế. Khi có tin mạnh:
  - chặn vào lệnh mới quanh giờ ra tin;
  - hủy lệnh chờ chưa khớp. REQ-021 đã có sẵn chỗ nối `news_entry_allowed`, hiện cố định `true` trong `Runtime/PendingOrderRuntime.mqh`;
  - có thể dời SL về hòa vốn hoặc giảm rủi ro cho lệnh đang mở.
- **AI Bridge (REQ-008) và đo hiệu quả AI (REQ-012):** AI chỉ đưa nhận định tham khảo. Đặc tả cấm AI tự đặt lệnh hay sửa ngưỡng rủi ro, và mọi nhận định đều phải được đo hiệu quả.

**Hệ quả hiện tại:**
- EA có thể vào lệnh ngay trước hoặc trong lúc ra tin mạnh (NFP, CPI, FOMC…).
- Phần chặn spread chỉ bắt được khi spread đã giãn ra, tức là khi tin đã ra. Nó không chặn trước được, và không ngăn được trượt giá khi SL bị khớp lúc giá giật mạnh.
- Ghi nhận thêm: đặc tả O-16 yêu cầu audit của candidate ghi `NEWS_UNAVAILABLE_ACCEPTED`, nhưng source hiện **chưa ghi** reason này. News Guard sẽ thay nó bằng trạng thái tin thật (mục 9).

---

## 3. Mục tiêu và phạm vi của News Guard

News Guard là phần tối thiểu của News Center, đủ để bảo vệ vào lệnh và lệnh đang mở quanh các tin đã có lịch:

1. Đọc **lịch kinh tế có sẵn trong MT5 terminal** (Economic Calendar API của MQL5). Không cần nguồn ngoài, đúng REQ-001: EA là trung tâm.
2. Gán trạng thái tin cho từng symbol theo các đồng tiền liên quan.
3. Áp policy lên: vào lệnh mới, lệnh chờ, lệnh đang mở.
4. Hiển thị trên tab **News** của Dashboard và ghi audit.

**Không thuộc phạm vi đợt này:**
- surprise chuẩn hóa (mục 7.3);
- AI News Interpreter;
- tin không có lịch (phát biểu đột xuất, sự kiện địa chính trị);
- thanh khoản ngày lễ.

Các tin không có lịch vẫn chỉ được bảo vệ bởi chặn spread và SL.

## 4. Nguồn dữ liệu: MT5 Economic Calendar

| Hàm MQL5 | Dùng để |
|---|---|
| `CalendarValueHistory(values, from, to, NULL, currency)` | Lấy các giá trị sự kiện (giờ ra tin, actual/forecast/previous) của một đồng tiền trong khoảng thời gian |
| `CalendarEventById(event_id, event)` | Lấy tên sự kiện, `importance` (LOW/MODERATE/HIGH), đơn vị, tần suất |
| `CalendarCountryById(country_id, country)` | Lấy đồng tiền của quốc gia (kiểm tra chéo) |
| `CalendarValueLast(change_id, values)` | Phát hiện thay đổi: giờ dời, actual mới công bố |

Lưu ý kỹ thuật:
- **Múi giờ:** thời gian trong calendar là giờ của trade server. EA quy đổi sang UTC bằng độ lệch server đang dùng (`EEA_PendingServerOffset`, làm tròn 15 phút). Mọi so sánh nội bộ dùng UTC; Dashboard hiển thị giờ địa phương (GMT+7).
- **Cập nhật:** đọc lại toàn bộ cửa sổ [now − 1 giờ, now + 7 ngày] mỗi 15 phút, và mỗi timer kiểm tra `CalendarValueLast` để bắt thay đổi ngay.
- **Strategy Tester không có calendar.** Trong tester, News Guard tắt và ghi `NEWS_GUARD_TESTER_DISABLED`; đây là ngữ cảnh không live, panel cũng không hiển thị.
- **Dữ liệu không đọc được:** hàm trả lỗi, terminal mất kết nối tới máy chủ lịch, hoặc lần đọc thành công gần nhất cũ hơn 30 phút → trạng thái `UNKNOWN` (TC-019). Không bao giờ tự coi là NORMAL.

## 5. Gắn tin với symbol

Đồng tiền liên quan của symbol = base currency và profit currency lấy từ broker (`SYMBOL_CURRENCY_BASE`, `SYMBOL_CURRENCY_PROFIT`), bỏ các mã không có trong lịch.

| Symbol mặc định | Đồng tiền theo dõi |
|---|---|
| EURUSD | EUR, USD |
| GBPUSD | GBP, USD |
| USDJPY | USD, JPY |
| XAUUSD | USD (XAU không có lịch) |
| BTCUSD | USD (BTC không có lịch) |

- Chỉ lấy tin mức **HIGH** (mặc định; xem quyết định D4).
- Hai tin cách nhau ít hơn khoảng chặn được gộp thành một cửa sổ liên tục.
- Đặc tả 7.1 có Currency Mapper theo region/exposure. Bản này dùng cách ánh xạ đơn giản trên; chỉ thêm bảng ánh xạ thủ công khi có symbol mà cách đơn giản không đủ.

## 6. Máy trạng thái tin cho từng symbol

Theo mục 7.4 của đặc tả, với T là giờ ra tin HIGH của các đồng tiền liên quan. Khoảng chặn theo D1 khác nhau cho từng profile:

| Khoảng thời gian | Trạng thái | SCALP | SWING |
|---|---|---|---|
| Không có tin trong 3 giờ tới | `NORMAL` | Vào lệnh bình thường | Vào lệnh bình thường |
| [T − 3 giờ, T − 60 phút) | `PRE_NEWS` | Vào lệnh bình thường, có cảnh báo và đếm ngược | **Chặn** lệnh mới |
| [T − 60 phút, T) | `PRE_NEWS_BLOCK` | **Chặn** lệnh mới | **Chặn** lệnh mới |
| [T, T + 5 phút) | `ACTIVE` | Chặn | Chặn |
| [T + 5, T + 15 phút) | `POST_NEWS` | Chặn | Chặn |
| Từ T + 15 phút | `NORMALIZING` → `NORMAL` | Chặn tới khi ổn định | Chặn tới khi ổn định |
| Không đọc được lịch | `UNKNOWN` | Áp policy D3 | Áp policy D3 |

- **Ổn định** nghĩa là spread ≤ 1,5× median spread (288 nến M5) **và** biên độ nến M5 đã đóng gần nhất ≤ 2×ATR14 (M5). Đạt một lần thì symbol về `NORMAL` cho tin đó.
- Nếu tới T + 60 phút vẫn chưa ổn định, symbol về `NORMAL` kèm audit `NEWS_NORMALIZE_TIMEOUT`. Từ đó chặn spread của S02 (spread > 2× median) tiếp tục bảo vệ. Cách này tránh việc chặn vô thời hạn, ví dụ khi thị trường đóng cửa ngay sau tin.
- Dời SL hòa vốn trước tin chạy ở mốc T − 15 phút (mục 7.3).
- Các mốc là seed PROPOSED, cấu hình bằng input (mục 10).
- Mỗi lần đổi trạng thái được ghi audit `NEWS_STATE_CHANGED` kèm symbol, tin, T (UTC) và trạng thái trước → sau.

## 7. Tác động lên vào lệnh, lệnh chờ và lệnh đang mở

### 7.1 Vào lệnh mới (đường live)
- News Guard là một lớp kiểm tra trong vòng live, đặt ngay sau bước chọn kiểu lệnh và **trước** Risk Kernel.
- Bị chặn thì ghi lý do theo profile: `NEWS_PRE_BLOCK_SCALP`, `NEWS_PRE_BLOCK_SWING`, `NEWS_ACTIVE`, `NEWS_POST`, `NEWS_NORMALIZING`, `NEWS_UNKNOWN`.
- Candidate không bị đánh dấu đã dùng, nên nếu còn hiệu lực sau cửa sổ tin thì vẫn được xét lại.
- Setup vẫn được quét bình thường trong lúc tin; chỉ việc gửi lệnh bị chặn.

### 7.2 Lệnh chờ (REQ-021)
- `news_entry_allowed` lấy từ News Guard theo profile của lệnh (`trade_style`) thay cho hằng `true`.
- Khi symbol vào trạng thái chặn của profile đó, tracker nhận một quan sát không phụ thuộc nến (`EEA_PendingObserveGuard`) và chuyển `CANCEL_REQUIRED` **ngay ở timer đó**, không chờ nến đóng.
- Khi đặt lệnh chờ mới, thời hạn broker được giới hạn tới trước thời điểm bắt đầu chặn của profile (SCALP: T − 60 phút, SWING: T − 3 giờ). Nếu thời gian còn lại ít hơn 1 nến thì không đặt lệnh (`NEWS_WINDOW_TOO_CLOSE`).

### 7.3 Lệnh đang mở (Trade Manager)
- Từ T − 15 phút: lệnh **đang lời ≥ 0,3R**, cả SCALP và SWING (D2), được dời SL về hòa vốn nếu broker chấp nhận khoảng cách stop. Lý do ghi là `NEWS_BREAK_EVEN`.
- Lệnh lỗ hoặc lời ít giữ nguyên SL ban đầu.
- Không đóng lệnh vì tin (D5). Chốt một phần và trail theo profile vẫn chạy bình thường. Time stop không bị dời.
- Khi phiên đã bị thu hồi, quy tắc của Trade Manager vẫn giữ: chỉ dời SL hòa vốn cho lệnh đang lời. Hai quy tắc dùng chung một thao tác, không bị thực hiện hai lần.

### 7.4 Không thay đổi
Ủy quyền phiên, giới hạn rủi ro O-04/FTMO, chống gửi trùng và mọi gate giữ nguyên. News Guard chỉ có thể chặn hoặc giảm, không bao giờ mở thêm quyền vào lệnh.

## 8. Dashboard

- **Header:** pill trạng thái tin của symbol gần tin nhất, kèm đếm ngược.
- **Tab News:**
  - bảng tin HIGH trong 48 giờ tới: giờ địa phương, đồng tiền, tên tin, mức độ, forecast / previous / actual;
  - trạng thái tin của từng symbol đang chọn;
  - thời điểm đọc lịch thành công gần nhất;
  - khi không đọc được lịch: dòng đỏ `UNKNOWN` kèm policy đang áp.
- **Tab Overview:** ô "Live engine – last decision" hiện lý do chặn vì tin khi có.
- **Settings → System:** các input News Guard đang hiệu lực (read-only).

## 9. Lưu trữ và audit

- `current/news_state.json`: snapshot các tin trong cửa sổ đọc, trạng thái từng symbol, thời điểm đọc thành công gần nhất. Chỉ phục vụ hiển thị ngay sau khi gắn lại EA; EA luôn đọc lại calendar trước khi dùng.
- Audit:
  - `NEWS_CALENDAR_REFRESHED` / `NEWS_CALENDAR_UNAVAILABLE`;
  - `NEWS_STATE_CHANGED`;
  - `NEWS_ENTRY_BLOCKED`, ghi một lần cho mỗi candidate và mỗi cửa sổ tin;
  - `NEWS_PENDING_CANCEL`;
  - `NEWS_BREAK_EVEN`.
- Audit của candidate và của lệnh ghi trạng thái tin tại thời điểm quyết định (`news_state`), thay cho `NEWS_UNAVAILABLE_ACCEPTED` của O-16.
- Mỗi lần có lệnh, Trade Manager ghi `news_state` vào audit của thao tác quản lý (đặc tả 6.3).

## 10. Input (seed PROPOSED)

| Input | Mặc định | Ý nghĩa |
|---|---|---|
| `InpNewsGuardEnabled` | `true` | Tắt thì quay về hành vi O-16 và Dashboard hiện `NEWS_GUARD_DISABLED` |
| `InpNewsScalpBlockBeforeMin` | 60 | SCALP chặn lệnh mới từ mốc này trước tin |
| `InpNewsSwingBlockBeforeMin` | 180 | SWING chặn lệnh mới từ mốc này trước tin (≥ mốc của SCALP) |
| `InpNewsActiveMin` | 5 | Độ dài `ACTIVE` |
| `InpNewsPostMin` | 15 | Hết `POST_NEWS`, bắt đầu kiểm tra ổn định |
| `InpNewsMaxNormalizeMin` | 60 | Chưa ổn định tới mốc này thì về NORMAL kèm audit |
| `InpNewsBreakEvenBeforeMin` | 15 | Mốc dời SL hòa vốn trước tin |
| `InpNewsBreakEvenMinR` | 0,3 | Lời tối thiểu (R) để dời SL hòa vốn |
| `InpNewsAllowWhenUnknown` | `false` | `false` = chặn lệnh mới khi không đọc được lịch; bật `true` để vẫn cho vào lệnh |
| `InpNewsIgnoreKeywords` | (trống) | Danh sách từ khóa cách nhau bằng dấu phẩy; tin HIGH có tên chứa từ khóa thì bỏ qua. Mặc định trống: người dùng giữ mọi tin HIGH, kể cả đấu giá trái phiếu và tồn kho dầu EIA (04/10/2026). |

Mức độ tin cố định là HIGH (D4).

## 11. Quyết định đã chốt (04/10/2026)

| ID | Quyết định |
|---|---|
| D1 | SCALP chặn lệnh mới từ **60 phút** trước tin; SWING chặn từ **3 giờ** trước tin. Sau tin cả hai chặn qua ACTIVE, POST_NEWS và tới khi ổn định. |
| D2 | Dời SL hòa vốn trước tin cho **cả SCALP và SWING**, chỉ với lệnh lời ≥ 0,3R, tại T − 15 phút. |
| D3 | Không đọc được lịch thì **chặn** lệnh mới (mặc định); người dùng bật `InpNewsAllowWhenUnknown` để vẫn cho phép. Lệnh đang mở vẫn được quản lý. |
| D4 | Chỉ tin mức **HIGH**. |
| D5 | **Không** đóng lệnh trước tin. |

## 12. Kiểm thử

| ID | Kịch bản → kết quả mong đợi |
|---|---|
| TC-NG-01 (TC-018) | Đếm ngược chuyển đúng NORMAL → PRE_NEWS (T−3h) → PRE_NEWS_BLOCK (T−60) → ACTIVE → POST_NEWS → NORMALIZING → NORMAL theo các mốc |
| TC-NG-02 (TC-019) | Calendar trả lỗi hoặc lần đọc thành công cũ hơn 30 phút → UNKNOWN; mặc định chặn lệnh mới; bật `InpNewsAllowWhenUnknown` thì cho phép; không bao giờ hiện NORMAL |
| TC-NG-03 | XAUUSD và BTCUSD chỉ theo tin USD; EURUSD theo cả EUR và USD |
| TC-NG-04 | Hai tin cách 20 phút gộp thành một cửa sổ chặn liên tục |
| TC-NG-05 | Giờ server ↔ UTC đúng qua chuyển DST (cuối tháng 3 và cuối tháng 10) |
| TC-NG-06 | Lệnh chờ SCALP bị hủy ngay ở T−60, lệnh chờ SWING ở T−3h; lệnh chờ mới có thời hạn ≤ thời điểm bắt đầu chặn của profile |
| TC-NG-07 | Lệnh lời 0,5R được dời SL hòa vốn tại T−15; lệnh lời 0,1R và lệnh lỗ giữ nguyên |
| TC-NG-08 | Trong [T−3h, T−60) SWING bị chặn còn SCALP vẫn vào được; từ T−60 cả hai bị chặn |
| TC-NG-09 | Sau T+15, spread vẫn > 1,5× median → vẫn chặn; tới T+60 vẫn chưa ổn định → về NORMAL kèm `NEWS_NORMALIZE_TIMEOUT` |
| TC-NG-10 | Gắn lại EA giữa cửa sổ tin → đọc lại calendar và vào đúng trạng thái, không vào lệnh lúc chờ đọc |
| TC-NG-11 (TC-020) | Tin chưa có actual hoặc forecast vẫn hiển thị đúng, không tính surprise |
| TC-NG-12 | `InpNewsGuardEnabled=false` → hành vi O-16, Dashboard hiện `NEWS_GUARD_DISABLED` |

Kiểm chứng trên terminal: ít nhất một tin HIGH của USD (ví dụ NFP thứ Sáu đầu tháng) phải đi đủ chuỗi trạng thái, có audit, và không có lệnh mới nào trong cửa sổ chặn.

## 13. Kế hoạch triển khai

1. Module thuần `News/NewsState.mqh`: máy trạng thái, gộp cửa sổ, ánh xạ đồng tiền, quyết định theo profile; kèm oracle Python và test (TC-NG-01, 03, 04, 08, 09).
2. Adapter `News/CalendarAdapter.mqh`: đọc MT5 Calendar, quy đổi UTC, theo dõi lần đọc gần nhất, xử lý UNKNOWN (TC-NG-02, 05, 11).
3. Nối vào vòng live (chặn và hệ số rủi ro), lệnh chờ REQ-021 (hủy và giới hạn thời hạn), Trade Manager (dời SL hòa vốn) (TC-NG-06, 07).
4. Dashboard tab News, pill ở header, `news_state.json`, audit (TC-NG-10, 12).
5. Compile, chạy test, deploy theo quy trình hiện có; kiểm chứng qua một tin HIGH thật trên demo.

Sau khi triển khai, cập nhật O-16 trong đặc tả tổng thể: News Guard thay cho `NEWS_UNAVAILABLE_ACCEPTED`. Các phần còn lại của News Center (surprise, AI News Interpreter, tin không có lịch) vẫn để mở.
