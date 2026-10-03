# Đặc tả S02 Break Retest v1

Ngày 03/10/2026. Trạng thái: thiết kế CONFIRMED bởi người dùng (O-19); mọi con số trong mục 10 là seed PROPOSED, chỉ được khóa sau khi kiểm chứng ở mục 13. Nguồn: master specification v1.4 mục 2, 4.4, 4.7, 5, 6.2, phụ lục B, phụ lục D (O-16, O-17, O-18). Tài liệu này thay thế phần định nghĩa key level của prototype `Setups/BreakRetest.mqh` (range 20 nến M5).

## 1. Quyết định đã chốt

| Mã | Quyết định |
| --- | --- |
| S02-D1 | Hai profile SCALP và SWING xây cùng lúc, cùng logic, khác khung thời gian và tham số. |
| S02-D2 | Key level là vùng hợp lưu: tối thiểu 2 trong 3 nguồn độc lập trùng nhau trong dung sai theo ATR. |
| S02-D3 | Dung sai hợp lưu ≤ 0,25×ATR14 của khung context (H1 cho SCALP, H4 cho SWING); không dùng pip cố định. |
| S02-D4 | Hai nguồn chỉ được tính riêng khi cực trị của chúng nằm ở hai nến khác nhau; cùng một nến tạo ra hai mức chỉ tính là một nguồn. |
| S02-D5 | Bộ nguồn SCALP: PDH/PDL, đỉnh/đáy phiên (Á, London, New York), swing H1. Bộ nguồn SWING: PDH/PDL, đỉnh/đáy tuần trước, swing H4. |
| S02-D6 | Ngược xu hướng HTF không chặn lệnh, chỉ nhân risk với hệ số 0,5; HTF trung tính hoặc cùng hướng giữ 1,0. |
| S02-D7 | Không lọc theo phiên; thay bằng chặn khi spread giãn bất thường (mục 7). |
| S02-D8 | Loại lệnh theo O-17: MARKET, BUY/SELL LIMIT, BUY/SELL STOP. Lệnh chờ chỉ được bật sau REQ-021. |

## 2. Chuỗi sự kiện và máy trạng thái

`Context → Location → Event (break) → Reaction (acceptance, retest, trigger) → Entry → Invalidation → Outcome`

```text
IDLE -> DETECTED -> ARMED -> RETESTING -> TRIGGERED -> ORDER_INTENT (Risk Kernel)
  mọi trạng thái trước TRIGGERED -> INVALIDATED | EXPIRED | BLOCKED (kèm reason code)
```

Mọi quyết định chỉ dùng nến đã đóng của khung entry (series index 1). Mỗi symbol, mỗi profile có một engine riêng; engine được gắn với symbol theo tên canonical, không theo số thứ tự dòng.

## 3. Profile

| Thuộc tính | SCALP | SWING |
| --- | --- | --- |
| Khung entry | M5 | H1 |
| Khung context, ATR dung sai, swing | H1 | H4 |
| Nguồn level | PDH/PDL, đỉnh/đáy phiên, swing H1 | PDH/PDL, đỉnh/đáy tuần trước, swing H4 |
| Cửa sổ acceptance / retest / trigger (nến entry) | 2 / 12 / 3 | 2 / 10 / 3 |
| TTL candidate sau TRIGGERED | 2 nến M5 | 2 nến H1 |
| Thời gian giữ dự kiến | phút đến 3 giờ | 1 đến 10 ngày |

## 4. Location: vùng hợp lưu

### 4.1 Nguồn level

- **PDH/PDL:** đỉnh và đáy của nến D1 đã đóng gần nhất theo ngày giao dịch của broker (server time). Đây là level kỹ thuật; quy tắc ngày của FTMO (Prague) chỉ áp cho risk, không đổi level.
- **Đỉnh/đáy phiên (SCALP):** cực trị của phiên đã kết thúc gần nhất trong ngày. Cửa sổ UTC seed: Á 00:00–07:00, London 07:00–12:00, New York 12:00–21:00; điều chỉnh DST là tham số cấu hình có kiểm thử.
- **Đỉnh/đáy tuần trước (SWING):** cực trị nến W1 đã đóng gần nhất.
- **Swing H1/H4:** fractal xác nhận với n = 3 nến mỗi bên; lấy các swing chưa bị phá trong lookback 5 ngày (H1) hoặc 8 tuần (H4).

Mỗi level lưu: nguồn, giá, thời điểm của nến tạo cực trị, khung thời gian.

### 4.2 Gom vùng

