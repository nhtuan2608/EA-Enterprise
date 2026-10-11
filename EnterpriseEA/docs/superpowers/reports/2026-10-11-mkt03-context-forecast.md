# MKT03: dự báo theo ngữ cảnh → lệnh limit / market cho chỉ số Mỹ và crypto — kết quả

Kế hoạch: `plans/2026-10-11-mkt03-context-forecast.md`. M30, LightGBM huấn luyện cuốn chiếu (mỗi 3 tháng, bỏ 20 nến sát mốc), mọi dự báo ngoài mẫu. Kế hoạch M: market, SL 1 ATR / TP 1,5 ATR / tối đa 16 nến. Kế hoạch L: limit cách 0,5 ATR chờ 4 nến, cùng SL/TP. Chi phí khắt khe, phí hoa hồng 0. R theo 1 ATR.

## Chỉ số

**Kế hoạch M** — chọn ngưỡng trên validate:

| Phân vị | θ | Lệnh validate | R/lệnh validate |
|---|---|---|---|
| 80% | +0.077 | 2584 | -0.065 |
| 90% | +0.181 | 1436 | -0.040 |
| 95% | +0.286 | 741 | -0.032 |

Ngưỡng chọn: phân vị 95% (θ +0.286). 10 thành phần ngữ cảnh quan trọng nhất (mô hình cuối): d1_dist, h4_dist, d_pdh, e55_e200, atr_ratio, dow, d_pdl, e21_e55, r48, comp16.

**Kế hoạch L** — chọn ngưỡng trên validate:

| Phân vị | θ | Lệnh validate | R/lệnh validate |
|---|---|---|---|
| 80% | +0.124 | 1838 | +0.002 |
| 90% | +0.231 | 1047 | -0.058 |
| 95% | +0.333 | 521 | -0.088 |

Ngưỡng chọn: phân vị 80% (θ +0.124). 10 thành phần ngữ cảnh quan trọng nhất (mô hình cuối): d1_dist, h4_dist, e55_e200, atr_ratio, d_pdh, d_pdl, dow, ny_hour, e21_e55, r48.

## Crypto lớn

**Kế hoạch M** — chọn ngưỡng trên validate:

| Phân vị | θ | Lệnh validate | R/lệnh validate |
|---|---|---|---|
| 80% | -0.222 | 1453 | -0.186 |
| 90% | -0.142 | 1453 | -0.186 |
| 95% | -0.072 | 1453 | -0.186 |

Ngưỡng chọn: phân vị 80% (θ -0.222). 10 thành phần ngữ cảnh quan trọng nhất (mô hình cuối): d1_dist, sym, vol_ratio, atr_ratio, h4_dist, e55_e200, d1_side, d_pdh, e21_e55, dow.

**Kế hoạch L** — chọn ngưỡng trên validate:

| Phân vị | θ | Lệnh validate | R/lệnh validate |
|---|---|---|---|
| 80% | -0.137 | 2445 | -0.057 |
| 90% | -0.056 | 2445 | -0.057 |
| 95% | +0.017 | 2102 | -0.042 |

Ngưỡng chọn: phân vị 95% (θ +0.017). 10 thành phần ngữ cảnh quan trọng nhất (mô hình cuối): d1_dist, vol_ratio, atr_ratio, h4_dist, sym, d_pdh, e55_e200, dow, e21_e55, d_pdl.

## Kiểm tra cuối (10/2025–10/2026)

| Ô | Lệnh | Khớp limit | R/lệnh | Không điều kiện | p hoán vị | Cận dưới 90% | Cận dưới 97,5% | Sau trừ 0,10R | Theo symbol | Đạt? |
|---|---|---|---|---|---|---|---|---|---|---|
| Chỉ số M | 314 | — | +0.023 | -0.065 | 0.101 | -0.062 | -0.108 | -0.077 | NAS100 109 +0.23, DJ30 110 -0.16, SP500 95 +0.01 | không |
| Chỉ số L | 1194 | 47% | -0.024 | -0.076 | 0.062 | -0.071 | -0.094 | -0.124 | NAS100 475 -0.05, DJ30 364 -0.05, SP500 355 +0.03 | không |
| Crypto lớn M | 718 | — | -0.098 | -0.290 | 0.000 | -0.153 | -0.183 | -0.198 | BTCUSD 519 -0.09, ETHUSD 199 -0.12 | không |
| Crypto lớn L | 557 | 55% | -0.067 | -0.227 | 0.001 | -0.129 | -0.161 | -0.167 | BTCUSD 370 +0.01, ETHUSD 187 -0.22 | không |

BTC validate dài (01/2021–09/2025, ngưỡng chọn trên chính kỳ này nên chỉ là bằng chứng phụ): M: 1066 lệnh -0.185; L: 1625 lệnh -0.024.


Với crypto, hầu hết dự báo validate âm, nên luật "dự báo > 0" quyết định số lệnh và ba phân vị cho cùng một tập lệnh.

## Kết luận

**MKT03 không đạt: không ô nào dương sau chi phí.** Nhưng có một phát hiện quan trọng.

- **Mô hình ngữ cảnh có khả năng chọn lệnh thật, nhất là crypto.**
  - Ở kỳ test, lệnh được chọn tốt hơn lệnh ngẫu nhiên rõ rệt: crypto M −0,10 so với −0,29 (p hoán vị 0,000); crypto L −0,07 so với −0,23 (p 0,001).
  - Chỉ số yếu hơn: +0,02 so với −0,07 (p 0,10) và −0,02 so với −0,08 (p 0,06).
  - Ngữ cảnh giúp thêm khoảng **+0,05 đến +0,19R/lệnh**.
- **Nhưng chi phí ở quy mô này lớn hơn phần cải thiện.** Với SL 1 ATR M30, một lệnh vào ngẫu nhiên đã mất −0,07R (chỉ số) đến −0,29R (crypto) chỉ vì spread và trượt.
- **Limit giảm chi phí đúng như kỳ vọng** (không điều kiện crypto −0,23 so với −0,29 của market), nhưng chỉ khớp 47–55%.
- **Ngữ cảnh quan trọng nhất ở mọi mô hình**:
  - khoảng cách tới EMA200 D1 và H4 (đúng ngữ cảnh S07);
  - độ dốc dải EMA (EMA55 − EMA200);
  - tỷ lệ biến động ATR14/ATR100;
  - khoảng cách tới đỉnh/đáy ngày trước;
  - thứ trong tuần;
  - với crypto, thêm tick volume.
- **Hướng tiếp theo hợp lý**: cùng khung phương pháp nhưng ở **quy mô lớn hơn** (nến H4 hoặc SL/TP rộng hơn), để chi phí còn khoảng 1/3. Phần cải thiện +0,1–0,2R của mô hình khi đó có thể vượt chi phí. Cần kế hoạch mới (MKT04).
