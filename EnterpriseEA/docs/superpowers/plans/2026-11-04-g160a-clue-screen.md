# G160a: sàng manh mối — cổng đi ngang K1–K5 trước, rồi các manh mối chưa test — kế hoạch đăng ký trước (04/11/2026)

Theo [khung G160](2026-11-04-g160-clue-library-ambush.md), vòng 1. Ưu tiên theo khung:
1. **nhóm K** (nhận diện đi ngang, làm cổng bật / tắt lưới bồi lệnh), vì G158 cháy khi giá chạy một chiều;
2. các manh mối **chưa test**: H2–H5, I1–I3, J1, J4, J5, J7.

Nhóm 3 của khung (manh mối đã test ở vai trò khác, nay đo ở vai trò chỗ dừng / chỗ bồi) **để sang G160a2**, để giữ số phép thử của vòng này nhỏ.

**Dữ liệu:**
- XAUUSD H1 thật 05/2018–10/2026 (như G158); H4 dựng từ H1;
- D1 thô 2010–2025 chỉ cho K2 / K4 (tính được từ D1).

**Kỳ dùng để xét cùng dấu** (như G156c):
- 05/2018–2021;
- 2022–2023;
- 2024–10/2026.

## Phần A — cổng đi ngang K (5 phép thử)

### Định nghĩa

Tính ở giá đóng của nến khung tương ứng. Trạng thái dùng cho nến H1 lấy từ **nến H4 / D1 đã đóng gần nhất**, không nhìn trước.

| Mã | "Đi ngang" khi |
|---|---|
| K1 | ADX14 H4 < 20 **và** độ rộng Bollinger (20, 2) H4 / giá ở phân vị < 30 % của 500 nến H4 trước |
| K2 | Efficiency ratio Kaufman 20 ngày D1 = \|C − C₋₂₀\| / Σ\|ΔC\| < 0,3 |
| K3 | Giá đóng H4 cắt qua EMA50 H4 ≥ 4 lần trong 60 nến H4 gần nhất (≈ 10 ngày) |
| K4 | Biên 10 ngày D1 (đỉnh cao nhất − đáy thấp nhất) < 1,5 × ADR20 |
| K5 | Hurst exponent (R/S, 100 lợi suất H4 gần nhất, các đoạn 10 / 20 / 25 / 50) < 0,45 |

### (A-i) Thước thị trường: giá có chạy một chiều sau khi cổng bật không

- Ở **mỗi ngày** k (giá đóng D1), Y = 1 nếu \|C₍k+10₎ − C_k\| ≥ 2 × ADR20 (giá dịch chuyển ròng ≥ 2 ADR trong 10 ngày: chính loại
  đường giá làm lưới thả nổi sâu).
- So sánh P(Y | K bật) với P(Y | K tắt). Chênh lệch = bật − tắt.
- **CI:** bootstrap theo khối tuần, mức Bonferroni α = 0,05 / 5.
- **Null theo dịch chuỗi:** dịch vòng chuỗi K đi 500 độ trễ ngẫu nhiên (≥ 60 ngày), giữ nguyên tỷ lệ bật và độ dai của trạng thái. Chênh lệch
  thật phải âm hơn ≥ 95 % chênh lệch dịch.
- **Đạt (A-i)** khi:
  - CI nằm hẳn dưới 0;
  - vượt null dịch;
  - cùng dấu âm ở ≥ 2 / 3 kỳ;
  - tỷ lệ ngày bật nằm trong 15–85 %.
- K2 / K4 tính thêm trên D1 2010–2018. Chỉ báo cáo, không phải tiêu chí.

### (A-ii) Thước tài khoản: lưới nền chỉ mở rổ khi cổng bật

- **Cơ chế:** nền của G159a (E4 + lưới × 1,5, bước 0,5 ATR D1, 10 lệnh, X1, không module), mô hình tài khoản G158.
- Tín hiệu E4 chỉ được mở rổ khi K bật ở nến tín hiệu.
- **Đối chứng:** 50 chuỗi K dịch vòng (như A-i), cùng cơ chế.
- **Stress D1 2010–2018 chỉ cho K2 / K4:** 20 lần × 60 entry ngẫu nhiên, chỉ giữ entry rơi vào ngày K bật. Đối chứng là cùng số entry ngẫu nhiên không lọc.
- **Đạt (A-ii)** khi:
  - kỳ chọn (05/2018–2022) và kỳ kiểm (2023–10/2026) đều 0 cháy, lãi > 0;
  - xác suất cháy 12 tháng = 0;
  - DD < 50 %;
  - DD **và** ES 5 % rổ tốt hơn ≥ 95 % (≥ 48 / 50) chuỗi dịch;
  - với K2 / K4: stress 0 cháy.
- K1 / K3 / K5 không đo được trước 2018, nên nhiều nhất chỉ là **"ứng viên chờ stress"**, không bao giờ "đạt".

**Một cổng K qua vòng G160a khi đạt cả (A-i) và (A-ii).**

## Phần B — manh mối chưa test (15 phép thử)

### Định nghĩa (đối xứng mua / bán; mô tả chiều mua)