1. Sắp xếp toàn bộ level theo giá.
2. Gom thành cụm khi khoảng cách giữa level kế tiếp ≤ tol = 0,25×ATR14(context).
3. Một cụm là **vùng hợp lưu hợp lệ** khi có ít nhất 2 nguồn khác loại và thời điểm nến cực trị khác nhau (S02-D4).
4. Vùng = [giá thấp nhất, giá cao nhất] của cụm. Bề rộng vùng > 0,5×ATR14(context) thì loại (`ZONE_TOO_WIDE`).
5. Nhiều vùng cùng lúc: mỗi vùng chạy một engine con; tối đa 1 candidate đang mở trên mỗi symbol và profile.

## 5. Context: xu hướng HTF

Lấy hai swing high và hai swing low xác nhận gần nhất trên khung context:

- HH và HL → `UP`; LH và LL → `DOWN`; trường hợp khác → `NEUTRAL`.
- Break cùng hướng hoặc `NEUTRAL` → `htf_risk_modifier = 1,0`; ngược hướng → `0,5` (S02-D6), ghi reason `HTF_COUNTER_TREND`.

## 6. Chuyển trạng thái

| Bước | Điều kiện (ví dụ cho lệnh mua; lệnh bán đối xứng) | Reason khi thất bại |
| --- | --- | --- |
| DETECTED | Nến đóng cửa trên đỉnh vùng ≥ 0,10×ATR14(entry); thân nến ≥ 50% biên độ nến | — |
| ARMED | Trong 2 nến tiếp theo không có nến đóng cửa trở lại trong vùng | `ACCEPTANCE_FAILED`, `ACCEPTANCE_EXPIRED` |
| RETESTING | Trong cửa sổ retest, low chạm đỉnh vùng + 0,15×ATR mà nến không đóng dưới đáy vùng − 0,10×ATR | `RETEST_EXPIRED`, `LEVEL_LOST` |
| TRIGGERED | Sau retest, nến đóng tăng, thân ≥ 40% biên độ và đóng cao hơn close của nến retest + 0,05×ATR | `TRIGGER_EXPIRED` |
| INVALIDATED | Bất kỳ nến nào đóng dưới đáy vùng − 0,10×ATR, hoặc có break ngược chiều | `THESIS_INVALIDATED` |

Nến trùng thời điểm hoặc lùi thời gian không làm đổi trạng thái (`DUPLICATE_CLOSED_BAR`, `OUT_OF_ORDER_CLOSED_BAR`), giữ nguyên như prototype.

## 7. Bộ lọc thực thi

- **Spread tương đối:** spread hiện tại ≤ 2,0 × median spread của 288 nến M5 gần nhất (lấy từ `MqlRates.spread`) → nếu vượt: `SPREAD_ABNORMAL`.
- **Spread so với stop:** spread ≤ 0,25 × khoảng cách entry–SL → nếu vượt: `SPREAD_TOO_WIDE_FOR_STOP`.
- **Không có News Center (O-16):** không chặn theo tin; trạng thái tin ghi `NEWS_UNAVAILABLE_ACCEPTED` trong audit của candidate.

## 8. Entry, SL, TP

- **SL:** cực trị của nhịp retest (low thấp nhất từ ARMED tới TRIGGERED đối với lệnh mua) trừ buffer = max(0,10×ATR14(entry), 1,5×spread hiện tại); làm tròn theo tick size về phía xa entry; phải thỏa stops level và freeze level.
- **TP:** level cấu trúc gần nhất theo hướng lệnh trong bộ nguồn của profile (một nguồn đơn lẻ cũng được dùng làm target), cách entry ≥ 1R thô. Không có target cấu trúc thì loại (`NO_STRUCTURAL_TARGET`); không dùng R cố định thay thế.
- **RR ròng:** (|TP − entry| − chi phí) / (|entry − SL| + chi phí) ≥ 1,5 (SCALP) hoặc 2,0 (SWING); chi phí = spread + commission ước tính + swap dự kiến (SWING).
- **Loại lệnh theo profile và symbol (S02-D8), mỗi cấu hình chỉ chọn một mode:**
  - `MARKET_ON_TRIGGER` (mặc định): vào lệnh tại giá thị trường sau nến TRIGGERED.
  - `LIMIT_AT_ZONE`: đặt LIMIT tại đỉnh vùng ngay khi ARMED; hết hạn khi hết cửa sổ retest; khớp lệnh mà chưa có trigger được ghi là entry mạo hiểm và chỉ dùng khi đã có số liệu chứng minh.
  - `STOP_ABOVE_TRIGGER`: đặt STOP cách high của nến trigger 1 tick; hết hạn sau TTL candidate.
  - Lệnh chờ bị chặn tới khi REQ-021 (TC-046 đến TC-051) đạt trên broker.

