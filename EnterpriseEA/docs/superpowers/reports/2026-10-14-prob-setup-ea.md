# ProbSetupEA: EA chọn lệnh theo xác suất (G112 + G114)

Ngày 14/10/2026. Mã nguồn:
- `ProbSetupEA.mq5`;
- `ProbSetup/ProbSignals.mqh`, `ProbSetup/ProbDecide.mqh`;
- `ProbSetup/ProbTables.mqh`, được sinh tự động bởi `research/long/g114_export_mql.py` từ `research/long/out/g114_frozen.json`.

EA chưa được chép lên MT5 hay VPS.

## 1. Kết luận trước: chưa có setup nào đạt chuẩn

- G114 (báo cáo `2026-10-14-g114-prob*.md`): không mã nào, không mô hình nào đạt tiêu chí đăng ký trước, ở M5, M15 hay M30. Các tiêu chí là:
  - cận dưới > 0 ở cả train và validate;
  - ít nhất 100 lệnh;
  - hơn chọn ngẫu nhiên với p < 0,05;
  - xác suất khớp tốt hơn mức chung.
- Vì vậy EA **mặc định chạy chế độ bóng**: chỉ ghi lệnh ảo lên panel và CSV, không đặt lệnh. Bảng xác suất mang cờ `PS_PASSED = false`.
- Cấu hình của EA là C1/C2 vàng M15, chọn bằng cộng log-LR + isotonic + cận dưới EV, mỗi lúc một lệnh. Kết quả **ngoài mẫu** (cuốn chiếu theo tháng):

| | Train 07/2024–03/2025 | Validate 04–12/2025 |
|---|---|---|
| Chọn theo EV_lo > 0 | 58 lệnh, −0,02R/lệnh (cận dưới −0,23) | 227 lệnh, +0,18R/lệnh (cận dưới +0,08) |
| Mọi lệnh C1/C2, không chồng | 393 lệnh, +0,03R | 358 lệnh, +0,12R |
| Lệnh ngẫu nhiên ngày khác, cùng số lệnh | | trung bình +0,09R; ngẫu nhiên ≥ chiến lược 6,5% |

- **Lưu ý về chiều lệnh:** ở validate, cổng xác suất giữ **221/227 lệnh MUA**, gần như thành bot chỉ mua. Nguyên nhân là kỳ train vàng tăng, nên yếu tố "chiều" và "D1 cùng chiều" đẩy xác suất của lệnh mua lên. Điều này trái với nguyên tắc giữ cả hai chiều. Nếu sau này muốn bật lệnh thật, cần quyết định trước:
  - hiệu chỉnh riêng từng chiều, hoặc
  - bỏ yếu tố "chiều" khỏi bảng.

## 2. EA làm gì

1. Mỗi khi đóng một nến M15, EA nạp 6000 nến M15 cùng H1, H4, D1 (chỉ nến đã đóng) và tìm lại mọi tín hiệu trong lịch sử đã nạp:
   - **C1 đuổi xung lực:** 6 nến đi ≥ 1 ATR M30 và giá đóng tạo đỉnh/đáy 24 nến;
   - **C2 đuổi phá cực trị ngày:** từ 10:00 server, giá đóng vượt đỉnh/đáy của ngày tới lúc đó.
2. Mỗi tín hiệu có các thông số sau (giống G112):
   - vào lệnh ở giá mở nến sau (giá ask với lệnh mua);
   - stop ở đỉnh/đáy fractal gần nhất ± spread, cách tối thiểu 0,5 ATR M30 và tối đa 3 ATR;
   - bỏ tín hiệu khi stop dưới 8 spread;
   - chốt 2R, giữ tối đa 48 nến.
3. Tám yếu tố của mỗi tín hiệu: chiều, phiên, D1 cùng chiều, H4 cùng chiều, ADX H1, volume tương đối, phân kỳ giá/delta, vị trí trong biên ngày.
4. Từ các yếu tố, EA tính:
   - điểm cộng log-LR;
   - xác suất sau hiệu chỉnh p, kèm số lệnh n của khối isotonic;
   - cận dưới Wilson 90% p_lo;
   - EV_lo = p_lo × R thắng TB − (1 − p_lo) × R thua TB.
5. **Chọn** lệnh khi EV_lo > 0, mỗi lúc một lệnh (lệnh sớm nhất trước; nếu cùng nến thì lấy EV_lo cao hơn).
6. **Lệnh thật** chỉ được đặt khi `InpTradeEnabled = true` và thỏa đủ:
   - chưa có lệnh nào của magic 141414;
   - tín hiệu là của nến vừa đóng, vào trong 120 giây đầu của nến mới (không vào trễ sau khi khởi động lại);
   - không gần tin HIGH USD, nếu bật `InpNewsMinutes`.

   SL/TP đặt ở broker. Lệnh tự đóng sau 48 nến, tính từ `POSITION_TIME`.

