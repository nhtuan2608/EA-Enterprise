# G137: các họ mẫu hình chưa từng thử, kèm P5 của G136 — kế hoạch đăng ký trước (21/10/2026)

## Vì sao

Nội dung người dùng gửi (framework nhiều lớp: bối cảnh → cấu trúc → mẫu hình → xác nhận → rủi ro) có hầu hết các ý đã được
thử ở G23–G136: SMC/ICT, quét thanh khoản, RSI và phân kỳ, hồi về EMA, mô hình nến, wedge, VSA, volume profile, chấm điểm
đa yếu tố, Wyckoff spring (G136 P4), morning star (G136 P3). Kết quả: không đạt (xem bảng đầu kế hoạch G136 và
[báo cáo sơ bộ G136](../reports/2026-10-21-g136-prelim-h1-vps.md)).

Lịch sử nghiên cứu **chưa có** phép thử nào cho các mục sau. G137 thử từng mục với luật cố định ghi trước:

| Mã | Họ | Khung (ô quyết định) |
|---|---|---|
| G1 | Vai-đầu-vai / vai-đầu-vai ngược | H1, M30 (2) |
| G2 | Tam giác (cân, tăng, giảm), phá vỡ | H1, M30 (2) |
| G3 | Harmonic (Gartley, Bat) | H1 (1) |
| G4 | Bollinger / z-score khi sideway (đảo về trung bình) | H1, M30 (2) |
| G5 | Kênh song song, hồi về biên rồi bật lại | H1, M30 (2) |
| P5 | Phá kênh hồi làm điểm bồi S07A (luật giữ nguyên như G136) | M15 trong sổ M30 (3, thuộc ngân sách G136) |

Elliott Wave không thử: không có cách đếm sóng tự động duy nhất, mọi định nghĩa đều là chọn tham số sau khi nhìn.

**Kỳ vọng trước**: thấp. Các họ gần nhất (mô hình nến, wedge, mean reversion RSI) đều thua ở G56/G86/G130. G137 dùng để
khép lại câu hỏi "còn mẫu hình cổ điển nào chưa thử", không phải vì có dấu hiệu tốt.

## Quy ước chung

- **Dữ liệu**: XAUUSD, giờ server. Kế hoạch dùng dữ liệu nghiên cứu như G136. **Bản sơ bộ** chạy trên nến Lirunex của VPS
  (M30 từ 03/2019, H1 từ 09/2019, M15 từ 08/2022) và phải ghi rõ khác nguồn.
- **Kỳ**: như G136: sớm (đến 06/2021, chỉ báo cáo), train 07/2021–12/2023, validate 01/2024–06/2025, test 07/2025–06/2026
  (không còn kín), sau 07/2026 chỉ xem; forward từ 21/10/2026.
- **ATR** 14 (Wilder), EMA đóng cửa, ADX 14 như G67.
- **Vào lệnh**: giá mở nến sau nến tín hiệu (mua ở giá ask). Một lệnh mỗi họ mỗi khung tại một thời điểm (không chồng lệnh
  cùng họ).
- **Thoát chung** (trừ khi mục ghi khác): SL, TP, hoặc hết số nến giữ tối đa thì đóng ở giá đóng cửa. SL và TP chạm cùng nến
  → tính SL. Lệnh bán đóng ở giá ask.
- **Chi phí**: harsh như G68/G135 (spread vào/ra, trượt 0,5 × spread trung vị mỗi chiều, phí, spread × 2 giờ rollover) và bản
  chi phí × 1,5.
- **Đối chứng ngẫu nhiên**: 200 lần, cùng số lệnh, cùng chiều, cùng giờ server, cùng kỳ, **cùng khoảng SL tính theo ATR và
  cùng cách thoát**; p gộp train + validate.
- **Nhiều phép thử**: 9 ô mới (G1–G5). Ngưỡng một ô p ≤ 0,005 (0,05 / 9 ≈ 0,0056, làm tròn xuống). P5 giữ 3 ô và ngưỡng của G136.
- **Đạt (G1–G5, từng ô)**: R/lệnh > 0 ở train, validate và test; ≥ 30 lệnh mỗi kỳ (H1) hoặc ≥ 40 (M30); p ≤ 0,005; R/lệnh
  gộp train + validate vẫn > 0 khi chi phí × 1,5.
- **Cổng thứ hai** (chỉ khi một ô đạt): báo tỷ lệ lệnh trùng thời gian và cùng chiều với một chân S07 M30, rồi mô phỏng danh
  mục S07 M30 + họ mới như G136 P1 (MAR ≥ M30 một mình ở cả ba kỳ, DD p90 một năm không vượt quá 3 điểm %).
- **Không chỉnh luật sau khi chạy.** Lỗi dữ liệu hay nhìn trước thì sửa, chạy lại toàn bộ và ghi rõ.
- **Đường vào EA**: như G136 (mặc định tắt hoặc SHADOW, forward ≥ 30 lệnh hoặc ≥ 2 tháng, người dùng đồng ý).

## Điểm xoay (dùng cho G1, G2, G5)

Đỉnh xoay tại nến k: high[k] lớn nhất trong k−3 … k+3; đáy xoay tương tự với low. Điểm xoay chỉ **biết được** ở nến k+3
(không dùng trước thời điểm đó).

## G1. Vai-đầu-vai

**Vai-đầu-vai ngược (mua)**: ba đáy xoay liên tiếp L1, L2, L3 (không có đáy xoay nào khác ở giữa), với đỉnh xoay cao nhất
P1 giữa L1–L2 và P2 giữa L2–L3:
- đầu thấp hơn cả hai vai ít nhất 0,5 ATR: L2 ≤ min(L1, L3) − 0,5 × ATR;
- hai vai cân: |L1 − L3| ≤ 1,0 ATR;
- độ rộng: từ L1 đến L3 trong 10–80 nến;
- xu hướng trước đó ngược chiều: EMA55 tại L1 thấp hơn EMA55 48 nến trước đó;
- **đường cổ** là đường thẳng qua P1 và P2.

