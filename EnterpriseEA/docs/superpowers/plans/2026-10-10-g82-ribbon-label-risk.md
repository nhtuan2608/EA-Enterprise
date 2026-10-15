# G82: Rủi ro theo nhãn "dải EMA xếp thứ tự" cho lệnh mua S07 — kế hoạch đăng ký trước (10/10/2026)

## Vì sao

G81: lệnh mua S07 M30 có dải EMA **xếp thứ tự** ở nến tín hiệu (EMA21 > EMA55 > EMA100 và giá đóng > EMA21) tốt hơn lệnh không có: +0,50 so với +0,42 R/lệnh cho cả bộ. Nếu chỉ lọc theo nhãn thì mất khoảng 1/4 số lệnh và tổng R giảm. Thay vì bỏ lệnh không nhãn, G82 thử **giảm rủi ro** cho chúng (hoặc tăng cho lệnh có nhãn).

**Trung thực về dữ liệu:** nhãn đến từ G81, đã nhìn trên toàn bộ dữ liệu. G82 kiểm cách dùng và độ vững, không phải ngoài mẫu.

## Sổ lệnh

Sổ mua S07 hiện tại (thiết kế G72):
- lệnh gốc M30;
- bồi lệnh S07A từ M15/H1/H4, tối đa 2 lệnh bồi, 3 lệnh mở, lệnh bồi luôn 1,5%;
- chi phí khắt khe G68.

**Nhãn** gắn cho lệnh gốc, tính ở nến tín hiệu M30.

Báo cáo hai phạm vi:
- **sổ đầy đủ** (gốc + bồi);
- **chỉ lệnh gốc**.

## Phần 1 — nhãn có thật không (cách G79, tập con lệnh gốc)

Lệnh gốc có nhãn so với lệnh gốc không nhãn, theo từng kỳ: 2018–2021, train 2021–2023, validate 2024–06/2025, test 07/2025–06/2026. Thêm kiểm định hoán vị (5000 lần).

**Nhãn được coi là thật** khi nhóm có nhãn tốt hơn ở ≥ 3/4 kỳ và p < 0,05.

## Phần 2 — mức rủi ro (lệnh gốc)

| Mã | Có nhãn | Không nhãn | Ghi chú |
|---|---|---|---|
| K0 | 1,5% | 1,5% | hiện tại |
| K1 | 1,5% | 1,0% | vừa trần 1,5% của EA |
| K3 | 1,5% | 0,75% | vừa trần |
| K2 | 2,0% | 1,5% | cần nâng trần EA |

**Đo lường** (lãi kép theo thứ tự đóng lệnh), trên hai giai đoạn: 09/2018–06/2026 và 07/2021–06/2026:
- %/năm;
- DD lớn nhất;
- DD p90 trong cửa sổ 1 năm;
- xác suất chạm 20% và 30% trong cửa sổ 1 năm;
- tỉ số %/năm ÷ DD p90.

## Tiêu chí (chốt trước, sổ đầy đủ)

Chỉ xét Phần 2 nếu Phần 1 đạt. Một mức K thay K0 khi đủ cả ba điều:
1. Tỉ số %/năm ÷ DD p90 cao hơn K0 ở **cả hai** giai đoạn.
2. Xác suất chạm 30% ≤ K0 ở cả hai giai đoạn.
3. %/năm ≥ 85% của K0 ở cả hai giai đoạn.

Nếu nhiều mức đạt:
- ưu tiên mức **vừa trần hiện tại** (K1, K3);
- trong đó chọn mức có tỉ số cao nhất ở 07/2021–06/2026.

K2 chỉ được chọn nếu K1 và K3 đều không đạt.

Đạt → EA tính nhãn ở nến tín hiệu S07 và đặt trọng số rủi ro cho lệnh không nhãn. Không đạt → giữ 1,5% cho mọi lệnh.

## Đầu ra

`research/long/g82_label_risk.py`, báo cáo `reports/2026-10-10-g82-ribbon-label-risk.md`.
