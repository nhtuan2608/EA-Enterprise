# G56 B + C: setup từ yếu tố sống sót, walk-forward (chỉ dữ liệu MT5)

Kế hoạch: `docs/superpowers/plans/2026-10-07-g56-factor-atlas.md` (B + C đăng ký trước khi chạy). R sau phí.

## SW1 (H1, PDHL_SWEEP)

Walk-forward gộp: -0.043R n=3000 thắng 27% tổng -129.1R DD 142.5R; năm dương 5/12; ngẫu nhiên p90 +0.013R → **KHÔNG ĐẠT**

| Năm kiểm | Cấu hình chọn trên train | Symbol giữ | Kết quả năm kiểm |
|---|---|---|---|
| 2014 | dừng 2.0 ATR, TP3R, MACD tắt (train -0.018R) | GBPUSD, USDJPY | -0.178R n=225 thắng 21% tổng -40.2R DD 49.2R |
| 2015 | dừng 2.0 ATR, TRAIL3, MACD bật (train -0.058R) | – | n=0 |
| 2016 | dừng 1.5 ATR, TRAIL3, MACD bật (train +0.017R) | USDJPY | +0.024R n=119 thắng 27% tổng +2.9R DD 16.0R |
| 2017 | dừng 1.5 ATR, TRAIL3, MACD bật (train +0.031R) | GBPUSD, USDJPY | -0.102R n=250 thắng 27% tổng -25.4R DD 37.2R |
| 2018 | dừng 1.5 ATR, TRAIL3, MACD bật (train +0.014R) | GBPUSD, USDJPY | -0.098R n=244 thắng 24% tổng -23.9R DD 47.0R |
| 2019 | dừng 2.0 ATR, TRAIL3, MACD tắt (train -0.033R) | GBPUSD, USDJPY | -0.011R n=271 thắng 29% tổng -2.9R DD 44.7R |
| 2020 | dừng 2.0 ATR, TRAIL3, MACD tắt (train -0.085R) | GBPUSD | +0.068R n=148 thắng 33% tổng +10.1R DD 19.1R |
| 2021 | dừng 2.0 ATR, TRAIL3, MACD bật (train -0.050R) | GBPUSD, XAUUSD | +0.053R n=240 thắng 32% tổng +12.8R DD 30.5R |
| 2022 | dừng 2.0 ATR, TP3R, MACD bật (train -0.017R) | EURUSD, GBPUSD, USDJPY | +0.183R n=262 thắng 31% tổng +48.0R DD 15.7R |
| 2023 | dừng 2.0 ATR, TP3R, MACD bật (train +0.054R) | EURUSD, GBPUSD, USDJPY, XAUUSD | -0.075R n=403 thắng 24% tổng -30.3R DD 71.6R |
| 2024 | dừng 2.0 ATR, TP3R, MACD bật (train +0.064R) | EURUSD, GBPUSD, USDJPY, XAUUSD, BTCUSD | -0.152R n=544 thắng 22% tổng -82.7R DD 119.7R |
| 2025 | dừng 2.0 ATR, TRAIL3, MACD bật (train -0.008R) | USDJPY, XAUUSD, BTCUSD | +0.008R n=294 thắng 33% tổng +2.3R DD 31.3R |

C — cố định kiểu thoát (dừng lỗ và lọc vẫn chọn trên train), SW1:

| Kiểu thoát | Walk-forward gộp | Năm dương |
|---|---|---|
| TIME | +0.004R n=1885 thắng 37% tổng +7.9R DD 61.2R | 4/12 |
| TP2R | -0.086R n=1096 thắng 31% tổng -94.4R DD 95.4R | 2/12 |
| TP3R | -0.072R n=2001 thắng 24% tổng -143.4R DD 176.5R | 3/12 |
| RUNNER | -0.088R n=578 thắng 45% tổng -50.9R DD 53.2R | 0/12 |
| TRAIL3 | -0.023R n=2779 thắng 28% tổng -63.5R DD 115.6R | 5/12 |

## SC1 (M15, ROUND_BREAK)

Walk-forward gộp: -0.013R n=490 thắng 26% tổng -6.4R DD 60.5R; năm dương 0/2; ngẫu nhiên p90 +0.072R → **KHÔNG ĐẠT**

| Năm kiểm | Cấu hình chọn trên train | Symbol giữ | Kết quả năm kiểm |
|---|---|---|---|
| 2024 | dừng 2.0 ATR, TP3R, MACD tắt (train -0.064R) | XAUUSD | -0.013R n=490 thắng 26% tổng -6.4R DD 60.5R |
| 2025 | dừng 2.0 ATR, TP2R, MACD tắt (train -0.061R) | – | n=0 |

C — cố định kiểu thoát (dừng lỗ và lọc vẫn chọn trên train), SC1:

| Kiểu thoát | Walk-forward gộp | Năm dương |
|---|---|---|
| TIME | n=0 | 0/2 |
| TP2R | n=0 | 0/2 |
| TP3R | +0.006R n=965 thắng 26% tổng +5.7R DD 62.4R | 1/2 |
| RUNNER | n=0 | 0/2 |
| TRAIL3 | n=0 | 0/2 |

