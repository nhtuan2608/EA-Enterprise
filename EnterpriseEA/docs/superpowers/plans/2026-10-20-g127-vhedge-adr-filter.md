# G127: bộ lọc ADR cho VHedge G119 — kế hoạch đăng ký trước (20/10/2026)

## Vì sao

Ở G126 Phần D (chỉ mô tả, 05/2024–12/2025), lệnh VHedge G119 vào khi ngày **chưa dùng 0,8 ADR** được +0,60R/lệnh (200 lệnh). Lệnh vào khi **đã dùng ≥ 0,8 ADR** được −0,10R/lệnh (30 lệnh).

Người dùng muốn kiểm tra đây có phải bộ lọc thật cho VHedge không.

Giai đoạn 05/2024–12/2025 là nơi **phát hiện** ra ý này, nên không được dùng nó làm bằng chứng. Bằng chứng duy nhất hợp lệ là **2026**: chưa mở cho ý này và chưa từng dùng để chọn VHedge G119 (các hồ sơ G119 được chọn trên dữ liệu trước 2025).

## Định nghĩa (cố định, giống G126)

- **Lệnh VHedge**: đúng bộ sinh lệnh G119 của nghiên cứu (`g120_combo.vhedge()["G119"]`): nến M5, giữ tới 5R. R mỗi nhóm lệnh như G119.
- **Thời điểm đo**: lúc vào lệnh (`t_in`, giờ server → UTC theo luật g67).
- **Ngày** = ngày UTC.
- **ADR** = trung bình (cao − thấp) của 10 ngày UTC trước đó, từ nến M30.
- **ADR đã dùng** = (cao − thấp từ 00:00 UTC đến nến M30 cuối cùng đã đóng trước lúc vào) ÷ ADR.
- **Bộ lọc**: chỉ vào khi ADR đã dùng **< 0,8**. Ngưỡng 0,8 cố định, không chỉnh.

## Bước 1 — kiểm tra lại trên giai đoạn phát hiện (05/2024–12/2025, chỉ mô tả, không quyết định)

1. **Đường ngưỡng**: R/lệnh giữ và bỏ ở các ngưỡng 0,6 / 0,7 / 0,8 / 0,9 / 1,0. Nếu hiệu ứng thật, nó nên thay đổi đều theo ngưỡng chứ không chỉ đúng ở 0,8.
2. **Có phải chỉ là giờ trong ngày?** Càng về cuối ngày, ADR đã dùng càng cao. So giữ với bỏ **trong cùng nhóm giờ UTC** (00–07, 07–13, 13–21, 21–24), rồi lấy trung bình có trọng số.
   - Nếu chênh lệch biến mất trong cùng nhóm giờ, ghi rõ trong báo cáo: hiệu ứng thật có thể là **giờ** chứ không phải ADR.
3. **Theo năm**: 2024 và 2025 riêng.
4. **Theo ngày server** (cách EA tính ngày dễ hơn): cùng ngưỡng 0,8, chỉ để biết khác biệt khi đưa vào EA.

Bước 1 không thay đổi bộ lọc hay ngưỡng. Nó chỉ cho biết điều cần chú ý khi đọc kết quả 2026.

## Bước 2 — test 2026 (mở một lần)

- **Dữ liệu**: lệnh VHedge G119 từ 01/01/2026 đến hết dữ liệu (10/2026).
- **Bộ lọc ĐẠT** khi đủ cả ba:
  1. R/lệnh nhóm giữ > R/lệnh nhóm bỏ;
  2. **tổng R** của nhóm bỏ ≤ 0, tức bỏ chúng không làm mất tiền;
  3. có ≥ 10 lệnh bị bỏ (đủ để nói gì đó).
- **Báo cáo thêm**:
  - kiểm định hoán vị nhãn giữ/bỏ (p một phía);
  - %/năm và DD của VHedge có và không có lọc (1,5% mỗi nhóm, như G120);
  - đường ngưỡng trên 2026 (mô tả).
- Mẫu 2026 nhỏ (ước khoảng 100 lệnh, trong đó khoảng 10–20 bị bỏ). Vì vậy:
  - **ĐẠT** cho phép bật bộ lọc **ở chế độ SHADOW / ghi nhận** trong EA, chưa dùng để chặn lệnh thật;
  - chỉ chuyển sang chặn thật khi có thêm ≥ 3 tháng dữ liệu live / forward cùng chiều.
- **KHÔNG ĐẠT** thì đóng ý này, VHedge giữ nguyên.

## Nếu đạt: đưa vào EA (cần người dùng đồng ý trước khi deploy)

- `Bots/VHedgeBot`: thêm input `InpVHedgeAdrMaxUsed` (mặc định 0 = tắt) và `InpVHedgeAdrMode` (SHADOW = chỉ ghi vào nhật ký bot "lệnh này lẽ ra bị lọc", LIVE = chặn).
- ADR trong EA tính theo ngày UTC: giờ server trừ độ lệch, cùng cách quy đổi như nghiên cứu. Kiểm tra khớp Python–MQL trên lệnh live / tester trước khi bật.

## Đầu ra

`research/long/g127_vhedge_adr.py`, báo cáo `reports/2026-10-20-g127-vhedge-adr-filter.md`.