## 3. Inputs

| Input | Mặc định | Ý nghĩa |
|---|---|---|
| InpTradeEnabled | false | Bật đặt lệnh thật. Tắt thì chỉ ghi lệnh bóng |
| InpRiskPercent / InpRiskBase | 0,5% / INITIAL | Rủi ro mỗi lệnh |
| InpUseKelly | false | Nhân rủi ro với cỡ 1/4 Kelly (0–1R). Thường nhỏ hơn lot tối thiểu |
| InpC1 / InpC2, InpBuy / InpSell | bật | Chọn loại setup và chiều lệnh |
| InpNewsMinutes | 0 (tắt) | Chặn lệnh thật trong ±N phút quanh tin HIGH USD. Nghiên cứu không dùng bộ lọc này |
| InpMaxLateSec | 120 | Chỉ vào lệnh thật trong N giây đầu của nến |
| InpHistoryBars | 6000 | Số nến M15 nạp. Cần ≥ 2000 để có volume tương đối của 20 ngày |
| InpShadowCsv | true | Ghi sổ lệnh bóng vào `MQL5\Files\ProbSetupEA_shadow.csv` |
| InpMagic | 141414 | Khác magic của 4 bot đang chạy |

## 4. Panel

Panel gồm các dòng và mục sau:
- Chế độ: BÓNG hoặc VÀO LỆNH THẬT.
- Cảnh báo "Bảng G114: CHƯA đạt tiêu chí".
- **Tổng kết bóng:** số lệnh được chọn và R/lệnh, so với mọi tín hiệu trong lịch sử đã nạp.
- **Tín hiệu gần nhất:** 8 tín hiệu, mỗi dòng có loại, chiều, p, n, p_lo, EV_lo, [chọn]/[bỏ], kết quả hoặc "đang chạy".
- **Lệnh thật:** lệnh đang mở, nếu có.

Bấm [+]/[−] để mở hoặc đóng từng mục, giống 4 bot hiện có.

## 5. Kiểm tra đã làm

1. **Oracle Python độc lập** (`Tests/prob_setup_oracle.py`): khớp tuyệt đối với bảng nghiên cứu `g112_chase_XAUUSD_m15.pkl` (05–07/2025) ở tất cả các mặt sau (`Tests/prob_setup_oracle_tests.py`):
   - tập tín hiệu;
   - giá vào, stop, rủi ro;
   - R và số nến của X1;
   - cả 8 yếu tố.
2. **G114** có 12 test (`Tests/g114_prob_tests.py`), gồm test nhìn trước dữ liệu: cắt bớt tương lai hoặc đảo kết quả tương lai thì quyết định của tháng không đổi. **Audit độc lập** (`research/long/g114_audit.py`) đếm thô LR, dùng công thức isotonic max–min chính xác và kiểm lại việc chọn từng tháng: 0 sai lệch ở 4 mã × 3 khung.
3. **Nguồn EA** (`Tests/prob_setup_ea_tests.py`) được kiểm các điểm sau:
   - lệnh chỉ nằm trong `TryTrade`, sau dòng `if(!InpTradeEnabled) return;`;
   - magic riêng;
   - chỉ dùng nến đã đóng (giá mở là thứ duy nhất lấy từ nến mới);
   - không giữ trạng thái lệnh trong bộ nhớ;
   - hằng số giống nghiên cứu;
   - bảng MQL = file JSON đóng băng;
   - công thức quyết định trong Python = các hàm G114.
4. **Biên dịch MetaEditor:** `ProbSetupEA.mq5` và `Tests/ProbSetupSelfTest.mq5` đều 0 lỗi, 0 cảnh báo.

## 6. Còn cần bạn làm (chạm vào MT5)

1. **So khớp MQL và Python trên dữ liệu terminal:**
   - chép `Tests/ProbSetupSelfTest.ex5` vào `MQL5\Scripts` của terminal;
   - kéo script lên chart XAUUSD (khung nào cũng được); script không đặt lệnh, chỉ ghi `MQL5\Files\ProbSetupSelfTest.csv`;
   - rồi chạy `python Tests/prob_setup_parity.py`. Kết quả mong đợi: "0 mismatches, MQL unit failures 0".
2. **Strategy Tester** (tùy chọn): chạy ProbSetupEA trên XAUUSD M15, chế độ bóng, để xem panel và CSV.
3. **Chỉ bật `InpTradeEnabled`** sau khi đã có bằng chứng bóng đủ dài và đã quyết định vấn đề chiều lệnh ở mục 1.
