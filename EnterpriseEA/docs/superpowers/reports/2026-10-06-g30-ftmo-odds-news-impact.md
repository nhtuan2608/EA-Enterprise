# G30: xác suất vượt FTMO theo mức rủi ro, và tác động thật của từng loại tin (06/10/2026)

Chỉ dữ liệu MT5. Script: `research/long/ftmo_odds.py`, `research/long/news_impact.py`.

## 1. Xác suất vượt FTMO 1-Step

Lệnh: S04 SWING (TM hiện tại) + S06B lọc USD, có và không bồi lệnh +1R, SWING H1 2010–2025.
Luật thi: 10.000 USD, mục tiêu +10%, lỗ ngày ≤ 3% vốn đầu (so với số dư đầu ngày), sàn tổng = đỉnh
số dư cuối ngày − 10% (trượt theo đỉnh), không giới hạn thời gian. Giới hạn nội bộ nhân theo mức rủi ro
(mở tối đa 4 lệnh, chốt lỗ ngày 4r tối đa 2,5%, tuần 8r tối đa 5%), và như EA (`FtmoHeadroom.mqh`),
chỉ vào lệnh khi mọi dừng lỗ đang mở cộng lệnh mới, nếu cùng chạm trong ngày, vẫn còn 0,5% trên sàn.
Hai cách rút: bắt đầu mỗi thứ Hai 2010–2024 theo đúng lịch sử; và 3.000 đường xáo ngẫu nhiên theo tháng.

| Rủi ro/lệnh | Phương án | Vượt ≤ 6 tháng | Vượt ≤ 12 tháng | Vượt ≤ 24 tháng | Thời gian vượt (trung vị) | Ngày tốt nhất ≤ 50% lợi nhuận |
|---|---|---|---|---|---|---|
| 0,3% (hiện tại) | S04 + S06B lọc USD | 0% | 0% | 0–1% | 4–9 năm | 100% |
| 0,5% | + bồi +1R | 0–1% | 2–6% | 10–30% | 2,4–3,3 năm | 100% |
| 0,75% | + bồi +1R | 2–5% | 13–22% | 48–57% | 1,6–2,1 năm | 100% |
| **1,0%** | **+ bồi +1R** | **8–14%** | **26–39%** | **64–69%** | **1,1–1,5 năm** | **94%** |
| 1,0% | không bồi | 4–7% | 18–24% | 57–58% | 1,5–1,6 năm | 91–92% |
| 1,5% | + bồi +1R | 16–30% | 41–56% | 71–73% | 0,6–0,9 năm | 35–43% |

(Khoảng giá trị: cách rút lịch sử – cách rút xáo tháng.)

- Nhờ kiểm tra dư địa giống EA, không đường nào chạm sàn FTMO trong mô phỏng (lỗ thả nổi và trượt giá
  không được mô hình; thực tế vẫn có rủi ro nhỏ). Những lần "chưa vượt" là tài khoản đi ngang lâu.
- Ở 0,3% hiện tại gần như không thể vượt trong 2 năm. Ở 1% có bồi lệnh: khoảng 1/3 vượt trong 12 tháng,
  2/3 trong 24 tháng. Ở 1,5% nhanh hơn nhưng phần lớn lần vượt có một ngày lãi chiếm quá 50% tổng lãi
  (luật "ngày tốt nhất" của FTMO 1-Step) và rủi ro thực tế cao hơn mô phỏng.
- Lot cố định hay rủi ro cố định: G25 đã cho thấy lot cố định làm lợi nhuận giảm một nửa; với mục tiêu FTMO
  càng nên dùng rủi ro cố định theo % vốn.
- Muốn tăng rủi ro quá 0,3% phải đổi hồ sơ rủi ro của EA (giới hạn mỗi lệnh 0,3%, mở 1,2%, ngày 1,2%,
  tuần 2,4%): là quyết định của người dùng, chưa đổi.

## 2. Tác động thật của từng loại tin HIGH

Nguồn: `logs/news_reactions.jsonl` (EA ghi từ 01/2026), chỉ tin đứng đầu cụm, symbol mang đồng tiền của tin.
So với giờ bình thường cùng giờ UTC trên dữ liệu M5 2024-06..2025-10 (EURUSD, GBPUSD, XAUUSD, USDJPY).

Tin mạnh (giữ chặn): Fed lãi suất ×6,7 (biên độ 60 phút so với bình thường), lương giờ/NFP ×3,3,
ECB lãi suất ×3,0, GBP CPI ×2,3, FOMC họp báo ×2,2, US Core CPI ×2,1, GBP GDP ×1,9, EUR GDP ×1,9
(4 giờ ×3,1), BoJ họp báo/lãi suất, Core PCE (4 giờ ×2,6), PPI, Chicago PMI.

