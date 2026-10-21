# G128: phân bổ rủi ro cho S07 + VHedge G119 — kết quả

Kế hoạch: `plans/2026-10-20-g128-risk-allocation.md`. Vốn đầu 10.000, lãi kép, lệnh giữ nguyên, chỉ đổi khối lượng. Gốc: S07 1,5% × trọng số EA; VHedge 1,5%/nhóm. Ô: %/năm / DD lớn nhất / **MAR** / DD p90 (cửa sổ 1 năm bắt đầu mỗi tháng) / số lệnh.

Chân S07: 1266; nhóm VHedge: 323.

## S07 một mình (train 03/2018–2021, validate 2022–2025)

| Luật | Train | Validate | Giữ? |
|---|---|---|---|
| Gốc | +16.7% / 32.5% / **0.52** / 32.0% / 461 | +122.5% / 19.2% / **6.39** / 19.2% / 699 | |
| A biến động | +21.1% / 33.9% / **0.62** / 33.4% / 461 | +117.2% / 21.0% / **5.58** / 21.0% / 699 |  |
| C sụt vốn 8% | +13.8% / 21.3% / **0.65** / 20.8% / 461 | +88.3% / 14.2% / **6.23** / 14.0% / 699 |  |
| C sụt vốn 12% | +11.2% / 23.3% / **0.48** / 22.9% / 461 | +102.8% / 16.6% / **6.20** / 16.1% / 699 |  |
| E chuỗi thua | +15.5% / 23.8% / **0.65** / 23.7% / 461 | +90.6% / 19.0% / **4.78** / 17.5% / 699 |  |

## S07 + VHedge (chọn trên 05/2024–12/2025)

| Luật | 05/2024–12/2025 | Giữ? |
|---|---|---|
| Gốc | +773.0% / 25.1% / **30.82** / 25.1% / 603 | |
| A biến động | +767.9% / 25.3% / **30.33** / 25.3% / 603 |  |
| B trần 4,5% | +599.0% / 25.1% / **23.89** / 25.1% / 593 |  |
| B trần 6% | +693.4% / 25.1% / **27.65** / 25.1% / 599 |  |
| C sụt vốn 8% | +557.5% / 17.0% / **32.73** / 17.0% / 603 | **giữ** |
| C sụt vốn 12% | +616.1% / 19.6% / **31.38** / 19.6% / 603 | **giữ** |
| D VHedge 1,0% | +553.4% / 21.0% / **26.33** / 21.0% / 603 |  |
| D VHedge 2,0% | +1047.5% / 29.0% / **36.15** / 29.0% / 603 |  |
| E chuỗi thua | +590.1% / 17.4% / **33.88** / 17.4% / 603 | **giữ** |
| **Bộ cuối: C sụt vốn 8% + E chuỗi thua** | +434.2% / 13.5% / **32.20** / 13.5% / 603 | (kém luật tốt nhất đứng riêng) |

## Test 2026 (mở một lần)

| Sổ | Gốc 2026 | Bộ cuối 2026 | Đạt? |
|---|---|---|---|
| S07 + VHedge (C sụt vốn 8% + E chuỗi thua) | +426.0% / 12.0% / **35.39** / 12.0% / 175 | +263.6% / 9.0% / **29.25** / 9.0% / 175 | không |

DD p90 trên 2026 không có ý nghĩa (chưa đủ 1 năm); cột đó lặp lại DD lớn nhất.

## Kết luận

**G128 không đạt.** Không luật phân bổ nào cải thiện được tỷ lệ lãi/DD một cách bền vững.

- **S07 một mình**: không luật nào được giữ ở cả hai kỳ.
  - Sụt vốn 8% (C) và chuỗi thua (E) giảm DD rõ (train 32% → 21–24%; validate 19% → 14–19%), nhưng giảm lãi gần tương ứng. MAR validate thấp hơn gốc.
  - Theo biến động (A) tăng lãi train nhưng tăng DD validate.
- **S07 + VHedge**: C và E được giữ trên 05/2024–12/2025, nhưng **trên 2026 bộ cuối thua gốc**: MAR 29,3 so với 35,4. DD giảm từ 12% xuống 9%, nhưng lãi giảm nhiều hơn (+426% → +264%).
- **Bản chất**: các luật "giảm rủi ro khi đang xấu" ở đây chỉ tương đương giảm rủi ro chung. Chúng không chọn được lúc xấu tốt hơn một mức rủi ro cố định thấp hơn. Muốn DD thấp hơn thì **giảm % rủi ro mỗi lệnh** là cách đơn giản và trung thực nhất (DD và lãi gần tỷ lệ với nhau).
- **Trần rủi ro đang mở (B)** chỉ làm mất lãi: hai bot hiếm khi cùng lúc chạm trần, nên trần chủ yếu cắt lệnh tốt.
- **VHedge 2%** cho MAR cao nhất trên 05/2024–12/2025 (36,2) nhưng DD p90 cao hơn, nên không được giữ. VHedge hiệu quả hơn S07 trong 2024–2026, nhưng lịch sử của nó mới khoảng 2,4 năm.
- **Lưu ý**: các con số %/năm rất lớn (hàng trăm %) là do lãi kép với hai bot cùng 1,5%/lệnh trong giai đoạn vàng tăng mạnh. Không nên dùng làm kỳ vọng.