**Tín hiệu**: trong 20 nến kể từ khi L3 được xác nhận, nến đầu tiên đóng cửa trên đường cổ (chiếu đến nến đó) + 0,1 ATR.
Bỏ nếu giá đã đóng dưới L3 trước đó.
**SL**: L3 − 0,1 ATR (khoảng cách 1–4 ATR, ngoài khoảng thì bỏ). **TP** 2R. Giữ tối đa 120 nến.
**Vai-đầu-vai (bán)**: đối xứng.

## G2. Tam giác

Tại mỗi nến i, xét 40 nến trước (i−39 … i−1) với các điểm xoay **đã xác nhận trước i**:
- ít nhất 2 đỉnh xoay và 2 đáy xoay; đường trên = hồi quy tuyến tính qua các đỉnh xoay, đường dưới = qua các đáy xoay;
- hội tụ: dốc đường trên ≤ +0,01 ATR/nến, dốc đường dưới ≥ −0,01 ATR/nến, và độ rộng (trên − dưới) ở nến i ≤ 0,6 × độ rộng
  ở nến i−39;
- độ rộng ở nến i ≥ 1 ATR (không phải dải hẹp vô nghĩa).

**Tín hiệu**: nến i đóng cửa trên đường trên + 0,1 ATR → mua; dưới đường dưới − 0,1 ATR → bán (chỉ nến phá đầu tiên của
mỗi tam giác; nghỉ 10 nến sau một tín hiệu).
**SL**: giữa tam giác tại nến i (1–4 ATR). **TP** 2R. Giữ tối đa 120 nến.
Báo thêm (không quyết định): chia theo cùng / ngược EMA200 và tỷ lệ trùng tín hiệu S07.

## G3. Harmonic (Gartley, Bat), H1

**ZigZag**: đảo chiều khi giá đi ngược ≥ 2 ATR (ATR tại điểm xoay) từ cực trị gần nhất; điểm xoay chỉ biết khi đã đảo đủ 2 ATR.
Với 4 điểm xoay đã biết X, A, B, C (luân phiên), cho mẫu tăng (mua tại D; X là đáy):

| Mẫu | AB / XA | BC / AB | D (thoái lui của XA tính từ A) | CD / BC |
|---|---|---|---|---|
| Gartley | 0,568–0,668 | 0,382–0,886 | 0,786 | 1,27–1,618 |
| Bat | 0,382–0,50 | 0,382–0,886 | 0,886 | 1,618–2,618 |

**Lệnh chờ**: từ khi C được xác nhận, đặt mua giới hạn tại mức D; điều kiện CD/BC kiểm tra trên giá D. Hủy nếu sau 60 nến
chưa khớp hoặc giá vượt quá C theo chiều ngược trước khi tới D.
**SL**: X − 0,1 ATR (Gartley) hoặc A − 1,13 × XA (Bat), khoảng cách 0,5–4 ATR. **TP**: thoái lui 0,382 của AD. Giữ tối đa 120 nến.
Mẫu giảm đối xứng. Khung H1 (M30 quá nhiễu cho ZigZag 2 ATR).

## G4. Bollinger / z-score khi sideway

**Sideway** tại nến i: ADX < 20 và |EMA200[i] − EMA200[i−48]| < 0,5 ATR.
z = (close − SMA20) / độ lệch chuẩn 20.
**Tín hiệu mua**: nến i−1 có z ≤ −2, nến i đóng lại z > −2, cả hai nến đều sideway. Bán đối xứng.
**SL**: thấp nhất của nến i−1, i − 0,1 ATR (0,5–3 ATR). **TP**: SMA20 tại nến i (R thay đổi theo lệnh). **Thoát sớm**: z đóng
vượt 0. Giữ tối đa 24 nến.

## G5. Kênh song song, hồi về biên

Hồi quy tuyến tính giá đóng cửa 60 nến (i−60 … i−1): dốc ≥ 0,02 ATR/nến (kênh tăng), R² ≥ 0,6, σ = độ lệch chuẩn phần dư,
biên dưới = đường hồi quy − 2σ (chiếu tới nến i).
**Tín hiệu mua**: nến i có low ≤ biên dưới, đóng cửa > biên dưới **và** > EMA20. Kênh giảm đối xứng cho bán.
**SL**: low[i] − 0,1 ATR (0,5–3 ATR). **TP** 2R. Giữ tối đa 60 nến. Nghỉ 10 nến sau một tín hiệu.

## P5 (từ G136, luật không đổi)

Xem kế hoạch G136. Bản sơ bộ chỉ có M15 từ 08/2022, nên chỉ chạy trên các chân gốc mua S07 M30 từ 09/2022 và **không tính
train** (train còn 07/2021–08/2022 thiếu M15). Lệnh bồi phá kênh dùng SL / TP 8R / đóng cùng lệnh gốc, một đơn vị rủi ro
× trọng số bồi 0,67 như G89.

## Thứ tự và đầu ra

1. Commit kế hoạch này trước khi chạy.
2. Bản sơ bộ trên VPS: `research/long/g137_prelim.py`, báo cáo `docs/superpowers/reports/2026-10-21-g137-prelim-vps.md` với
   bảng theo kỳ, đối chứng ngẫu nhiên, chi phí × 1,5 và dòng **ĐẠT / KHÔNG ĐẠT (sơ bộ)** cho từng ô.
3. Bản chính thức chạy trên PC (dữ liệu nghiên cứu, M15 đủ từ 07/2021).
