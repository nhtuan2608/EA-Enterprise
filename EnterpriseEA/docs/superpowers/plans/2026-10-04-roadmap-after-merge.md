# Lộ trình sau merge (04/10/2026)

Mốc: `main` đã có `9d0b9ea` (merge `feature/ui-redesign-v2`). Terminal demo chạy `fc4ec26`; phiên ủy quyền 7 ngày đang ACTIVE; tuần chạy thử S02 bắt đầu từ thứ Hai 05/10.

## 1. Hiện trạng theo đặc tả v1.4

| Nhóm | Trạng thái |
|---|---|
| REQ-001/002/004/006/009/010/011, REQ-013–017 | Xong (observer, risk kernel O-04 / FTMO, execution gate, dashboard, calendar, restart, ledger) |
| REQ-003 Setup Engine | 1/6 họ setup: **S02 Break Retest v1**. Còn S01 Asian Range Break, S03 PDH/PDL Break, S04 Failed Break, S05 Trend Pullback, S06 Compression Expansion. Đặc tả mục S2 ưu tiên **S04** ngay sau S02 để kiểm tra hai chuỗi đối lập |
| REQ-005 Trade Manager | Code xong (v1). Chờ lệnh thật để kiểm chứng |
| REQ-021 Lệnh chờ | Code xong. Chờ lệnh thật (TC-046..051) |
| REQ-007 News | News Guard đỏ/vàng, bộ ghi phản ứng, gộp cụm: xong. Chưa kiểm chứng trên tin thật; AI News Interpreter chưa có |
| REQ-008 / REQ-012 AI | Đã có thiết kế (`2026-10-04-ai-bridge-and-news-review-design.md`); chưa code |
| Đặc tả 9.2 Thao tác tay trên lệnh | Chưa có; tab Trades đang chỉ để xem |
| REQ-018–020 Telegram | Chưa có |
| Kiểm chứng S02 (bước 6) | Forward 1 tuần đang chạy; Strategy Tester chưa chạy |

## 2. Thứ tự triển khai

| # | Hạng mục | Vì sao ở vị trí này | Ra kết quả |
|---|---|---|---|
| P1 | **Replay News Guard trên tin và giá từ 01/01/2026** | Kiểm chứng News Guard bằng dữ liệu lịch sử, không phải chờ tin thật | Mỗi bản ghi phản ứng có thêm đánh giá "News Guard có che được nhịp biến động không"; có thống kê theo cụm tin |
| P2 | **Tự động kiểm tra số liệu tin** (AI design mục 7) | Chạy được ngay, không cần AI; bắt lỗi dữ liệu trước khi AI đọc | `news_data_health.json` + dòng Data health trên tab News |
| P3 | **AI Bridge v1, Level 0** | Tự động hóa việc đọc số liệu mà người dùng đang làm tay | Báo cáo AI hằng ngày, giải thích từng cụm tin, chẩn đoán EA, nút ASK AI |
| P4 | **Command queue + thao tác tay** CLOSE / PARTIAL / BE / TRAIL (đặc tả 9.2) | Cần trước khi có nhiều lệnh thật; cũng là nền cho Telegram và AI Level 2 | Nút trên tab Trades, có xác nhận, đi qua cùng các cổng kiểm tra |
| P5 | **S04 Failed Break** | Setup thứ hai theo ưu tiên của đặc tả; chuỗi ngược với S02 | Engine S04 + risk path dùng chung, test theo TC-005 |
| P6 | **Kiểm chứng S02** bằng Strategy Tester + báo cáo tuần forward | Khóa tham số PROPOSED | Báo cáo kiểm chứng S02 |
| P7 | S01 / S03 / S05 / S06 | Sau khi S02 và S04 đã có số liệu | Từng setup một, cùng khuôn với S02 |
| P8 | Telegram (REQ-018–020) | Dùng lại command queue (P4) và AI bridge (P3) | Điều khiển và hỏi AI qua Telegram |

## 3. Quyết định mặc định khi chưa có ý kiến khác

- **AI (Q1–Q6 trong thiết kế AI):** áp dụng các đề xuất. Chỉ bật Level 0 (AI chỉ báo cáo, không có quyền nào trên lệnh), nên không ảnh hưởng tới giao dịch. Người dùng đổi được bất cứ lúc nào.
- **Replay từ đầu năm:** chỉ đo và đánh giá, không đổi tham số News Guard.

## 4. Quy trình mỗi hạng mục

1. Thiết kế (spec) → người dùng chốt các điểm ảnh hưởng tới giao dịch.
2. Code + test (oracle Python khi có logic tính toán) + compile MetaEditor.
3. Deploy: kiểm tra target khớp bản đang chạy → backup → deploy → người dùng gắn lại EA → kiểm tra log.
4. Commit trên `feature/ui-redesign-v2`; merge vào `main` theo từng mốc.
