# EnterpriseEA qua MCP — cài cho Claude Code (demo và VPS)

MCP server `bridge/eea_mcp_server.py` cho Claude Code đọc trạng thái và nhật ký của EnterpriseEA. Bật thêm `--allow-control` thì Claude bật/tắt được bot. Server chỉ đọc và ghi file trong thư mục dữ liệu của EA (`MQL5/Files/EnterpriseEA`). Nó không đặt lệnh, không đụng vị thế, không cần mạng (trên VPS, kết nối đi qua SSH).

Server chỉ dùng thư viện chuẩn, cần Python 3.9 trở lên. Hai file đi kèm nhau: `eea_mcp_server.py` và `bot_journal.py`.

## Công cụ

| Công cụ | Làm gì |
|---|---|
| `health_check` | EA còn chạy không, các file có đúng chỗ và còn mới không, session, kill switch, lệnh bot bị kẹt. Nên gọi đầu tiên. |
| `bots_status` | 4 bot: Active, OFF/SHADOW/LIVE, lệnh mở, lãi/lỗ hôm nay, gần khớp, Portfolio Guard |
| `account_status` | balance/equity, live session (hạn, giới hạn), kill switch, pause, chính sách rủi ro, lãi/lỗ đã đóng hôm nay |
| `read_bot_log` | nhật ký bot `logs/bots-YYYYMM.jsonl`: tóm tắt theo bot và các dòng (lọc theo bot, số giờ, loại sự kiện) |
| `read_audit` | `logs/audit.jsonl` (bỏ nhịp RUNTIME_REFRESHED, lọc theo loại) |
| `vhedge_groups` | nhóm VHedge đang mở và các nhóm đã đóng gần nhất (U) |
| `bot_off` / `all_bots_off` | tắt bot ngay. Lệnh đang mở vẫn được quản lý. *chỉ khi có `--allow-control`* |
| `bot_on` → `bot_confirm` | xin bật, nhận mã 6 số (hạn 2 phút), rồi xác nhận. *chỉ khi có `--allow-control`* |

Lệnh điều khiển đi đường này:
1. Server ghi file vào `current/remote/bot_commands/` với `source: "MCP"`, rồi chờ EA trả lời (tối đa 45 giây; EA đọc lệnh mỗi lần timer chạy, `InpRuntimeRefreshSeconds` = 30 giây).
2. EA kiểm tra như lệnh Telegram: OPERATOR, đúng tài khoản và config, TTL, `mcp_sequence` lớn hơn lần trước (bộ đếm riêng, không lẫn với Telegram).
3. File MCP không được mang cờ xác thực của Telegram. Nếu có, EA từ chối.
4. Tắt nhận lệnh MCP: input `InpBotsMcpCommands=false`.

Dấu vết của mỗi lệnh:
- `logs/mcp.jsonl` (phía server): ai gửi, lý do, kết quả. Không lưu mã xác nhận.
- `logs/audit.jsonl`: `BOT_ENABLED` / `BOT_DISABLED` với `source: MCP`, hoặc `BOT_COMMAND_REJECTED`.
- `logs/bots-*.jsonl`: dòng `SWITCH … qua MCP`.

## Thư mục và file: ai tạo, lúc nào

Không cần tạo tay thư mục nào. EA tự tạo thư mục cha khi ghi file đầu tiên. Bảng dưới để biết thiếu file nào là bất thường:

| Đường dẫn (trong `MQL5/Files/EnterpriseEA`) | Ai ghi | Khi nào có |
|---|---|---|
| `current/bots_state.json` | EA | timer đầu tiên sau khi biết tài khoản (bootstrap từ input) |
| `current/bots_status.json` | EA | mỗi timer (30 giây). Cũ hơn 2 phút = EA không chạy |
| `current/live_status.json`, `account_snapshot.json` | EA | mỗi timer |
| `current/live_session.json`, `execution_controller_state.json` | EA | khi bấm Authorize session |
| `current/bots/vhedge_groups.txt`, `xrt_state.txt` | EA | lần lưu đầu của bot (có nhóm/lệnh hoặc ngày mới) |
| `logs/audit.jsonl` | EA | lúc khởi động |
| `logs/bots-YYYYMM.jsonl` | EA | lúc khởi động (dòng START), sau đó mỗi nến M30 (NEAR) |
| `current/remote/bot_commands/*.json` | gateway Telegram, MCP | khi có lệnh; EA đọc xong thì xóa |
| `current/remote/results/*.json` | EA | kết quả từng lệnh |
| `logs/mcp.jsonl` | MCP server | lệnh điều khiển đầu tiên |
| `../VHedge_<symbol>_<magic>.csv` (trong `MQL5/Files`) | EA | nhóm VHedge đầu tiên đóng |

`health_check` kiểm tra đúng danh sách này và nói rõ cái nào MISSING hoặc STALE.

## 1. Trên máy này (demo)

```bash
claude mcp add eea-demo -s user -- python "D:/Work/Private/Trading/EA-Enterprise/EnterpriseEA/bridge/eea_mcp_server.py" --root "C:/Users/Zbook Studio/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075/MQL5/Files/EnterpriseEA"
```

