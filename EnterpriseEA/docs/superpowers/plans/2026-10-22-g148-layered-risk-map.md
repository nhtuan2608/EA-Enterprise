# G148: bản đồ rủi ro nhiều tầng — từ nến → indicator → bối cảnh → volume/VWAP/biến động → price action/thanh khoản → thời gian/tin → phân phối/FOMO — kế hoạch đăng ký trước (22/10/2026)

## Vì sao

Người dùng (22/10): phối hợp từng chút một, chồng từ nến lên indicator, rồi bối cảnh / cấu trúc, volume, VWAP, biến động, price action,
"vol ít mà giá đi nhanh" ở khung nhỏ so với khung lớn, thói quen chốt lời, quét thanh khoản, điểm tiếp diễn, giờ trước tin, đầu / cuối
tháng, thứ Hai sau thứ Sáu tin mạnh, vùng phân phối / FOMO. Mục tiêu là lập bản đồ rủi ro và tìm setup / hệ thống mới.

G147 (21 yếu tố, một tầng) cho thấy hầu như mọi điều kiện đổi dấu theo năm. G148 mở rộng lên khoảng 50 yếu tố và **chồng từng tầng**:
một tầng chỉ được đánh giá trên phần vũ trụ đã lọc bởi các tầng trước. Nhờ vậy thấy được yếu tố nào chỉ có tác dụng **khi đã có** yếu tố
trước.

## Vũ trụ lệnh (không dựa vào setup nào)

- XAUUSD M30 `data/m30v`, từ 01/05/2018 (như G147).
- Mọi nến đóng trừ giờ server 23 và 0. Một lệnh mua và một lệnh bán giả định:
  - vào ở giá mở nến sau;
  - **SL 1,5 ATR14, TP 3 ATR14** (rộng hơn G147 để chi phí chiếm ít R hơn);
  - giữ tối đa 48 nến; chi phí harsh, bản × 1,5.
- Lịch tin: MT5 calendar xuất bởi EA (`MQL5/Files/EnterpriseEA/research/calendar/calendar_*.csv`, cột `time_server`), tin USD mức HIGH.

## Kỳ

| Kỳ | Khoảng | Dùng để |
|---|---|---|
| chọn | 01/05/2018 – 12/2021 | chọn yếu tố và ngưỡng |
| validate | 2022 – 2023 | kiểm |
| test | 01/2024 – 06/2026 | kiểm |
| sau | 07/2026+ | chỉ xem |

## Các tầng và yếu tố

Trạng thái viết **theo chiều lệnh**: "cùng" = ủng hộ, "ngược" = chống. Tính tại nến tín hiệu, chỉ dùng dữ liệu đã đóng.

**Tầng 1 — Nến**
- N1 thân / ATR: lớn cùng (≥ 0,6) / lớn ngược / doji (< 0,15) / vừa
- N2 râu từ chối: râu phía ngược ≥ 50% biên độ (giá bị đẩy về chiều lệnh) / râu phía cùng ≥ 50% / không
- N3 vị trí close trong nến: sát cực theo chiều (≥ 0,8) / sát cực ngược (≤ 0,2) / giữa
- N4 inside bar: có / không
- N5 nhấn chìm: cùng / ngược / không
- N6 chuỗi màu: ≥ 3 nến liên tiếp cùng chiều / ≥ 3 ngược / khác
- N7 biên độ nến / ATR: bùng (> 1,5) / lặng (< 0,5) / thường

**Tầng 2 — Indicator (phổ biến → sâu hơn)**
- I1 EMA20 vs EMA50: cùng / ngược
- I2 giá vs EMA20: cùng / ngược
- I3 giá vs EMA200 M30: cùng / ngược
- I4 EMA21/55/100 xếp thứ tự: cùng / ngược / lẫn
- I5 MACD histogram: cùng / ngược
- I6 MACD histogram mạnh lên / yếu đi
- I7 RSI14 theo chiều: > 70 / 55–70 / 45–55 / 30–45 / < 30
- I8 Stochastic %K(14,3) theo chiều: > 80 / < 20 / giữa
- I9 ADX: < 20 / 20–30 / > 30
- I10 ADX tăng / giảm (so 3 nến)
- I11 DI: cùng / ngược
- I12 Bollinger %b theo chiều: ngoài dải phía cùng (> 1) / ngoài dải phía ngược (< 0) / trong
- I13 kéo căng khỏi EMA20 theo chiều: > 2 ATR / < −2 ATR / trong

**Tầng 3 — Bối cảnh / cấu trúc**
- C1 phía EMA200 H4: cùng / ngược
- C2 D1 SMA50/200: cùng / ngược
- C3 biến động 20 ngày D1 theo chiều: > +1,5 ATR D1 / < −1,5 / giữa
- C4 cấu trúc M30 (hai đỉnh và hai đáy xoay cuối): HH/HL cùng chiều / ngược / lẫn
- C5 vừa phá cấu trúc (BOS: close vượt đỉnh / đáy xoay gần nhất trong 3 nến): cùng / không
- C6 vị trí so với biên độ hôm qua: đã vượt phía cùng / đã vượt phía ngược / trong
- C7 vị trí so với biên độ tuần trước: tương tự C6
- C8 dốc EMA200 M30 (48 nến): cùng / ngược / phẳng

