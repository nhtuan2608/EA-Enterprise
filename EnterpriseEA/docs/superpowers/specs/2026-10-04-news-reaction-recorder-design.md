# Bộ ghi phản ứng giá sau tin (News Reaction Recorder)

Ngày 04/10/2026. Trạng thái: **IMPLEMENTED** (`News/NewsReaction.mqh`, `News/NewsReactionRecorder.mqh`). Người dùng đồng ý R1–R6 ở mục 12 theo đề xuất.

**Bổ sung khi triển khai (04/10/2026):**
- **Mức ảnh hưởng.** Mỗi bản ghi có trường `impact`, theo yêu cầu của người dùng:
  - `DIRECT` (đỏ): tin của chính đồng tiền trong cặp.
  - `INDIRECT` (vàng): tin HIGH của một đồng tiền lớn khác thuộc nhóm lãi suất, lạm phát, việc làm hoặc GDP (sector `MONEY`, `PRICES`, `JOBS`, `GDP` của MT5). Ví dụ lãi suất ECB với XAUUSD và USDJPY. Nhờ vậy có số liệu đo được mức ảnh hưởng gián tiếp, trong đó có ảnh hưởng tới vàng.
- **Cụm tin cùng giờ** (người dùng yêu cầu 04/10/2026). Các tin HIGH ra cùng thời điểm và cùng ảnh hưởng tới một symbol có chung một đường giá, ví dụ NFP + Unemployment Rate + Average Hourly Earnings. Mỗi tin vẫn có bản ghi riêng; ngoài ra mỗi bản ghi lưu thêm:
  - `cluster_events`: danh sách tin trong cụm, đã sắp xếp;
  - `cluster_size`;
  - `cluster_lead`;
  - `group`: tên cụm × symbol.

  Thống kê, khoảng chặn gợi ý và phần "Gần đây" chỉ dùng bản ghi **dẫn đầu** của cụm, nên mỗi cụm được tính một lần. Tab News gộp các tin cùng giờ thành một dòng (`+N`) và hiện thống kê của cả cụm.
- **Khác bản thiết kế:**
  - Tác động lên lệnh ghi số lệnh thoát trong [T, T+60] (`exits_in_window`), chưa có trượt giá chi tiết từng SL.
  - Số tín hiệu bị chặn và số lệnh chờ bị hủy chỉ được đếm khi EA chạy liên tục trong cửa sổ tin; nếu gỡ EA giữa chừng thì phần này không đầy đủ.
  - Backfill dùng độ lệch giờ server hiện tại. Vì vậy các tin trước lần đổi giờ của broker có thể lệch 1 giờ, cần lưu ý khi đọc số liệu cũ.

Nguồn: master specification v1.4 mục 6.3 (dữ liệu quản lý lệnh), 7.1 (Surprise Calculator), 7.3 (Surprise), REQ-007, REQ-012, TC-020; thiết kế News Guard (`2026-10-04-market-information-and-news-guard-design.md`).

---

## 1. Vấn đề

News Guard hiện chỉ dùng **giờ ra tin**: chặn vào lệnh trước và sau tin, rồi chờ spread và biến động ổn định lại. Actual / forecast / previous chỉ được hiển thị. Hệ thống chưa ghi lại:

- tin ra tốt hay xấu hơn dự báo, và mức độ bất ngờ;
- giá thực sự phản ứng thế nào, mạnh tới đâu, kéo dài bao lâu;
- spread giãn tới mức nào, bao lâu mới trở lại bình thường;
- các lệnh của EA bị ảnh hưởng ra sao.

Thiếu những số liệu này thì không có cơ sở để chỉnh khoảng chặn cho từng loại tin. Hiện mọi tin HIGH đều bị chặn giống nhau, từ NFP tới đấu giá trái phiếu.

## 2. Mục tiêu và giới hạn

**Mục tiêu:**
1. Với mỗi tin HIGH và mỗi symbol đang chọn bị tin đó ảnh hưởng, ghi một **bản ghi phản ứng** gồm kết quả tin, đường giá, spread và tác động lên lệnh của EA.
2. Tổng hợp theo **loại tin × symbol** để biết loại tin nào làm giá chạy mạnh hay yếu.
3. Hiển thị trên tab News và đưa ra **khoảng chặn gợi ý** cho từng loại tin.

