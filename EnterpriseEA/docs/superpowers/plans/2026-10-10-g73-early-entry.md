# G73: Vào lệnh sớm cho S07 (nén → bung DMI + EMA, XAUUSD) — kế hoạch đăng ký trước (10/10/2026)

## Vì sao

S07 (G68/G72) chỉ vào lệnh sau khi **nến khung chính đóng cửa** vượt cả 4 EMA, rồi khớp ở giá mở nến kế tiếp. Lúc đó giá thường đã chạy một đoạn, SL đặt ở đáy vùng nén nên xa. Người dùng hỏi có cách phát hiện sớm hơn mà vẫn tốt không. Thử hai cách, mỗi cách riêng, so với bản gốc:

- **V1 — kích hoạt trong nến (đóng nến nhỏ):** trong lúc nến khung chính đang chạy, mỗi khi một nến nhỏ đóng cửa (M15 trong M30/H1; M5 trong M15/M30), tính lại các điều kiện của nến chính **như thể nó đóng tại giá đó**:
  - ADX, +DI, −DI, ATR theo Wilder;
  - EMA21/55/100/200 với giá đóng tạm.

  Nếu đủ điều kiện S07 thì vào lệnh ở giá mở nến nhỏ kế tiếp:
  - nén trong W nến chính đã đóng trước đó;
  - ADX tạm > ADX nến trước, ADX tạm − đáy ≤ 10;
  - DI tách đúng chiều và mở rộng;
  - giá tạm vượt cả 4 EMA tạm;
  - cùng phía EMA200 H4.

  Nến nhỏ cuối cùng của nến chính chính là bản gốc. V1 vì vậy gồm mọi tín hiệu gốc, cộng các tín hiệu đến sớm hơn, cộng các tín hiệu chỉ có giữa nến rồi mất khi nến đóng.
  - SL = đáy (đỉnh) từ đầu cửa sổ tới giá hiện tại của nến chính ∓ 0,1 ATR tạm, trong 1–4 ATR, có xét khoảng nghỉ > 6 giờ như G68.
- **V2 — lệnh chờ Stop khi vùng nén hình thành:** sau mỗi nến chính đóng mà không có lệnh mở, nếu đủ các điều kiện sau thì đặt một lệnh chờ:
  - **đang nén:** đáy ADX trong W nến gần nhất (tính cả nến vừa đóng) ≤ 20, khoảng cách DI tại đáy ≤ 6, ADX hiện tại − đáy ≤ 10;
  - giá H4 ở một phía EMA200 H4.

  Lệnh chờ đặt theo phía H4:
  - **Buy Stop** tại max(đỉnh cửa sổ, EMA cao nhất trong 4 EMA) + 0,1 ATR khi H4 trên EMA200.
  - **Sell Stop** tại min(đáy cửa sổ, EMA thấp nhất) − 0,1 ATR khi H4 dưới EMA200.
  - Khớp được nghĩa là giá đã vượt cả vùng nén lẫn dải EMA.
  - SL = đáy (đỉnh) cửa sổ ∓ 0,1 ATR. Không đặt lệnh nếu SL > 4 ATR; SL nhỏ hơn 1 ATR thì nới ra 1 ATR.
  - Lệnh chỉ sống một nến chính. Đóng nến mà chưa khớp thì xét lại và đặt lại với mức mới (hoặc hủy nếu hết nén).
  - Lệnh mua khớp khi giá ask chạm mức (high + spread ≥ mức), giá khớp = max(mức, giá mở nến nhỏ + spread). Lệnh bán khớp khi giá bid chạm mức.
  - Trên nến nhỏ khớp lệnh, chỉ xét SL (giả định xấu): nếu nến đó cũng chạm SL thì tính là thua.
  - Không cần DI tách / ADX quay lên — chính là điểm "sớm".

## Phần giữ nguyên (bản gốc G68 cho từng khung)

