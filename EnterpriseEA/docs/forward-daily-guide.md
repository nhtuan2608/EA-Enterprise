# Theo dõi forward hằng ngày (lệnh ảo, không đặt lệnh)

Script `research/forward/daily_forward.py` dựng lại từ đầu, mỗi lần chạy, các lệnh ảo của hai manh mối chỉ còn xác nhận được bằng dữ liệu mới:

| Manh mối | Từ ngày | Nguồn |
|---|---|---|
| Nến V M30 (G118 ứng viên A, stop ± 2 ATR) | 10/10/2026 | G118, G134 |
| CtxBox (G106), M5 / M15 / M30 / H1 | 12/10/2026 | G106 |

Script **chỉ đọc** nến XAUUSD từ terminal MT5 qua thư viện Python `MetaTrader5` (`copy_rates_from_pos`). Nó không gửi gì vào terminal.

**Kết quả:**
- `research/forward/forward_daily.md`: tóm tắt và từng lệnh;
- `research/forward/forward_history.csv`: mỗi lần chạy thêm một dòng cho mỗi mục, để xem diễn biến theo ngày.

Chạy tay: `research/forward/run_daily_forward.bat` (Windows), hoặc `python research/forward/daily_forward.py` trong thư mục `research/long`.

> Lưu ý: nếu terminal chưa mở, `MetaTrader5.initialize()` sẽ **tự mở** terminal. Terminal mở theo cách này nạp lại profile, kể cả EA đang gắn trên chart. Chỉ đặt lịch trên máy mà điều đó chấp nhận được (terminal vốn chạy suốt), hoặc mở terminal trước giờ chạy.

## Cách 1 (khuyến nghị): máy Windows có MT5 (máy demo / laptop)

Thư viện `MetaTrader5` chỉ chạy với Python cho Windows, nên đây là cách đơn giản nhất.

Tạo lịch chạy 07:00 mỗi ngày bằng **Task Scheduler**: mở PowerShell **của người dùng** (không cần quyền admin) rồi chạy:

```powershell
schtasks /Create /TN "EEA daily forward" /SC DAILY /ST 07:00 /TR "\"D:\Work\Private\Trading\EA-Enterprise\.worktrees\g126\EnterpriseEA\research\forward\run_daily_forward.bat\"" /F
```

- Kiểm tra: `schtasks /Query /TN "EEA daily forward"`.
- Chạy thử ngay: `schtasks /Run /TN "EEA daily forward"`.
- Gỡ: `schtasks /Delete /TN "EEA daily forward" /F`.
- Đổi đường dẫn nếu dùng bản ở thư mục khác, ví dụ sau khi merge vào main: `D:\Work\Private\Trading\EA-Enterprise\EnterpriseEA\research\forward\run_daily_forward.bat`.
- Lịch chỉ chạy khi người dùng đã đăng nhập Windows (mặc định của `schtasks` khi không có `/RU`).

## Cách 2: VPS Linux (MT5 chạy Wine ở `/opt/qtl/data/mt5/terminal`)

Python trên Linux **không** dùng được thư viện `MetaTrader5`. Có hai hướng.

### 2a. Python cho Windows chạy trong Wine (cùng prefix với MT5)

Làm một lần:

```bash
# tải Python cho Windows (ví dụ 3.11, bản 64-bit) rồi cài vào prefix của MT5
WINEPREFIX=/opt/qtl/data/mt5/.wine wine python-3.11.9-amd64.exe /quiet InstallAllUsers=1 PrependPath=1
WINEPREFIX=/opt/qtl/data/mt5/.wine wine python -m pip install MetaTrader5 numpy pandas lightgbm
```

- Chép thư mục `research/` (gồm `long/`, `forward/`, `g10/`) sang VPS, ví dụ `/opt/qtl/research/`.
- Chép kèm dữ liệu nghiên cứu cần cho phần tái lập: `research/long/data/m30v/XAUUSD.csv`.
- Trên VPS symbol là **XAUUSD.r**: sửa `BROKER` trong `research/long/g106_shadow.py` và tên symbol trong `research/long/g134_extensions.py` (`terminal_m30`).
- Sửa `TERMINAL` trong hai file đó thành đường dẫn `terminal64.exe` trong Wine, ví dụ `C:\Program Files\MetaTrader 5\terminal64.exe` nếu cài mặc định trong prefix.

Đặt lịch bằng **cron** (07:00 giờ VPS) cho user chạy MT5:

```bash
crontab -e
# thêm dòng:
0 7 * * * cd /opt/qtl/research/long && WINEPREFIX=/opt/qtl/data/mt5/.wine DISPLAY=:0 wine python ../forward/daily_forward.py >> /opt/qtl/research/forward/cron.log 2>&1
```

- `DISPLAY` phải khớp với màn hình ảo (Xvfb) mà MT5 đang dùng trên VPS.
- Xem log: `tail -50 /opt/qtl/research/forward/cron.log`.
- Gỡ: `crontab -e` rồi xóa dòng đó.

### 2b. Không cài Python vào Wine: lấy nến bằng script MQL5, tính trên máy khác

- Trên VPS chạy script `EEA_ExportDeals` (thư mục `Scripts`). Script xuất nến M5 / M15 / M30 / H1 / H4 vào `MQL5/Files/EEA_export/`, kèm lịch sử lệnh.
- Chép thư mục đó về máy Windows rồi dùng `Tests/live_vs_research.py` để đối chiếu.
- Cách này cần chạy tay; không tự động hoàn toàn được nếu không có Python trong Wine.

## Đọc kết quả

- **Nến V M30**: nghiên cứu cho +0,42U/nhóm, khoảng 2 nhóm/tháng. Cần **ít nhất 15–20 nhóm forward** trước khi kết luận.
- **CtxBox**: so R/lệnh forward với lịch sử G106 theo từng khung. Nếu sau khoảng 30 lệnh mỗi khung vẫn âm rõ thì coi lợi thế lịch sử của khung đó là không còn.