**Giới hạn (bắt buộc theo đặc tả):**
- **Chỉ đo, không giao dịch.** Bộ ghi không tạo tín hiệu, không đổi rủi ro, không đặt hay đóng lệnh.
- **Không suy ra BUY/SELL từ dấu của surprise** (đặc tả 7.3). Hướng phản ứng chỉ được ghi lại như một quan sát.
- **Không tự đổi tham số.** Khoảng chặn gợi ý chỉ là đề xuất; người dùng tự đổi input nếu đồng ý. Ngưỡng phải được version hóa, AI hay Telegram không được sửa.
- **Không tạo surprise chuẩn hóa giả (TC-020):** thiếu actual, thiếu forecast hoặc chưa đủ lịch sử thì không tính.

## 3. Nguồn dữ liệu (đều có sẵn trong MT5)

| Dữ liệu | Hàm MQL5 | Ghi chú |
|---|---|---|
| Tin, giờ tin, actual / forecast / previous / revised | `CalendarValueHistory`, `CalendarEventById` | Đang dùng cho News Guard |
| Lịch sử các lần công bố trước của cùng một tin | `CalendarValueHistoryByEvent(event_id, …)` | Dùng tính độ lệch chuẩn của surprise |
| Đường giá quanh tin | `CopyRates(symbol, PERIOD_M1, …)` | Nến M1 từ T − 30 phút tới T + 4 giờ |
| Spread chi tiết quanh tin | `CopyTicksRange(symbol, …, T − 30m, T + 60m)` | Nếu broker không có tick lịch sử thì dùng spread của nến M1 và ghi `SPREAD_SOURCE=M1` |
| ATR tham chiếu | Nến M5 trước tin | ATR14 (M5) tại T − 5 phút, giá trị đã chốt trước khi tin ra |
| Lệnh của EA | Trade Manager, REQ-021 tracker, deal history | Lệnh mở, lệnh chờ bị hủy, SL bị khớp và trượt giá |
| Trạng thái News Guard | Audit `NEWS_STATE_CHANGED` | Thời điểm về NORMAL, có timeout hay không |

**Không đo theo thời gian thực.** Mỗi bản ghi được tính **sau khi** cửa sổ đo đã qua (mặc định T + 4 giờ 5 phút), hoàn toàn từ dữ liệu lịch sử. Cách này đơn giản, cho cùng kết quả dù EA chạy liên tục hay vừa gắn lại, và không làm nặng timer lúc đang có tin.

## 4. Kết quả tin (surprise)

| Trường | Cách tính |
|---|---|
| `actual`, `forecast`, `previous`, `revised_previous` | Từ calendar tại thời điểm tính bản ghi |
| `surprise_raw` | actual − forecast (chỉ khi có cả hai) |
| `surprise_side` | `ABOVE` / `INLINE` / `BELOW`. INLINE khi \|actual − forecast\| ≤ một nửa đơn vị làm tròn của tin |
| `surprise_std` | (actual − forecast) / σ, với σ là độ lệch chuẩn của (actual − forecast) qua **≥ 8 lần công bố trước** của cùng tin. Không đủ 8 lần thì để trống và ghi `SURPRISE_HISTORY_INSUFFICIENT` |
| `surprise_quality` | `OK`, `NO_FORECAST`, `NO_ACTUAL`, `SURPRISE_HISTORY_INSUFFICIENT` |

Ghi chú: "cao hơn dự báo" không đồng nghĩa với tốt hay xấu cho đồng tiền. Ví dụ tỷ lệ thất nghiệp cao hơn là xấu, còn CPI cao hơn có thể bị coi là tốt cho USD. Vì vậy bộ ghi chỉ ghi phía (side) của surprise, không gán ý nghĩa tăng hay giảm giá.

## 5. Phản ứng giá (cho từng symbol bị ảnh hưởng)

Mốc giá **P0** = giá đóng cửa của nến M1 kết thúc ngay trước T. **ATR_ref** = ATR14 (M5) tại T − 5 phút.

| Nhóm | Trường | Ý nghĩa |
|---|---|---|
| Biến động theo mốc | `move_1m`, `move_5m`, `move_15m`, `move_60m`, `move_240m` | Giá đóng nến M1 tại T + k trừ P0, lưu ba đơn vị: giá, point, bội số ATR_ref |
| Biên độ | `max_up_60m`, `max_down_60m` | Đỉnh cao nhất − P0 và P0 − đáy thấp nhất trong 60 phút, theo ATR_ref |
| Hướng | `first_direction` | Dấu của `move_5m` (UP / DOWN / FLAT khi nhỏ hơn 0,1×ATR_ref) |
| Đảo chiều | `reversal_60m` | Hướng 5 phút và hướng 60 phút ngược nhau, mỗi bên ≥ 0,3×ATR_ref |
| Mức tiếp diễn | `follow_through` | move_60m / move_5m (khi \|move_5m\| ≥ 0,3×ATR_ref) |
| Thời gian tới đỉnh | `bars_to_extreme_60m` | Số nến M1 tới điểm xa P0 nhất |
| Thanh khoản | `tick_volume_ratio_15m` | Tick volume 15 phút sau tin chia cho trung bình 15 phút cùng giờ của 5 ngày trước |

