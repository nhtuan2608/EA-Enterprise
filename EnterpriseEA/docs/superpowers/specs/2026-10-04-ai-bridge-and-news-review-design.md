# AI Bridge v1 và tự động kiểm tra số liệu tin

Ngày 04/10/2026. Trạng thái: **DESIGN — chưa sửa source**. Chờ người dùng chốt các quyết định ở mục 11.

Nguồn: master specification v1.4 mục 8 (MCP AI Bridge), 8.3 (authority levels), 8.4 (policy flow), 8.5–8.6 (request/response contract), 8.7 (AI-SEC-01..06), 9.1 (tab AI/NEWS), mục 13 (AIG-01..07), REQ-008, REQ-012, TC-021 đến TC-024; News Guard và News Reaction Recorder (04/10/2026).

---

## 1. Vấn đề

- Bộ ghi phản ứng tạo ra số liệu theo từng tin và từng symbol. Hiện người dùng phải **tự đọc** thống kê, tự phát hiện số liệu bất thường, rồi tự quyết định có đổi khoảng chặn tin hay không.
- Phần AI trong đặc tả (REQ-008, REQ-012) **chưa được xây**: tab AI trên Dashboard vẫn là placeholder.

## 2. Mục tiêu

1. **Tự động kiểm tra số liệu tin**, theo hai lớp:
   - **Lớp xác định (deterministic, chạy trong EA):** kiểm tra chất lượng và sự nhất quán của số liệu. Lớp này không cần AI và luôn chạy.
   - **Lớp AI:** đọc số liệu đã kiểm tra, viết báo cáo dễ hiểu, chỉ ra điều đáng chú ý và đề xuất chỉnh khoảng chặn.
2. **Dựng AI Bridge tối thiểu** đúng đặc tả mục 8: EA gửi ngữ cảnh có cấu trúc, AI trả lời theo schema, EA kiểm tra rồi hiển thị và ghi audit.
3. **Đo hiệu quả của AI** (REQ-012): mọi cảnh báo và khuyến nghị đều được lưu và chấm điểm về sau bằng kết quả thực tế.

## 3. Ranh giới bắt buộc

- **AI bắt đầu ở Level 0 (Observer)**, chỉ đọc, phân tích và báo cáo; sau đó lên **Level 1 (Advisor)**: cảnh báo, khuyến nghị, xếp hạng. **AI không vào lệnh, không đổi rủi ro, không đổi input.** Level 2 (chỉ được giảm rủi ro hoặc chặn setup) chỉ xét sau khi qua AIG-01..07; Level 3 nằm ngoài phạm vi.
- Mọi khuyến nghị (kể cả khoảng chặn tin) **chỉ là đề xuất**. Người dùng tự đổi input nếu đồng ý (giống R3 của bộ ghi).
- EA **không bao giờ chờ AI**: không gọi AI trong OnTick, không chặn OnTimer. AI chậm, lỗi hay offline thì EA vẫn chạy deterministic như hiện tại (TC-021).
- **Bảo mật (AI-SEC-01..06):**
  - chỉ gửi các trường trong allowlist; không gửi account number, mật khẩu, file cấu hình;
  - tên tin và mọi text từ calendar được coi là dữ liệu, được escape và giới hạn độ dài (chống prompt injection, TC-023);
  - response sai schema, sai `request_id`, quá TTL hoặc chứa action ngoài whitelist thì bị loại và ghi log (TC-022);
  - có circuit breaker: lỗi liên tiếp thì ngừng gọi AI một thời gian.

## 4. Kiến trúc

```
EA (MQL5)                         Bridge (Python, ngoài MT5)              Provider
─────────                         ──────────────────────────              ────────
ai/requests/<id>.json   ──►   đọc queue, kiểm tra schema/allowlist,  ──►  claude -p  (phân tích)
                              dựng prompt, gọi CLI có timeout              codex exec (chẩn đoán)
ai/responses/<id>.json  ◄──   kiểm tra JSON trả về theo schema,      ◄──
                              ghi response + audit của bridge
EA đọc response trên timer, kiểm tra lại request_id / TTL / schema / whitelist,
lưu report, hiển thị trên tab AI và tab News, ghi audit.
```