## 9. Tự động thích ứng theo symbol, loại tài khoản và leverage

Mục tiêu: người dùng không phải nhập lot, pip value, SL/TP theo symbol hay theo loại tài khoản (ví dụ Standard 1 lot = 100.000, Micro 1 lot = 1.000, Ultra Low Standard spread thấp hơn).

| Thông tin | Nguồn tự động | Trạng thái |
| --- | --- | --- |
| Contract size, tick size, tick value, digits | `SymbolInfo*` | Đã đọc (`SymbolSpecAdapter`) |
| Volume min, max, step | `SymbolInfo*` | Đã đọc |
| Stops level, freeze level, filling, expiration | `SymbolInfo*` | Đã đọc |
| Lỗ tại SL cho 1 lot, theo tiền tài khoản | `OrderCalcProfit` (đã gồm contract size và quy đổi tiền) | Đã dùng khi tính lot |
| Margin cần cho lệnh (đã gồm leverage tài khoản và leverage riêng từng symbol) | `OrderCalcMargin` | Đã dùng |
| Leverage tài khoản | `ACCOUNT_LEVERAGE` | Cần thêm vào account snapshot để audit |
| Swap long/short | `SYMBOL_SWAP_LONG/SHORT`, `SYMBOL_SWAP_MODE` | Cần thêm cho chi phí SWING |
| Spread hiện tại và median | Quote hiện tại, `MqlRates.spread` | Cần thêm (mục 7) |
| Commission | Không có trong thông số symbol; học từ `DEAL_COMMISSION` của các deal gần nhất theo symbol | Cần thêm; khi chưa có deal nào thì dùng hồ sơ chi phí của tài khoản (mặc định 0 với loại "không phí hoa hồng") và gắn cờ `COST_ESTIMATED` |
| Tên symbol khác nhau theo loại tài khoản (hậu tố) | Symbol registry, chặn riêng từng symbol (SYM-02) | Đã có |

Quy tắc:

1. SL và TP tính bằng **giá** từ cấu trúc và ATR, nên không phụ thuộc loại tài khoản. Loại tài khoản chỉ đổi lot, chi phí và margin.
2. Lot = risk tiền ÷ lỗ tại SL cho 1 lot (`OrderCalcProfit`), làm tròn xuống theo volume step; dưới volume min thì loại (`VOLUME_BELOW_MINIMUM`), không làm tròn lên. Cùng một mức risk, tài khoản Micro tự cho lot lớn gấp 100 lần Standard.
3. Leverage chỉ ảnh hưởng margin, không ảnh hưởng mức lỗ. Sau lệnh, margin level phải ≥ 300% (seed) và margin tự do phải còn dương sau khi cộng các vị thế đang mở bị dừng lỗ (stress).
4. Thông số quan trọng đổi (contract size, tick value, volume, leverage, stops level) → hủy candidate đang mở và tính lại; ghi `INSTRUMENT_SPEC_CHANGED`.
5. Các input thủ công sau sẽ bị bỏ khi S02 v1 vào runtime: `InpLiveStopBufferTicks`, `InpLiveTargetRMultiple`, `InpLiveMaxSpreadPoints`, `InpLiveMinimumNetRR`. Chỉ còn người dùng duyệt các giới hạn risk (O-04).

## 10. Tham số seed (PROPOSED)

| Tham số | SCALP | SWING |
| --- | --- | --- |
| ATR | ATR14(M5) cho buffer entry; ATR14(H1) cho dung sai | ATR14(H1); ATR14(H4) |
| Dung sai hợp lưu | 0,25×ATR(context) | 0,25×ATR(context) |
| Bề rộng vùng tối đa | 0,5×ATR(context) | 0,5×ATR(context) |
| Break buffer / thân nến | 0,10×ATR / 50% | 0,10×ATR / 50% |
| Retest tolerance / invalidation buffer | 0,15 / 0,10×ATR | 0,15 / 0,10×ATR |
| Trigger progress / thân nến | 0,05×ATR / 40% | 0,05×ATR / 40% |
| SL buffer | max(0,10×ATR, 1,5×spread) | max(0,10×ATR, 1,5×spread) |
| RR ròng tối thiểu | 1,5 | 2,0 |
| HTF counter-trend modifier | 0,5 | 0,5 |
| Spread guard | 2,0×median; ≤ 0,25×stop | 2,0×median; ≤ 0,25×stop |