Một bản ghi phản ứng có thể dùng ngay cho SCALP (mốc 1–60 phút) và SWING (mốc 60–240 phút).

## 6. Spread và trạng thái ổn định

| Trường | Ý nghĩa |
|---|---|
| `spread_pre_median` | Median spread trong [T − 30, T − 5] phút |
| `spread_peak` / `spread_peak_ratio` | Spread lớn nhất trong [T − 1, T + 15] phút và bội số so với spread trước tin |
| `spread_recovery_min` | Số phút từ T tới khi spread về ≤ 1,5× spread trước tin |
| `guard_normal_at_min` | Số phút từ T tới khi News Guard về NORMAL; ghi kèm có `NEWS_NORMALIZE_TIMEOUT` hay không |
| `spread_source` | `TICKS` hoặc `M1` |

## 7. Tác động lên lệnh của EA

| Trường | Ý nghĩa |
|---|---|
| `positions_open` | Các lệnh EA đang mở trên symbol tại T: ticket, profile, R tại T − 15 phút, R tại T + 60 phút, đã dời SL hòa vốn trước tin chưa |
| `stops_hit` | SL bị khớp trong [T, T + 60]: giá SL, giá khớp, trượt giá (point và R) |
| `pending_cancelled` | Lệnh chờ bị News Guard hủy trước tin |
| `entries_blocked` | Số candidate bị chặn trong cửa sổ tin, theo profile |
| `would_have_hit_sl` | Với các lệnh đã dời SL hòa vốn trước tin: SL ban đầu có bị chạm trong 60 phút không. Dùng để đánh giá việc dời SL hòa vốn có đáng làm không |

## 8. Tổng hợp và khoảng chặn gợi ý

Gom theo **(tên tin, đồng tiền) × symbol**, ví dụ "USD Nonfarm Payrolls × XAUUSD":

- số mẫu `n`;
- median và p80 của \|move_15m\|, \|move_60m\| theo ATR;
- median `spread_peak_ratio`, median `spread_recovery_min`;
- tỷ lệ đảo chiều trong 60 phút;
- tỷ lệ SL bị khớp có trượt giá.

**Khoảng chặn gợi ý** chỉ được tính khi n ≥ 6:

- **Sau tin:** p80 của max(`spread_recovery_min`, thời gian để biến động trở lại ≤ 1×ATR_ref mỗi 5 phút), làm tròn lên 5 phút.
- **Trước tin:** giữ theo D1 (SCALP 60 phút, SWING 3 giờ). Nếu nhóm tin có p80 \|move_60m\| < 0,5×ATR_ref thì gợi ý **giảm**, tức có thể không cần chặn.

Gợi ý chỉ hiển thị; không input nào tự thay đổi.

## 9. Lưu trữ, khôi phục, audit

- **`logs/news_reactions.jsonl`:** mỗi dòng một bản ghi (tin × symbol). Khóa duy nhất là `calendar_value_id + symbol`; ghi lại cùng khóa thì bỏ qua (idempotent).
- **`current/news_reaction_stats.json`:** bảng tổng hợp ở mục 8, tính lại mỗi khi có bản ghi mới.
- **Đọc lịch:** lùi lại **48 giờ** cho bộ ghi (News Guard vẫn dùng 6 giờ). Nhờ vậy, gỡ EA ra rồi gắn lại trong vòng 2 ngày vẫn bù được bản ghi còn thiếu.
- **Audit:** `NEWS_REACTION_RECORDED` (tin, symbol, move_15m theo ATR, spread_peak_ratio) và `NEWS_REACTION_INCOMPLETE` khi thiếu dữ liệu nến hoặc tick (ghi rõ lý do, không bịa số).

## 10. Dashboard (tab News)

- Thêm phần **"Gần đây"**: 5 bản ghi mới nhất, mỗi dòng gồm tin, symbol, phía surprise, move 5m / 60m theo ATR, spread peak, thời gian về NORMAL.
- Mỗi tin sắp tới hiện thêm **thống kê lịch sử** của nhóm tin đó cho symbol đang xem. Ví dụ: `NFP × XAUUSD: n=8, 15m 2,1 ATR, spread ×4,2, ổn định sau 22 phút`.
- Hiện **khoảng chặn gợi ý** cạnh khoảng chặn đang áp, khác nhau thì tô màu.