**Tầng 4 — Volume / VWAP / biến động / tốc độ**
- V1 tick volume / trung bình 20: cao (≥ 1,5) / thấp (≤ 0,7) / thường
- V2 khoảng cách tới VWAP ngày (từ đầu ngày server, trọng số tick volume) theo chiều: > 1 ATR / < −1 ATR / trong
- V3 ATR14 / trung bình 100: cao (> 1,25) / thấp (< 0,8) / thường
- V4 độ rộng Bollinger so với 120 nến: hẹp / rộng / thường
- V5 "vol ít mà giá đi nhanh": biên độ nến ≥ 1,2 ATR **và** volume ≤ 0,8 × trung bình: có / không
- V6 tốc độ so với khung lớn: di chuyển 4 nến theo chiều / ATR20 D1: > 0,5 / < −0,5 / giữa
- V7 volume 6 nến gần nhất so với 20 nến trước: tăng (> 1,2) / giảm (< 0,8) / thường

**Tầng 5 — Price action / thanh khoản / thói quen**
- P1 quét đáy / đỉnh hôm qua rồi quay lại (mua: hôm nay đã thủng đáy hôm qua và close đang trên đáy đó): cùng / ngược / không
- P2 quét biên phiên Á (00–09) sau 09:00 rồi quay lại: cùng / ngược / không
- P3 giá tròn $10 phía trước trong 0,3 ATR: có / không
- P4 điểm tiếp diễn: đi 20 nến cùng chiều > 2 ATR và 4 nến gần nhất hồi ngược ≥ 0,5 ATR: có / không
- P5 chốt lời / chững: đi 20 nến cùng chiều > 3 ATR và 4 nến gần nhất biên độ tổng < 1 ATR: có / không
- P6 thanh khoản phía trước (hai đỉnh / đáy xoay cách nhau ≤ 0,2 ATR, nằm trong 1,5 ATR phía trước): có / không
- P7 retest mức vừa phá (mua: hôm nay đã vượt đỉnh hôm qua, giờ cách đỉnh đó ≤ 0,3 ATR phía trên): có / không

**Tầng 6 — Thời gian / tin**
- T1 giờ: Á sớm 01–05 / Á muộn 06–09 / London 10–14 / New York 15–19 / tối 20–22
- T2 thứ: Thứ Hai … Thứ Sáu
- T3 trong tháng: 2 ngày giao dịch đầu / 2 ngày cuối / giữa
- T4 tin USD HIGH: trong 2 giờ tới / trong 2 giờ qua / không
- T5 ngày có NFP: có / không
- T6 ngày có quyết định lãi suất Fed: có / không
- T7 thứ Hai sau thứ Sáu biến động mạnh (biên độ thứ Sáu ≥ 1,5 ATR20 D1): có / không

**Tầng 7 — Phân phối / FOMO (khung lớn)**
- M1 khoảng cách tới EMA200 D1 theo chiều (ATR D1): > 4 (FOMO) / 1–4 / 0–1 / ngược
- M2 RSI14 D1 theo chiều: > 70 / < 30 / giữa
- M3 chuỗi ngày: ≥ 4 ngày liên tiếp cùng chiều / ≥ 4 ngược / khác
- M4 gần đỉnh (mua) / đáy (bán) 52 tuần, trong 2 ATR D1: có / không
- M5 phân phối sau FOMO: 20 ngày trước đi cùng chiều > 5 ATR D1 **và** biên độ 5 ngày gần nhất < 0,7 × trung bình: có / không

## Cách chồng tầng (chỉ trên kỳ chọn)

Vũ trụ bắt đầu = mọi lệnh của kỳ chọn. Lần lượt tầng 1 → 7:
1. Với mỗi trạng thái của tầng: Δ = R của lệnh có trạng thái − R của lệnh không có, trong **vũ trụ hiện tại**, tính riêng 8 ô (năm 2018*,
   2019, 2020, 2021 × mua / bán).
2. **TRÁNH** nếu mọi ô có dữ liệu đều Δ < 0, có ≥ 7 ô có dữ liệu, |Δ| trung bình ≥ 0,03R, trạng thái chiếm ≥ 5% vũ trụ hiện tại.
   **ƯU TIÊN** đối xứng.
3. Hết tầng: bỏ khỏi vũ trụ mọi lệnh có trạng thái TRÁNH của tầng đó; trạng thái ƯU TIÊN cộng 1 điểm. Sang tầng sau.

(Với khoảng 160 trạng thái, xác suất một trạng thái vô nghĩa vượt luật 8/8 cùng dấu chỉ khoảng 0,8%, tức khoảng 1 trạng thái giả.
Bước xác nhận bên dưới lọc tiếp.)

## Hệ thống và đạt

- Hệ thống = lệnh không có trạng thái TRÁNH nào và điểm ƯU TIÊN ≥ T. T ∈ {0, 1, 2, 3, 4} chọn trên kỳ chọn: R/lệnh cao nhất, còn ≥ 300 lệnh.
  Mỗi chiều một lệnh mở tại một thời điểm.
- **Xác nhận từng trạng thái** (kết quả phụ): cùng dấu ở validate và test, cả mua và bán, trong vũ trụ cuối.
- **Đạt** (1 ô, tất cả cùng đúng):
  1. R/lệnh > 0 ở validate và test, mỗi kỳ ≥ 100 lệnh;
  2. mua > 0 và bán > 0 (gộp validate + test);
  3. tháng vàng không tăng > 0 (≥ 50 lệnh);
  4. đối chứng ngẫu nhiên p ≤ 0,005 (cùng kỳ, chiều, giờ);
  5. chi phí × 1,5 > 0;
  6. cửa sổ 6 tháng tệ nhất ≥ −15R;
  7. bỏ 5 lệnh lớn nhất vẫn > 0.

Báo thêm: R của hệ thống tích lũy sau từng tầng trên validate / test (chỉ để xem, không quyết định), so với vũ trụ không lọc.

Script `research/long/g148_layered_risk_map.py`. Không chỉnh luật sau khi chạy.