## 11. Risk

`FinalRisk = BaseRisk × htf_risk_modifier × các hệ số khác của mục 5.4`, luôn bị chặn bởi giới hạn mỗi lệnh, portfolio, exposure theo đồng tiền và sàn FTMO (phụ lục B). AI và UI không được tăng risk. BaseRisk và các giới hạn lấy từ `Risk/RiskLimitsProfile.mqh` (O-04, phụ lục D): FTMO 2-Step 0,50% mỗi lệnh, FTMO 1-Step 0,30% mỗi lệnh; ngược HTF còn một nửa.

## 12. Audit của candidate

Mỗi chuyển trạng thái ghi: candidate_id, symbol canonical và broker, profile, config version, vùng (các nguồn, giá, thời điểm nến), ATR các khung, xu hướng HTF và modifier, spread và median, entry/SL/TP, RR ròng, chi phí và cờ ước tính, entry mode, reason codes, thời điểm UTC.

## 13. Kiểm thử và kiểm chứng

| ID | Kịch bản và kết quả mong đợi |
| --- | --- |
| TC-S02-01 | PDH trùng swing H1 trong dung sai → vùng hợp lệ; chỉ một nguồn → không có vùng |
| TC-S02-02 | Đỉnh phiên London và PDH cùng một nến → tính một nguồn, không đủ hợp lưu |
| TC-S02-03 | Dung sai co giãn theo ATR: cùng hình giá cho kết quả như nhau trên EURUSD, XAUUSD, BTCUSD |
| TC-S02-04 | Đủ break → acceptance → retest → trigger theo đúng thứ tự → TRIGGERED |
| TC-S02-05 | Đóng ngược vào vùng trước acceptance → ACCEPTANCE_FAILED; hết cửa sổ retest → RETEST_EXPIRED |
| TC-S02-06 | Ngược HTF → risk × 0,5 và có reason HTF_COUNTER_TREND; HTF trung tính → 1,0 |
| TC-S02-07 | Spread vượt 2× median hoặc vượt 0,25×stop → bị loại có reason |
| TC-S02-08 | Không có target cấu trúc hoặc RR ròng thấp hơn ngưỡng → bị loại |
| TC-S02-09 | Cùng risk tiền: tài khoản Standard và Micro cho lot khác nhau 100 lần, lỗ tại SL như nhau |
| TC-S02-10 | Lot sau làm tròn dưới volume min → VOLUME_BELOW_MINIMUM, không làm tròn lên |
| TC-S02-11 | Spec hoặc leverage đổi giữa chừng → candidate bị hủy, ghi INSTRUMENT_SPEC_CHANGED |
| TC-S02-12 | Restart giữa chừng → engine khôi phục đúng trạng thái, không tạo candidate trùng |
| TC-S02-13 | SCALP và SWING trên cùng symbol chạy độc lập, không dùng chung trạng thái |

Kiểm chứng trên MT5 Strategy Tester với 5 symbol mặc định, mỗi profile, ít nhất 12 tháng lịch sử: tần suất tín hiệu, tỷ lệ thắng, expectancy theo R sau chi phí, MFE/MAE, thời gian tới 1R, kết quả theo phiên và theo trạng thái HTF. Ngưỡng nghiệm thu được người dùng chốt sau khi có số liệu đầu tiên; chỉ khi đó tham số mục 10 mới chuyển từ PROPOSED sang CONFIRMED.

## 14. Kế hoạch triển khai

1. Module Location: tính level theo từng nguồn, gom vùng, kiểm tra độc lập; fixture và oracle Python (TC-S02-01 đến 03).
2. Module HTF structure (TC-S02-06).
3. Mở rộng engine S02 hiện có thành engine theo vùng và profile, giữ các bảo vệ nến trùng/lùi thời gian và checkpoint (TC-S02-04, 05, 12, 13).
4. Instrument auto-profile: leverage, swap, median spread, commission học từ deal (TC-S02-07, 09, 10, 11).
5. SL/TP/RR theo cấu trúc, nối vào Risk Kernel và risk modifier (TC-S02-08); bỏ các input thủ công ở mục 9.
6. Compile, chạy Strategy Tester, tạo báo cáo kiểm chứng; hiển thị vùng, trạng thái và lý do trên Dashboard › Market.
7. Lệnh chờ LIMIT/STOP chỉ sau REQ-021.

## 15. Còn mở

- Ngưỡng nghiệm thu của Strategy Tester (sau lần chạy đầu).
- Cửa sổ phiên có điều chỉnh DST hay giữ UTC cố định.