| Mã | Manh mối (chiều mua) | Khung | Loại | Đối chứng |
|---|---|---|---|---|
| H2 | Stochastic 14-3-3: %K cắt lên %D khi cả hai < 20 | H1 | đảo | Đ |
| H3 | CCI20 cắt lên lại −200 sau khi ở dưới | H1 | đảo | Đ |
| H4 | Williams %R14 cắt lên lại −80, chế độ D1 = tăng | H1 | theo D1 | R |
| H5 | Phân kỳ histogram MACD (12, 26, 9): đáy pivot 5 / 5 thấp hơn đáy pivot trước, histogram ở đáy sau cao hơn; vào khi pivot xác nhận (5 nến sau) | H1 | đảo | Đ |
| I1-2 / I1-3 | Elliott vào sóng 5, ZigZag k = 2 / 3 ATR H4. 5 điểm P0–P4: P2 > P0; sóng 3 (P2→P3) ≥ sóng 1 (P0→P1); P4 > P1. Vào khi đáy P4 được xác nhận | H4 | theo | T |
| I2-2 / I2-3 | Sau sóng 5 hoàn tất (P0–P5 như I1, P5 > P3), chỉnh A-B-C với \|C\| ∈ [1; 1,618] × \|A\| và B không vượt P5. Vào theo chiều sóng gốc khi đáy C được xác nhận | H4 | theo | T |
| I3-2 / I3-3 | Harmonic X-A-B-C-D (Gartley AB 0,618 / D 0,786 XA; Bat AB 0,382–0,5 / D 0,886; Butterfly AB 0,786 / D 1,27; Crab AB 0,382–0,618 / D 1,618; BC 0,382–0,886 AB; sai số ± 5 %). Khi X-A-B-C xác nhận, vào ở **nến H1 đầu tiên chạm mức D** (trong 120 nến H1) | H4 → H1 | đảo | Đ |
| J1 | Ichimoku (9, 26, 52): Tenkan cắt lên Kijun khi giá đóng trên mây | H4 | theo | T |
| J5 | Heikin Ashi đổi sang xanh sau ≥ 5 nến đỏ liên tiếp | H4 | đảo | Đ |
| J7 | Parabolic SAR (0,02; 0,2) lật lên, chế độ D1 = tăng | H4 | theo D1 | R |
| J4 | Pivot ngày cổ điển (P, S1–S3, R1–R3 từ D1 hôm trước): **chỗ dừng** | H1 | mức | M |

**ZigZag:** một đỉnh / đáy chỉ được xác nhận khi giá đã đi ngược k × ATR14 H4 từ nó. Tín hiệu đặt ở **nến xác nhận**, không ở nến
đỉnh / đáy (tránh nhìn trước). Tín hiệu H4 gắn vào nến H1 đóng cùng nến H4 đó.

### Thước đo

**(B-i) Hướng**, cho 14 manh mối dạng sự kiện:
- Nhãn first-passage đối xứng ± 1 ATR14 H1 từ giá đóng nến tín hiệu, trong 4 nến H1 (như G156c, đổi sang H1).
- Bỏ các sự kiện không chạm mức nào, hoặc chạm cả hai trong một nến.
- Gộp sự kiện cách nhau < 4 nến (dedupe).
- **Đối chứng:**
  - **Đ** (đảo): mọi nến H1, chiều = −dấu(C − C₋₈);
  - **T** (theo): mọi nến H1, chiều = dấu(C − C₋₈);
  - **R** (theo D1): mọi nến có chế độ D1 ≠ 0, chiều = chế độ D1.

**(B-ii) Chỗ dừng**, cho J4:
- Mỗi lần nến H1 chạm một mức pivot (đi lên chạm R / P từ dưới, đi xuống chạm S / P từ trên), Y = 1 nếu giá đảo lại ≥ 0,5 ATR H1 tính từ mức
  trước khi đi tiếp thêm 0,5 ATR qua mức, trong 2 nến.
- **Đối chứng:** mức giả ở giữa hai mức pivot liền kề (P ± 0,5 × (R1 − P), ...), cùng cách đo.

**Đạt (mỗi phép thử)** khi:
- n ≥ 100 sự kiện có nhãn (05/2018–10/2026);
- chênh lệch (manh mối − đối chứng) có CI bootstrap khối tuần ở mức α = 0,05 / 15 nằm hẳn trên 0;
- cùng dấu dương ở ≥ 2 / 3 kỳ (kỳ có n ≥ 30);
- **null dịch nhãn toàn họ:** dịch nhãn kết quả đi 200 độ trễ ngẫu nhiên. Số manh mối đạt thật phải vượt phân vị 95 % của số manh mối "đạt" dưới null.

## Kết quả đi đâu

- Cổng K qua vòng thì vào **G160c / G159** (chỉ mở rổ khi đi ngang; K chuyển sang xu hướng ngược rổ thì ngừng bồi và hedge).
- Manh mối B qua vòng thì vào **G160b** (phục kích) và **G160d** (ghép đôi). Không qua thì đóng ở vai trò entry.
- Mọi phép thử (5 + 15 = 20) ghi vào sổ cái phòng nghiên cứu.

Script `research/long/g160a_clue_screen.py`, kết quả `research/long/results/g160a/`. Không chỉnh định nghĩa, tham số hay tiêu chí sau khi chạy.
