# G56 A: bản đồ yếu tố (chỉ dữ liệu MT5)

Kế hoạch: `docs/superpowers/plans/2026-10-07-g56-factor-atlas.md` (đăng ký trước). Hiệu ứng = lợi nhuận tiến theo hướng giả thuyết, đơn vị ATR, đã trừ trôi giá; dấu âm = chiều ngược lại. q = Benjamini–Hochberg trên train.

## H1: 208 phép thử, chọn trên train 27, sống sót validate + test + chi phí 1

| Yếu tố | Tầm | Hướng | Train (q) | Validate (p) | Test | Sau phí val / test | Sống sót |
|---|---|---|---|---|---|---|---|
| PDHL_SWEEP | 12 | ngược giả thuyết | -0.310 (0.000) | -0.212 (0.000) | -0.246 | -0.019 / +0.144 | không |
| RSI_REVERT | 24 | theo giả thuyết | +0.345 (0.000) | +0.097 (0.194) | +0.090 | -0.122 / -0.028 | không |
| NR7_BREAK | 4 | ngược giả thuyết | -0.086 (0.000) | -0.048 (0.003) | -0.017 | -0.189 / -0.089 | không |
| MACD_FLIP_TREND | 1 | theo giả thuyết | +0.071 (0.000) | +0.061 (0.000) | +0.055 | -0.193 / -0.055 | không |
| RSI_REVERT | 12 | theo giả thuyết | +0.194 (0.000) | +0.094 (0.052) | +0.087 | -0.118 / -0.021 | không |
| ADX_PULLBACK | 4 | ngược giả thuyết | -0.147 (0.000) | -0.036 (0.311) | -0.124 | -0.220 / +0.019 | không |
| MON_GAP_FILL | 24 | theo giả thuyết | +0.429 (0.000) | +0.074 (0.576) | -0.331 | -0.185 / -0.451 | không |
| PDHL_SWEEP | 4 | ngược giả thuyết | -0.129 (0.000) | -0.073 (0.010) | -0.099 | -0.157 / -0.006 | không |
| MACD_FLIP_TREND | 4 | theo giả thuyết | +0.122 (0.000) | +0.191 (0.000) | +0.116 | -0.062 / +0.009 | không |
| NR7_BREAK | 12 | ngược giả thuyết | -0.111 (0.001) | -0.013 (0.674) | +0.003 | -0.224 / -0.112 | không |
| HOUR_14 | 4 | theo giả thuyết | +0.074 (0.001) | +0.012 (0.639) | +0.014 | -0.221 / -0.060 | không |
| ADX_PULLBACK | 24 | ngược giả thuyết | -0.290 (0.002) | -0.051 (0.602) | -0.149 | -0.206 / +0.037 | không |
| ADX_PULLBACK | 1 | ngược giả thuyết | -0.055 (0.002) | -0.038 (0.032) | -0.041 | -0.218 / -0.063 | không |
| MON_AFTER_GREEN_FRI | 12 | theo giả thuyết | +0.330 (0.002) | +0.043 (0.708) | -0.082 | -0.227 / -0.253 | không |
| PDHL_SWEEP | 24 | ngược giả thuyết | -0.217 (0.002) | -0.255 (0.000) | -0.272 | +0.024 / +0.176 | **CÓ** |
| RISING_WEDGE_BREAK | 1 | theo giả thuyết | +0.071 (0.003) | +0.080 (0.000) | +0.040 | -0.205 / -0.088 | không |
| HOUR_15 | 4 | theo giả thuyết | +0.057 (0.004) | +0.014 (0.505) | +0.009 | -0.210 / -0.062 | không |
| ADX_PULLBACK | 12 | ngược giả thuyết | -0.204 (0.004) | -0.045 (0.495) | -0.187 | -0.211 / +0.078 | không |
| MON_AFTER_RED_FRI | 24 | theo giả thuyết | +0.362 (0.011) | -0.001 (0.996) | +0.040 | -0.106 / +0.074 | không |
| HOUR_14 | 12 | theo giả thuyết | +0.089 (0.013) | +0.057 (0.141) | +0.037 | -0.137 / +0.011 | không |
| MON_AFTER_GREEN_FRI | 24 | theo giả thuyết | +0.340 (0.029) | -0.079 (0.617) | -0.260 | -0.415 / -0.505 | không |
| PRESSURE_3 | 24 | theo giả thuyết | +0.243 (0.044) | +0.174 (0.142) | +0.024 | -0.041 / -0.040 | không |
| NR7_BREAK | 24 | ngược giả thuyết | -0.101 (0.053) | +0.005 (0.917) | +0.072 | -0.243 / -0.185 | không |
| FRI_FADE_WEEK | 24 | ngược giả thuyết | -0.315 (0.056) | +0.007 (0.963) | +0.136 | -0.222 / -0.206 | không |
| HOUR_13 | 12 | theo giả thuyết | +0.079 (0.057) | +0.064 (0.136) | +0.030 | -0.134 / -0.001 | không |
| HOUR_07 | 4 | ngược giả thuyết | -0.073 (0.090) | -0.042 (0.178) | -0.009 | -0.249 / -0.140 | không |
| HOUR_15 | 12 | theo giả thuyết | +0.065 (0.098) | +0.027 (0.434) | +0.020 | -0.159 / -0.003 | không |