- **File queue** nằm trong `MQL5/Files/EnterpriseEA/ai/`. MQL5 không được phép tự chạy process ngoài nếu không dùng DLL, nên file queue là cách an toàn và đúng đặc tả 8.1.
- **Bridge** là một script Python nhỏ, nằm trong repo (`EnterpriseEA/bridge/ai_bridge.py`), do Windows Task Scheduler khởi động khi người dùng đăng nhập. Bridge chỉ làm transport, gọi CLI, kiểm tra schema, xử lý timeout, quản lý hàng đợi và audit. Bridge không có engine phân tích thị trường riêng (đặc tả 8.1).
- **Provider:**
  - `claude` CLI cho phân tích tin, thị trường và lệnh;
  - `codex` CLI cho chẩn đoán log, lỗi và cấu hình (đặc tả 8.2).
  - Cả hai đã cài sẵn trên máy. Người dùng cần đăng nhập sẵn, vì bridge không giữ credential.
- **Giới hạn chi phí:** số lần gọi tối đa mỗi ngày, và mỗi request có kích thước tối đa (mục 11, Q4).

## 5. Request và response (theo đặc tả 8.5–8.6)

**Request** (EA ghi):
```json
{ "schema_version": "1.0", "request_id": "uuid", "request_type": "NEWS_DATA_REVIEW",
  "created_at_utc": "...", "deadline_ms": 120000, "provider": "claude",
  "allowed_actions": ["REPORT", "WARN", "RECOMMEND_WINDOW_CHANGE"],
  "context": { ... chỉ các trường trong allowlist của request_type ... } }
```

**Response** (bridge ghi sau khi đã kiểm tra):
```json
{ "schema_version": "1.0", "request_id": "same", "provider": "claude", "created_at_utc": "...",
  "valid_until_utc": "...", "status": "OK", "summary": "…", "findings": [ { "code": "...", "severity": "INFO|WARN", "detail": "...", "evidence_refs": ["news_reaction:<key>"] } ],
  "recommendations": [ { "action": "RECOMMEND_WINDOW_CHANGE", "target": "USD 10-Year Note Auction", "proposal": "pre 15m", "reason_codes": ["LOW_REACTION"] } ],
  "confidence_label": "MEDIUM" }
```

- `confidence_label` chỉ để giao tiếp, không phải xác suất thắng.
- V1 không cho AI trả giá, lot hay lệnh.
- Action ngoài `allowed_actions` làm cả response bị loại.

## 6. Các loại request của v1

| Loại | Khi nào | AI làm gì | Provider |
|---|---|---|---|
| `NEWS_DATA_REVIEW` | Mỗi ngày 07:00 VN, và ngay sau khi backfill xong | Đọc kết quả kiểm tra xác định (mục 7) và thống kê theo cụm tin × symbol; viết báo cáo; đề xuất khoảng chặn cho từng nhóm tin | claude |
| `NEWS_EVENT_REVIEW` | Khi bộ ghi vừa ghi xong một cụm tin (T + 4h05m) | Giải thích ngắn tin đó có cấu trúc, so với lịch sử của chính tin đó, nêu điểm bất thường | claude |
| `PRE_SESSION_REVIEW` | Trước London (13:30 VN) và trước New York (18:30 VN) | Tóm tắt trạng thái symbol, vùng S02, exposure, tin sắp tới kèm phản ứng lịch sử; cảnh báo | claude |
| `TRADE_REVIEW` | Khi Trade Manager đánh dấu UNDERPERFORMING hoặc lệnh đóng bất thường | So đường giá thực tế với đường kỳ vọng; khuyến nghị giữ / giảm / xem lại (chỉ khuyến nghị) | claude |
| `EA_DIAGNOSTICS` | Mỗi ngày 06:30 VN | Đọc audit 24 giờ: lỗi, DEGRADED, refresh thất bại, kết quả gửi lệnh không rõ; chẩn đoán nguyên nhân | codex |
| `ASK_AI` | Người dùng bấm trên tab AI | Trả lời theo loại câu hỏi đã chọn, cùng ngữ cảnh | theo loại |