- Khung chính và cửa sổ nén: M15 16 nến, M30 8 nến, H1 4 nến (4 giờ). Giữ tối đa 480/240/120 nến, nghỉ 8/4/2 nến sau mỗi lệnh.
- Thoát E2X: đóng ngược EMA55 của khung chính, chuyển sang EMA100 khi lệnh đã chạy ≥ 3R. TP 8R.
- Chi phí: spread (tối thiểu bằng trung vị) + USD 6/lot. Bộ chi phí khắt khe G68: trượt 0,5 × spread trung vị mỗi chiều, spread ×3 lúc 23:30–01:00 giờ server, phí ×2.
- Cả mua và bán (quy tắc người dùng: không âm thầm bỏ một chiều).

## So sánh công bằng

Cả ba (gốc B0, V1, V2) chạy cùng một bộ mô phỏng trên **nến nhỏ**:
- SL/TP xét trên từng nến nhỏ;
- điều kiện thoát EMA xét khi nến chính đóng, thoát ở giá mở nến nhỏ kế tiếp.

Bản gốc B0 vào ở giá mở nến nhỏ đầu tiên của nến chính kế tiếp (= giá mở nến chính). Có báo cáo thêm B0 chạy trên nến chính (như G68/G69) để đối chiếu.

## Dữ liệu và kỳ

- Nến nhỏ chính: **M15** cho khung chính M30 và H1 (có từ 20/07/2021). M5 của broker chỉ có từ 14/05/2024, nên khung chính M15 (nến nhỏ M5) chỉ có từ 2024.
- Kỳ quyết định: train 20/07/2021–2023, validate 2024–06/2025, test 07/2025–06/2026. Kỳ 07/2026–nay chỉ báo cáo. Kỳ 2018–2021 không có nến nhỏ nên không dùng.
- Kiểm tra bằng M5 (đúng ý "nến 5 phút"): khung chính M30 với nến nhỏ M5, từ 05/2024. Chỉ báo cáo, xem có cùng chiều với kết quả M15 không.

## Tiêu chí (chốt trước)

Một cách (V1 hoặc V2) **thay** bản gốc trên một khung + chiều khi đạt cả 5 điều (chi phí khắt khe, gộp train + validate + test):

1. R/lệnh ≥ R/lệnh của B0 cùng khung + chiều;
2. Tổng R ≥ tổng R của B0 (vào sớm mà mất nhiều lệnh tốt thì không đáng);
3. R/lệnh > 0 ở cả train, validate và test;
4. DD p90 (rủi ro 1,5%/lệnh, cửa sổ 1 năm, 2000 lần lấy mẫu) ≤ DD p90 của B0 + 2 điểm %;
5. Thắng vào lệnh ngẫu nhiên p < 0,05/12 (2 cách × 3 khung × 2 chiều): cùng số lệnh mỗi kỳ, cùng chiều, cùng SL tính theo ATR, cùng cách thoát, 200 lần.

Quyết định cho EA dựa vào **M30 mua** (bản gốc LIVE). M30 bán, H1 và M15 chỉ báo cáo; bên bán dù đạt vẫn giữ SHADOW tới khi có ≥ 30 lệnh ảo (D6).

## Báo cáo thêm

- Độ sớm: với mỗi lệnh V1/V2 có lệnh B0 cùng chiều trong cùng đợt bung, báo cáo trung vị số phút vào sớm hơn, giá vào tốt hơn (tính theo R của B0) và SL (ATR).
- Tỉ lệ tín hiệu "giữa nến rồi mất" (V1) và lệnh chờ khớp rồi thua ngay (V2).
- Bốn ví dụ của người dùng (bán 23/9, 25–28/9; mua 05/8, 19/8/2026) có bắt được, bắt sớm hơn không.

Không cách nào đạt → báo cáo trung thực, giữ bản gốc.

## Đầu ra

`research/long/g73_early.py`, báo cáo `reports/2026-10-10-g73-early-entry.md`.