Tin gần như không khác giờ bình thường (biên độ 60 phút < ×1,25, biến động 4 giờ < ×1,25, cú sốc < 15%):

| Tin | Số lần | 60 phút | 4 giờ | Cú sốc |
|---|---|---|---|---|
| USD Initial Jobless Claims | 30 | ×1,12 | ×1,18 | 10% |
| USD EIA Crude Oil Stocks Change | 39 | ×1,05 | ×1,12 | 1% |
| EUR ECB President Lagarde Speech | 59 | ×1,06 | ×1,01 | 6% |
| USD 10-Year Note Auction | 8 | ×1,13 | ×1,10 | 6% |
| USD CB Consumer Confidence Index | 9 | ×1,11 | ×1,01 | 7% |
| USD Durable Goods Orders m/m | 6 | ×1,07 | ×0,45 | 4% |
| USD Existing / New Home Sales | 8 / 7 | ×1,04 / ×0,90 | ×0,96 / ×0,82 | 5% / 8% |
| USD ISM Non-Manufacturing PMI | 10 | ×1,09 | ×0,79 | 0% |
| USD S&P Global Services PMI | 9 | ×0,71 | ×0,74 | 0% |
| JPY BoJ L Money Stock y/y | 9 | ×1,11 | ×0,30 | 9% |

Biên: 30-Year Bond Auction, ISM Manufacturing, ECB họp báo, Bailey, ADP, Core Retail Sales có biên độ
60 phút bình thường nhưng biến động 4 giờ ×1,3–1,8: với SWING nên giữ chặn. BoE lãi suất giữ chặn
(14% cú sốc, 30 phút mới bình thường).

### Gợi ý `InpNewsIgnoreKeywords` (người dùng quyết)

```
Initial Jobless Claims,EIA Crude Oil,Lagarde Speech,CB Consumer Confidence,Durable Goods,Home Sales,ISM Non-Manufacturing,S&P Global Services PMI,Note Auction,Money Stock
```

Lưu ý:
- EA so khớp không phân biệt hoa thường, theo chuỗi con, cho mọi đồng tiền. Không đưa "CPI y/y", "GDP q/q",
  "Retail Sales" vào danh sách vì sẽ khớp cả tin mạnh (GBP CPI, EUR GDP, US Retail Sales).
- Tin bị bỏ qua cũng không còn được EA ghi phản ứng (`NewsReactionRecorder`), nên sẽ mất số liệu theo dõi
  các tin đó.
- Mẫu mới 1 năm (6–10 lần ra tin cho phần lớn tin; Jobless Claims, EIA, Lagarde 30–59 lần). Các nghiên cứu
  G23–G28 không áp chặn tin mà S04/S06B vẫn dương, nên nới các tin yếu ít rủi ro.

## 3. (G32) FTMO 2-Step so với 1-Step

`research/long/ftmo2_odds.py`: cùng chuỗi lệnh, cùng kiểm tra dư địa như EA. 2-Step: vòng 1 +10%, vòng 2 +5%
(mỗi vòng số dư mới), lỗ ngày 5%, sàn cố định vốn đầu − 10%, ít nhất 4 ngày giao dịch mỗi vòng.

| Rủi ro/lệnh, S04 + S06B lọc USD + bồi +1R | 1-Step: ≤ 12 tháng / ≤ 24 tháng / trung vị | 2-Step (cả 2 vòng): ≤ 12 tháng / ≤ 24 tháng / trung vị |
|---|---|---|
| 0,75% | 13–22% / 48–57% / 1,6–2,1 năm | 0–4% / 5–26% / 2,6–3,5 năm |
| 1,0% | 26–39% / 64–69% / 1,1–1,5 năm | 2–12% / 25–44% / 1,9–2,7 năm |
| 1,5% | 41–56% / 71–73% / 0,6–0,9 năm (ngày tốt nhất vi phạm nhiều) | 13–28% / 49–59% / 1,2–1,8 năm |
| 2,0% | – | 21–38% / 54–56% / 0,8–1,3 năm |

- Hệ thống này không bao giờ chạm sàn nhờ kiểm tra dư địa, nên lợi thế của 2-Step (lỗ ngày 5%, sàn cố định)
  không giúp gì; điều quyết định là tổng lợi nhuận phải đạt: 1-Step cần 10%, 2-Step cần 10% + 5%.
- Với hệ thống lãi ít nhưng đều này, **1-Step nhanh hơn rõ** ở cùng mức rủi ro. 2-Step chỉ bằng 1-Step khi
  tăng rủi ro lên khoảng gấp đôi (2% so với 1%), tức sụt giảm thực tế lớn gấp đôi.
- Điểm cộng của 2-Step: không có luật "ngày tốt nhất" và sàn không trượt theo đỉnh; điểm trừ: chậm hơn.