Muốn Claude bật/tắt được bot trên demo, thêm một server riêng có `--allow-control`:

```bash
claude mcp add eea-demo-control -s user -- python "D:/Work/Private/Trading/EA-Enterprise/EnterpriseEA/bridge/eea_mcp_server.py" --root "C:/Users/Zbook Studio/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075/MQL5/Files/EnterpriseEA" --allow-control --operator claude-laptop
```

Kiểm tra: `claude mcp list`. Trong một phiên Claude Code, hỏi "health_check EA demo".

## 2. Trên VPS (Linux, MT5 chạy Wine ở `/opt/qtl/data/mt5/terminal`)

**a. Đăng nhập SSH bằng key** (một lần). Từ máy này:

```bash
ssh qtl@<VPS_HOST> "python3 --version"
```

Lệnh phải chạy mà không hỏi mật khẩu. Nếu còn hỏi, thêm key vào `~/.ssh/authorized_keys` trên VPS. MCP chạy qua SSH không nhập mật khẩu được.

**b. Chép server lên VPS:**

```bash
ssh qtl@<VPS_HOST> "mkdir -p /opt/qtl/eea-mcp"
```

```bash
scp bridge/eea_mcp_server.py bridge/bot_journal.py qtl@<VPS_HOST>:/opt/qtl/eea-mcp/
```

**c. Thử trên VPS.** Lệnh dưới phải in ra một dòng JSON có `"serverInfo"`:

```bash
ssh qtl@<VPS_HOST> 'echo "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}" | python3 /opt/qtl/eea-mcp/eea_mcp_server.py --root /opt/qtl/data/mt5/terminal/MQL5/Files/EnterpriseEA'
```

Nếu báo `does not exist`, sửa đường dẫn `--root`. Tìm bằng lệnh `find /opt/qtl/data/mt5 -type d -name EnterpriseEA -path "*Files*"`.

**d. Quyền file.** User SSH phải:
- đọc được `MQL5/Files/EnterpriseEA`;
- ghi được `current/remote/bot_commands` và `logs`, nếu dùng control.

MT5 chạy trong Docker hoặc dưới user khác thì thêm `qtl` vào group sở hữu thư mục, hoặc `chmod -R g+rw` cho hai thư mục đó.

**e. Đăng ký trong Claude Code** (trên máy bạn). `-T` để SSH không mở terminal ảo:

```bash
claude mcp add eea-vps -s user -- ssh -T qtl@<VPS_HOST> python3 /opt/qtl/eea-mcp/eea_mcp_server.py --root /opt/qtl/data/mt5/terminal/MQL5/Files/EnterpriseEA
```

Bản có điều khiển, đặt tên riêng để dễ tắt:

```bash
claude mcp add eea-vps-control -s user -- ssh -T qtl@<VPS_HOST> python3 /opt/qtl/eea-mcp/eea_mcp_server.py --root /opt/qtl/data/mt5/terminal/MQL5/Files/EnterpriseEA --allow-control --operator claude-laptop
```

**f. Quyền trong Claude Code.** Cho phép sẵn các công cụ đọc. Luôn để công cụ bật bot ở chế độ hỏi. Ví dụ `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": ["mcp__eea-vps__health_check", "mcp__eea-vps__bots_status", "mcp__eea-vps__account_status",
              "mcp__eea-vps__read_bot_log", "mcp__eea-vps__read_audit", "mcp__eea-vps__vhedge_groups"],
    "ask": ["mcp__eea-vps-control__bot_on", "mcp__eea-vps-control__bot_confirm",
            "mcp__eea-vps-control__bot_off", "mcp__eea-vps-control__all_bots_off"]
  }
}
```

Không đưa `bot_confirm` vào `allow`. Bước xác nhận chỉ có nghĩa khi bạn tự duyệt.

## Cập nhật EA trên VPS

Bản EA có nhật ký bot và nguồn MCP là `builds/EnterpriseEA_Bots.ex5` từ commit này trở đi. Chép đè như hướng dẫn trong `builds/README.md`, rồi khởi động lại MT5 trên VPS. Input mới `InpBotsMcpCommands` mặc định `true`.

## Gỡ lỗi

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| `claude mcp list` báo failed | SSH còn hỏi mật khẩu hoặc host key. Chạy `ssh qtl@<VPS_HOST>` một lần bằng tay để chấp nhận key |
| `bots_status`: không có file | `--root` sai, EA chưa gắn, hoặc `InpBotsEnabled=false` |
| `stale: true` | MT5 hoặc EA đang dừng (cuối tuần vẫn chạy timer, nên cũ nghĩa là EA dừng thật) |
| lệnh `PENDING` mãi | EA không chạy, hoặc EA ghi vào thư mục khác (`InpDataRoot`) |
| `BOT_COMMAND_SOURCE_DISABLED` | `InpBotsMcpCommands=false` |
| `BOT_COMMAND_AUTH_IDENTITY_OR_TTL_INVALID` | đồng hồ VPS lệch (> 5 s), hoặc EA đổi tài khoản/config |
| `read_bot_log` trống | EA cũ chưa có nhật ký, hoặc vừa sang tháng mới mà chưa có sự kiện |
