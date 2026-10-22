# G152b: hòa vốn trước tin chỉ với tin lớn (V2) cho S07 — kiểm bằng dữ liệu forward — kế hoạch đăng ký trước (23/10/2026)

## Vì sao

G152 (05/2018 – 06/2026) không cho phép bỏ hẳn quy tắc hòa vốn trước tin cho S07 (đánh đổi theo chế độ thị trường). Biến thể V2 (chỉ NFP, CPI,
Core PCE, quyết định lãi suất Fed, họp báo FOMC) gần như không thua cả hai phía, nhưng G152 chỉ ghi V2 là "báo cáo". G152b ghi V2 thành ô quyết
định và kiểm trên dữ liệu **chưa tồn tại lúc ghi kế hoạch**.

## Luật (cố định)

- Sổ S07 M30 bản Python G89 (như G152), nến và lịch tin MT5 **từ 23/10/2026**.
- V1 = quy tắc EA hiện tại; V2 = chỉ tin lớn; ngưỡng lời 0,3R, 15 phút trước tin, như G152 (`g152_news_breakeven.py`, đổi kỳ).
- Chạy khi đủ **≥ 60 chân S07** mới, hoặc sau **6 tháng**, tùy cái nào đến trước.

## Đạt khi

- tổng R V2 ≥ V1 trên kỳ forward;
- MAR V2 ≥ V1;
- DD lớn nhất V2 không cao hơn V1 quá 3 điểm %.

Nếu đạt: đề xuất đổi mặc định `InpS07NewsBreakEvenScope` từ `S07_NEWS_BE_ALL` sang `S07_NEWS_BE_TOP_TIER` (người dùng đồng ý mới đổi). Nếu
không: giữ mặc định.

## Đã làm cùng ngày (không đổi hành vi)

EA có input `InpS07NewsBreakEvenScope` (`ALL` = như cũ, **mặc định**; `TOP_TIER`; `OFF`), chỉ áp cho lệnh S07*, các setup khác không đổi. Build
`builds/EnterpriseEA_Bots.ex5` từ commit này. Chưa nạp lên demo / VPS.