## M15: 150 phép thử, chọn trên train 17, sống sót validate + test + chi phí 1

| Yếu tố | Tầm | Hướng | Train (q) | Validate (p) | Test | Sau phí val / test | Sống sót |
|---|---|---|---|---|---|---|---|
| ROUND_BREAK | 24 | theo giả thuyết | +0.287 (0.000) | +0.168 (0.001) | +0.197 | +0.005 / +0.047 | **CÓ** |
| ADX_PULLBACK | 2 | ngược giả thuyết | -0.117 (0.000) | -0.076 (0.000) | -0.028 | -0.157 / -0.152 | không |
| HOUR_21 | 8 | theo giả thuyết | +0.246 (0.000) | +0.272 (0.000) | +0.399 | -0.211 / -0.183 | không |
| ADX_PULLBACK | 8 | ngược giả thuyết | -0.224 (0.000) | -0.126 (0.012) | -0.071 | -0.108 / -0.111 | không |
| PDHL_SWEEP | 24 | ngược giả thuyết | -0.375 (0.000) | -0.174 (0.157) | -0.428 | -0.039 / +0.278 | không |
| HOUR_21 | 2 | theo giả thuyết | +0.065 (0.006) | +0.044 (0.034) | +0.055 | -0.459 / -0.559 | không |
| BB_SQUEEZE_BREAK | 2 | ngược giả thuyết | -0.091 (0.006) | -0.097 (0.006) | -0.094 | -0.259 / -0.176 | không |
| PDHL_SWEEP | 8 | ngược giả thuyết | -0.160 (0.009) | -0.064 (0.326) | -0.118 | -0.161 / -0.046 | không |
| FRI | 8 | theo giả thuyết | +0.437 (0.009) | -0.125 (0.564) | +0.049 | -0.442 / -0.126 | không |
| FALLING_WEDGE_BREAK | 2 | theo giả thuyết | +0.071 (0.022) | +0.099 (0.000) | +0.043 | -0.201 / -0.182 | không |
| HOUR_02 | 2 | theo giả thuyết | +0.055 (0.027) | +0.013 (0.610) | -0.014 | -0.252 / -0.179 | không |
| STREAK_6 | 2 | ngược giả thuyết | -0.071 (0.027) | -0.021 (0.516) | -0.013 | -0.222 / -0.172 | không |
| HOUR_19 | 8 | ngược giả thuyết | -0.090 (0.027) | -0.153 (0.000) | -0.250 | -0.101 / +0.029 | không |
| HOUR_21 | 24 | theo giả thuyết | +0.261 (0.027) | +0.150 (0.201) | +0.302 | -0.274 / -0.217 | không |
| RISING_WEDGE_BREAK | 2 | theo giả thuyết | +0.063 (0.046) | +0.006 (0.879) | +0.034 | -0.305 / -0.194 | không |
| MACD_FLIP_TREND | 24 | theo giả thuyết | +0.180 (0.046) | +0.037 (0.667) | +0.229 | -0.201 / +0.059 | không |
| BB_SQUEEZE_BREAK | 8 | ngược giả thuyết | -0.161 (0.058) | -0.200 (0.010) | -0.040 | -0.158 / -0.233 | không |