## 7. Tự động kiểm tra số liệu tin (lớp xác định, chạy trong EA)

Chạy mỗi khi có bản ghi mới và trước mỗi `NEWS_DATA_REVIEW`. Kết quả ghi ở `current/news_data_health.json` và hiển thị trên tab News. Không cần AI.

| Mã kiểm tra | Phát hiện | Mức |
|---|---|---|
| `NDH_INCOMPLETE_RATE` | Tỷ lệ bản ghi `INCOMPLETE_*` theo symbol > 10% | WARN |
| `NDH_TIME_ALIGNMENT` | Nến M1 biến động mạnh nhất quanh tin HIGH thường nằm lệch T đúng ±60 phút → nghi sai múi giờ hoặc DST của server (đặc biệt với backfill) | WARN |
| `NDH_SPREAD_SOURCE` | Phần lớn bản ghi dùng spread từ M1 thay vì tick → thời gian hồi spread kém tin cậy | INFO |
| `NDH_OUTLIER` | \|move_15m\| > 10 ATR hoặc spread peak > ×30 → nghi dữ liệu xấu, cần xem tay | WARN |
| `NDH_CLUSTER_CONSISTENCY` | Cùng một cụm nhưng các tin trong cụm cho đường giá khác nhau → lỗi ghi | WARN |
| `NDH_BACKFILL_STALL` | Con trỏ backfill không tiến trong 2 giờ | WARN |
| `NDH_SAMPLE_COVERAGE` | Nhóm tin sắp tới có < 6 mẫu → chưa có khoảng chặn gợi ý | INFO |
| `NDH_SUGGESTION_GAP` | Khoảng chặn gợi ý khác khoảng đang áp > 30 phút, với n ≥ 6 | INFO, gửi AI xem |
| `NDH_GUARD_EFFECT` | Thống kê lệnh được dời SL hòa vốn trước tin: tỷ lệ SL ban đầu có bị chạm (`be_would_have_hit_sl`) | INFO |

## 8. Hiển thị

- **Tab AI** (thay placeholder):
  - trạng thái bridge: online / offline, lần gọi gần nhất, circuit breaker;
  - báo cáo gần nhất của từng loại request;
  - danh sách cảnh báo còn hiệu lực theo TTL;
  - nút **ASK AI**, **REFRESH**, **DETAIL**, không chặn UI khi request đang chạy.
- **Tab News:** dòng "Data health" (số WARN/INFO) và tóm tắt mới nhất của AI, kèm các đề xuất khoảng chặn đang chờ người dùng quyết định.
- **Audit:** `AI_REQUEST_QUEUED`, `AI_RESPONSE_ACCEPTED`, `AI_RESPONSE_REJECTED` (kèm lý do), `AI_CIRCUIT_OPEN`, `NEWS_DATA_HEALTH`.

## 9. Đo hiệu quả AI (REQ-012, AIG-01..07)

- Mọi cảnh báo và khuyến nghị được lưu vào `logs/ai_recommendations.jsonl` cùng `request_id`.
- **Chấm điểm tự động về sau:**
  - **Cảnh báo về tin:** chấm bằng bản ghi phản ứng thực tế, ví dụ cảnh báo "biến động mạnh" có thật sự xảy ra không.
  - **Đề xuất khoảng chặn:** sau khi người dùng áp đề xuất, so số lần bị chặn, trượt giá và biến động so với trước khi áp.
  - **Khuyến nghị cho lệnh:** so với kết quả lệnh nếu làm theo và nếu không làm theo (shadow).
- Báo cáo hiệu quả hàng tuần nằm trên tab AI. Chỉ khi đủ mẫu và qua AIG-01..07 mới xét lên Level 2. Việc lên Level 2 là quyết định riêng của người dùng.

