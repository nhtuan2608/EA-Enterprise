# G131: đỉnh/đáy cạn đà sau nhiều lần RSI quá mua/quá bán — kết quả

Kế hoạch: `plans/2026-10-20-g131-rsi-exhaustion-top.md`. XAUUSD H4 (từ M30, 03/2018+). Train 03/2018–2021, validate 2022–2025. 2026 không phải test sạch (ví dụ thiết kế nằm trong 01–03/2026). Chi phí khắt khe. Ô: số lệnh / R mỗi lệnh (SL trên đỉnh test lại, thoát ở EMA200 H4 hoặc RSI cực trị bên kia).

## 18 biến thể

| Bối cảnh | Đỉnh | Vào | Train | Validate | Bán (train · val) | Mua (train · val) | Ngẫu nhiên validate | p | Chọn? |
|---|---|---|---|---|---|---|---|---|---|
| X1 | T1 | E1 | 1 / -1.01 | 4 / -1.01 | 1 / -1.01 · 4 / -1.01 | — · — | +nan | nan |  |
| X1 | T1 | E2 | 4 / +0.89 | 2 / +0.16 | 3 / +0.64 · 2 / +0.16 | 1 / +1.63 · — | +nan | nan |  |
| X1 | T1 | E3 | 5 / +0.51 | 6 / -0.62 | 4 / +0.23 · 6 / -0.62 | 1 / +1.63 · — | +nan | nan |  |
| X1 | T2 | E1 | — | 3 / -1.01 | — · 3 / -1.01 | — · — | +nan | nan |  |
| X1 | T2 | E2 | 2 / +1.44 | 2 / -1.05 | 1 / +1.25 · 2 / -1.05 | 1 / +1.63 · — | +nan | nan |  |
| X1 | T2 | E3 | 2 / +1.44 | 5 / -1.03 | 1 / +1.25 · 5 / -1.03 | 1 / +1.63 · — | +nan | nan |  |
| X2 | T1 | E1 | — | 2 / -1.01 | — · 2 / -1.01 | — · — | +nan | nan |  |
| X2 | T1 | E2 | 1 / -1.01 | 2 / +0.16 | 1 / -1.01 · 2 / +0.16 | — · — | +nan | nan |  |
| X2 | T1 | E3 | 1 / -1.01 | 4 / -0.42 | 1 / -1.01 · 4 / -0.42 | — · — | +nan | nan |  |
| X2 | T2 | E1 | — | 2 / -1.01 | — · 2 / -1.01 | — · — | +nan | nan |  |
| X2 | T2 | E2 | — | 1 / -1.01 | — · 1 / -1.01 | — · — | +nan | nan |  |
| X2 | T2 | E3 | — | 3 / -1.01 | — · 3 / -1.01 | — · — | +nan | nan |  |
| X3 | T1 | E1 | — | 5 / -0.46 | — · 4 / -0.32 | — · 1 / -1.01 | +nan | nan |  |
| X3 | T1 | E2 | 2 / +0.33 | 2 / +1.65 | 2 / +0.33 · 2 / +1.65 | — · — | +nan | nan |  |
| X3 | T1 | E3 | 2 / +0.33 | 7 / +0.15 | 2 / +0.33 · 6 / +0.34 | — · 1 / -1.01 | +nan | nan |  |
| X3 | T2 | E1 | — | 4 / -0.32 | — · 3 / -0.09 | — · 1 / -1.01 | +nan | nan |  |
| X3 | T2 | E2 | — | 2 / +1.65 | — · 2 / +1.65 | — · — | +nan | nan |  |
| X3 | T2 | E3 | — | 6 / +0.34 | — · 5 / +0.61 | — · 1 / -1.01 | +nan | nan |  |

Ngẫu nhiên / p chỉ tính cho biến thể dương ở cả hai kỳ với ≥ 10 lệnh mỗi kỳ.

## 2026 (không phải test sạch) — biến thể mặc định ('X1', 'T1', 'E3')

| Vào lệnh (server) | Chiều | R |
|---|---|---|

2026: — (bán —, mua —).

## Tất cả lệnh của biến thể đó (train + validate)

| Vào lệnh | Chiều | R | Kỳ |
|---|---|---|---|
| 2020-03-10 04:00 | BÁN | +1.25 | train |
| 2020-05-19 08:00 | BÁN | -1.01 | train |
| 2020-07-10 20:00 | BÁN | -1.01 | train |
| 2021-01-07 04:00 | BÁN | +1.68 | train |
| 2022-03-01 04:00 | BÁN | -1.01 | validate |
| 2022-03-10 04:00 | BÁN | +1.34 | validate |
| 2023-07-25 16:00 | BÁN | -1.02 | validate |
| 2024-04-11 12:00 | BÁN | -1.01 | validate |
| 2024-08-15 16:00 | BÁN | -1.01 | validate |
| 2024-10-24 20:00 | BÁN | -1.02 | validate |
| 2020-11-02 04:00 | MUA | +1.63 | train |

