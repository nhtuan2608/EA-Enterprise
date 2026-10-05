# AI Bridge v1

Script trung chuyển giữa EA và AI CLI (master specification mục 8, thiết kế `docs/superpowers/specs/2026-10-04-ai-bridge-and-news-review-design.md`).

- EA ghi yêu cầu vào `<MQL5/Files/EnterpriseEA>/ai/requests/`.
- Bridge kiểm tra yêu cầu, gọi `claude` (phân tích) hoặc `codex` (chẩn đoán), kiểm tra JSON trả về rồi ghi kết quả vào `ai/responses/`.
- EA đọc kết quả, kiểm tra lại, rồi hiển thị trên tab AI.
- AI ở **Level 0/1: chỉ báo cáo và khuyến nghị, không bao giờ đặt lệnh hay đổi cấu hình.**

## Yêu cầu

- Python 3.10+, không cần thư viện ngoài.
- `claude` CLI và/hoặc `codex` CLI đã đăng nhập sẵn. Bridge không giữ credential.

## Chạy trên Windows (thủ công)

```powershell
.\bridge\run_bridge.ps1
```

Script tự tìm thư mục `MQL5\Files\EnterpriseEA` của terminal. Muốn chỉ định thư mục khác thì dùng `-QueueRoot "<đường dẫn>"`. Muốn chạy một lượt rồi thoát thì thêm `-Once`.

## Chạy trên Ubuntu VPS (MT5 chạy bằng Wine)

1. Chép thư mục `bridge/` lên VPS, ví dụ `/opt/enterpriseea/bridge`.
2. Sửa `ai-bridge.service`:
   - `--queue-root` trỏ tới `~/.wine/drive_c/users/<user>/AppData/Roaming/MetaQuotes/Terminal/<id>/MQL5/Files/EnterpriseEA`;
   - `User=` là user đã đăng nhập `claude` / `codex`.
3. Cài và bật dịch vụ:
   ```bash
   sudo cp ai-bridge.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now ai-bridge
   ```
4. Đặt múi giờ của VPS (hoặc chỉnh `InpAiNewsReviewLocal` / `InpAiDiagnosticsLocal`). Lịch chạy của AI theo giờ máy chạy MT5.

## Cấu hình tùy chọn

Dùng `--config bridge.json`. Mọi khóa đều tùy chọn, ví dụ:

```json
{ "timeout_seconds": 120, "max_calls_per_day": 30,
  "commands": { "claude": ["claude", "-p", "--output-format", "text", "--tools", "", "--no-session-persistence"] } }
```

## An toàn

- **Kiểm tra yêu cầu:** đúng schema; loại request và action phải nằm trong whitelist; kích thước ≤ 50 KB; deadline còn hạn.
- **Text từ dữ liệu là dữ liệu, không phải chỉ dẫn:** bị lọc ký tự điều khiển và cắt độ dài trước khi đưa vào prompt.
- **Câu trả lời của AI bị loại** nếu không đúng JSON, thiếu trường, hoặc có action ngoài danh sách cho phép.
- **Giới hạn và ngắt:** tối đa 30 lần gọi mỗi ngày; 3 lỗi liên tiếp thì ngừng gọi 30 phút.
- **Provider bị hạn chế:** `claude` chạy không có tool; `codex` chạy với sandbox chỉ đọc; cả hai chạy trong thư mục tạm trống.
- **Log:** `logs/ai_bridge.jsonl`. Trạng thái: `ai/bridge_heartbeat.json`; EA hiện `ONLINE` khi heartbeat mới hơn 2 phút.