## 10. Telegram (REQ-018–020)

Không thuộc đợt này. Bridge được thiết kế để sau này đẩy báo cáo AI sang Telegram mà không phải đổi gì phía EA.

## 11. Quyết định cần người dùng chốt

| ID | Câu hỏi | Đề xuất |
|---|---|---|
| Q1 | Mức quyền AI ban đầu | Level 0 (chỉ báo cáo) trong 2 tuần, sau đó Level 1 (cảnh báo / khuyến nghị) |
| Q2 | Các loại request bật ở v1 | `NEWS_DATA_REVIEW`, `NEWS_EVENT_REVIEW`, `EA_DIAGNOSTICS`, `ASK_AI`. `PRE_SESSION_REVIEW` và `TRADE_REVIEW` bật ở đợt 2 |
| Q3 | Cách chạy bridge | Windows Task Scheduler chạy khi đăng nhập, tự khởi động lại khi lỗi |
| Q4 | Giới hạn chi phí | Tối đa 30 lần gọi/ngày; request ≤ 50 KB; timeout 120 giây; circuit breaker sau 3 lỗi liên tiếp, nghỉ 30 phút |
| Q5 | Lịch chạy | `NEWS_DATA_REVIEW` 07:00 VN, `EA_DIAGNOSTICS` 06:30 VN |
| Q6 | Ngôn ngữ báo cáo | Tiếng Việt |

## 12. Kiểm thử

| ID | Kịch bản → kết quả mong đợi |
|---|---|
| TC-AI-01 (TC-021) | Bridge tắt hoặc AI quá timeout → EA vẫn chạy, tab AI hiện OFFLINE, không có request nào bị kẹt |
| TC-AI-02 (TC-022) | Response sai JSON, sai `request_id`, quá TTL hoặc có action ngoài whitelist → bị loại, audit `AI_RESPONSE_REJECTED` |
| TC-AI-03 (TC-023) | Tên tin chứa câu lệnh độc hại → vẫn chỉ là dữ liệu, đã escape, không đổi hành vi |
| TC-AI-04 (TC-024) | Response đề xuất tăng rủi ro hoặc vào lệnh → bị loại ngay tại bridge và EA |
| TC-AI-05 | Request chỉ chứa trường trong allowlist; không có account number hay đường dẫn file |
| TC-AI-06 | Circuit breaker mở sau 3 lỗi liên tiếp, tự đóng sau 30 phút |
| TC-AI-07 | Kiểm tra xác định: tạo dữ liệu lệch ±60 phút → `NDH_TIME_ALIGNMENT`; outlier → `NDH_OUTLIER` |
| TC-AI-08 | Chi phí: vượt 30 lần gọi/ngày → request tiếp theo bị hoãn sang ngày sau, có audit |
| TC-AI-09 | Kiểm tra tĩnh: EA và bridge không có đường nào để AI gửi lệnh hay đổi input |

## 13. Kế hoạch triển khai

1. **Lớp kiểm tra số liệu tin xác định** trong EA: `news_data_health.json` và hiển thị trên tab News (TC-AI-07). Bước này có giá trị ngay cả khi chưa có AI.
2. **Schema** request/response (`schemas/ai-request.schema.json`, `ai-response.schema.json`) và phía EA: ghi request, đọc và kiểm tra response, audit, circuit breaker (TC-AI-01, 02, 04, 06).
3. **Bridge Python:** đọc queue, áp allowlist, dựng prompt, gọi `claude` / `codex` có timeout, kiểm tra schema, kiểm soát chi phí, chạy bằng Task Scheduler; kèm test riêng (TC-AI-03, 05, 08).
4. **Các request của v1** và tab AI trên Dashboard.
5. **Lưu khuyến nghị** và chấm điểm hiệu quả (REQ-012).
6. Compile, test, deploy; chạy Level 0 trong 2 tuần rồi đánh giá.
