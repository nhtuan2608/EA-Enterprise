# Lộ trình nghiên cứu tiền tệ (FX)

Mã **FXnn** dành riêng cho nghiên cứu FX, tách khỏi dãy **Gnn** (vàng / EA chung). Các nghiên cứu FX trước khi tách vẫn giữ mã G cũ:

| Mã | Nội dung | Kết quả |
|---|---|---|
| G55 | Scorecard setup trên nhiều tài sản | S06B_USD EUR/GBP, S04 GBPUSD dương nhưng ít lệnh |
| G90 | Swing FX từ setup hiện có (H1/H4) | ❌ âm sau chi phí |
| G91 | Sổ FX ghép setup, chọn 2010–20, test 2021–25 | ❌ −0,03R/lệnh; lợi thế xoay vòng giữa cặp/kỳ |
| G92 | S04 mở rộng H1/H4 | ⏸ dừng, thay bằng G93 |
| G93 | S04 + S06B(_USD) EUR/GBP ở M15/M30/H1 | ❌ không ô nào đạt; S06B M30 không lọc là ứng viên |

## Dãy FX

| Mã | Nội dung | Trạng thái |
|---|---|---|
| FX01 | Vào lệnh theo USD (test lại đỉnh/đáy, phá cấu trúc), vùng cung/cầu, lực đẩy sau tin; lệnh limit, giờ tròn; M15/M30/H1 | ❌ 11/10 cả 12 ô âm mọi kỳ, kể cả trước phí. Limit tệ hơn thị trường với tín hiệu theo nến (chọn lọc ngược), tốt hơn với vùng cung/cầu nhưng vẫn âm. `reports/2026-10-11-fx01-usd-led-limit.md` |
| FX02 | Sức mạnh tiền tệ D1 (USD, EUR, GBP, JPY; động lượng chéo, đảo chiều ngắn, xu hướng từng cặp) | ❌ 11/10 không họ nào đạt. Động lượng 60–120 ngày dương 2010–16 và 2021–25 nhưng âm 2017–20 (phụ thuộc chế độ). `reports/2026-10-11-fx02-currency-strength.md` |
| FX03 | Dòng tiền có lịch: đồng tiền yếu trong giờ nội địa, chốt giá London cuối tháng | ❌ 11/10 EUR/GBP yếu giờ châu Âu có thật (+0,06R trước chi phí, cùng dấu mọi kỳ) nhưng chi phí ≈ hiệu ứng. Chốt giá cuối tháng không ổn định. `reports/2026-10-11-fx03-structural-flows.md` |