## 11. Nạp sẵn dữ liệu lịch sử (backfill)

MT5 có sẵn lịch sử calendar và nến M1 nhiều tháng, nên bộ ghi có thể tính ngay phản ứng của các tin HIGH trong **12 tuần gần nhất** khi khởi động lần đầu. Việc này chạy theo từng đợt nhỏ trên timer để không làm chậm EA. Lợi ích là có thống kê dùng được ngay thay vì chờ nhiều tuần. Tick cũ có thể không còn; khi đó spread lấy từ nến M1 và ghi `spread_source=M1`. Các bản ghi backfill có `source=BACKFILL` và không có phần tác động lên lệnh (mục 7).

## 12. Quyết định cần người dùng chốt

| ID | Câu hỏi | Đề xuất |
|---|---|---|
| R1 | Các mốc đo sau tin | 1, 5, 15, 60, 240 phút (240 phút phục vụ SWING) |
| R2 | Nạp sẵn lịch sử | Có, 12 tuần |
| R3 | Khoảng chặn gợi ý | Chỉ hiển thị; người dùng tự đổi input |
| R4 | Điều kiện tính surprise chuẩn hóa | ≥ 8 lần công bố trước có cả actual và forecast |
| R5 | Symbol được ghi | Các symbol đang chọn bị tin ảnh hưởng (theo đồng tiền, như News Guard) |
| R6 | Số mẫu tối thiểu để gợi ý | n ≥ 6 |

## 13. Kiểm thử

| ID | Kịch bản → kết quả mong đợi |
|---|---|
| TC-NR-01 | Nến M1 tổng hợp quanh T: move_1/5/15/60/240m, max up/down, first_direction, reversal tính đúng theo ATR_ref |
| TC-NR-02 (TC-020) | Thiếu actual hoặc forecast → không có surprise_raw / surprise_std; surprise_quality ghi rõ lý do |
| TC-NR-03 | Chỉ có 7 lần công bố trước → `SURPRISE_HISTORY_INSUFFICIENT`; đủ 8 lần → σ và surprise_std đúng |
| TC-NR-04 | Ghi trùng cùng khóa (gắn lại EA) → không tạo dòng thứ hai |
| TC-NR-05 | Gắn lại EA sau T + 4 giờ trong vòng 48 giờ → bản ghi được bù đầy đủ |
| TC-NR-06 | Không có tick lịch sử → spread lấy từ M1, `spread_source=M1` |
| TC-NR-07 | Thiếu nến M1 trong cửa sổ đo → `NEWS_REACTION_INCOMPLETE`, không có số giả |
| TC-NR-08 | Lệnh đã dời SL hòa vốn trước tin: `would_have_hit_sl` đúng theo SL ban đầu |
| TC-NR-09 | Tổng hợp: median / p80 đúng; n < 6 thì không có gợi ý |
| TC-NR-10 | Bộ ghi không gọi bất kỳ hàm gửi lệnh nào (kiểm tra tĩnh) |
| TC-NR-11 | Backfill chạy theo đợt, không vượt ngân sách thời gian mỗi timer; dừng giữa chừng rồi tiếp tục đúng chỗ |

## 14. Kế hoạch triển khai

1. Module thuần `News/NewsReaction.mqh`: tính surprise, các chỉ số phản ứng và tổng hợp từ dữ liệu đã cho; oracle Python và test (TC-NR-01..03, 09).
2. Adapter: đọc M1 / tick / lịch sử calendar, quyết định thời điểm tính, ghi `news_reactions.jsonl` theo khóa (TC-NR-04..07).
3. Nối tác động lên lệnh từ Trade Manager, REQ-021 tracker và deal history (TC-NR-08).
4. Backfill 12 tuần theo đợt (TC-NR-11).
5. Dashboard tab News: phần "Gần đây", thống kê theo nhóm tin, khoảng chặn gợi ý.
6. Compile, test, deploy theo quy trình hiện có; kiểm chứng bằng cụm tin PMI/ISM thứ Hai 05/10 và Jobless Claims thứ Năm 08/10.

## 15. Liên quan về sau

- **AI News Interpreter (đặc tả 7.1, REQ-008):** bản ghi phản ứng và thống kê là ngữ cảnh có cấu trúc cho AI giải thích tin, không phải lệnh.
- **REQ-012 (đo hiệu quả AI):** cảnh báo của AI về tin có thể được chấm điểm bằng chính các bản ghi này.
- **Tinh chỉnh News Guard:** sau đủ mẫu, có thể đưa ra khoảng chặn theo từng nhóm tin thay cho khoảng chặn chung. Đó sẽ là một quyết định riêng của người dùng.
