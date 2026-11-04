# G166: bot hedge cặp FX (hồi quy chênh lệch EUR / GBP / JPY) — kế hoạch đăng ký trước (05/11/2026)

## Bối cảnh

Người dùng muốn một **bot hedging mới**. Các hướng đã đóng:
- **G158–G163**: hedge, bồi lệnh, lưới trên cùng mã vàng. Cháy khi vàng chạy một chiều dài (2011–2015). Có SL tổng thì an toàn nhưng không có lợi
  thế.
- **G165**: hedge chênh lệch XAU / XAG. Bot trung tính với vàng, nhưng chênh lệch hồi quy quá chậm (half-life 68–101 ngày); cả 8 cấu hình đều âm ở kỳ chọn.

G166 thử dạng hedge còn lại có **dữ liệu dài sẵn**: hai chân USD ngược nhau trên ba cặp FX chính. Mỗi rổ gồm hai lệnh, chiều USD triệt tiêu, nên
rổ chỉ còn lại tỷ giá chéo. Dữ liệu ingest có EURUSD, GBPUSD, USDJPY H1 từ 2010.

**Kỳ vọng trước: thấp.**
- G157: phá vỡ trên FX là tung đồng xu (49–51 %).
- G165: chênh lệch giữa hai tài sản liên quan trôi theo tháng.

G166 dùng để khép lại câu hỏi "hedge cặp FX có lợi thế không", không phải vì đã thấy dấu hiệu tốt.

## Dữ liệu

- **Nguồn:** kho ingest QTL trên VPS (`cache/ohlcv/<mã>/1h`, giờ UTC). Không có spread theo nến.
- **Nến H1:** EURUSD, GBPUSD, USDJPY, ghép theo giờ chung của cả ba mã.
- **Lỗ dữ liệu đã kiểm trước:**
  - GBPUSD và USDJPY thiếu từ khoảng 10/2025 đến 26/06/2026.
  - Cả ba mã có vài lỗ nghỉ lễ 73–79 giờ (cuối năm).
  - Không có nến sai high / low.
  - Có 42 nến H1 phẳng (high = low).
  - Các bước giá > 2 %/giờ đều là sự kiện thật: Brexit 24/06/2016, GBP 26/09/2022, JPY 2010–2011.
- **Đây là bản sơ bộ trên dữ liệu ingest**, không phải dữ liệu MT5 của broker. Kết quả chỉ để quyết định có đáng làm tiếp hay không.

**Kỳ:**

| Kỳ | Khoảng |
|---|---|
| chọn | 2010–2017 |
| kiểm 1 | 2018–2021 |
| kiểm 2 | 2022 → hết dữ liệu chung trước lỗ 10/2025 |
| chỉ xem | 26/06/2026 → 02/10/2026 |

## Chéo và chân lệnh

| Mã | Chéo tổng hợp | Hai chân khi **mua** chênh lệch | Hai chân khi **bán** chênh lệch |
|---|---|---|---|
| X1 | EURGBP = EURUSD / GBPUSD | mua EURUSD, bán GBPUSD | bán EURUSD, mua GBPUSD |
| X2 | EURJPY = EURUSD × USDJPY | mua EURUSD, mua USDJPY | bán EURUSD, bán USDJPY |
| X3 | GBPJPY = GBPUSD × USDJPY | mua GBPUSD, mua USDJPY | bán GBPUSD, bán USDJPY |

**Chênh lệch:** s = ln(A) ± β × ln(B), theo bảng trên.
- **M1:** β = 1, tức đúng tỷ giá chéo, hai chân cùng giá trị danh nghĩa tính bằng USD.
- **M2:** β = hệ số hồi quy OLS của ln(A) theo ln(B), tính trên N nến lấy mẫu trước đó, chỉ dùng dữ liệu đã có.

## Cơ chế bot (cố định)

**Lấy mẫu:** H4 (nến H1 đóng lúc 03, 07, 11, 15, 19, 23 giờ UTC) hoặc D1 (nến H1 đóng lúc 23 giờ UTC).

**z-score:** z = (s − TB_N(s)) / ĐLC_N(s), với N ∈ {20; 60} nến lấy mẫu. Tính đến nến đã đóng. Lệnh vào ở **giá mở nến H1 kế tiếp**.

**Vào lệnh:** mỗi chéo và mỗi cấu hình chỉ có một rổ tại một thời điểm.
- z ≥ +k: bán chênh lệch.
- z ≤ −k: mua chênh lệch.
- k ∈ {2,0; 2,5}.

**Thoát lệnh**, kiểm tại mỗi nến lấy mẫu đóng, đóng ở giá mở nến H1 kế tiếp:
- **về giữa:**
  - X0: z đổi dấu (qua 0);
  - X5: |z| ≤ 0,5.
- **SL rổ:** |z| ≥ k + 1,5 theo chiều bất lợi.
- **dừng theo thời gian:** sau 3 × N nến lấy mẫu.
- **lỗ dữ liệu:** nếu hai nến H1 liên tiếp cách nhau > 120 giờ khi đang có rổ, đóng ở nến đầu tiên sau lỗ. Có ghi lại số lần.

**Đơn vị kết quả.** Lợi nhuận rổ (theo lợi suất danh nghĩa, chân B nhân β) chia cho 1R = 1,5 × ĐLC_N(s) lúc vào lệnh. Đây là khoảng cách
từ điểm vào tới SL rổ, tính theo z.

## Chi phí (cố định, do không có spread theo nến)

| Chi phí | EURUSD | GBPUSD | USDJPY |
|---|---|---|---|
| Spread (pip, trả một lần mỗi lần vào và ra) | 1,0 | 1,5 | 1,2 |
| Trượt giá, mỗi chiều | 0,2 pip | 0,2 pip | 0,2 pip |

- **Phí:** 6 USD / lot khứ hồi mỗi chân, tức 0,006 % giá trị danh nghĩa.
- **Swap:** −0,5 pip mỗi đêm mỗi chân **cho cả hai chiều** (mức bất lợi, kiểu broker bán lẻ). Thứ Tư tính × 3.
- **Chi phí bi quan:** chi phí × 1,5 và swap × 2.

## Cấu hình và chọn

Lưới: 3 chéo × 2 khung lấy mẫu × 2 M × 2 N × 2 k × 2 cách thoát = **96 cấu hình**.

**Mỗi chéo chọn một cấu hình** trên kỳ chọn:
- trong các cấu hình có ≥ 30 rổ ở kỳ chọn;
- lấy MAR lớn nhất (tổng R / DD lớn nhất tính bằng R);
- nếu không có cấu hình nào có MAR > 0, chéo đó **trượt** luôn.

**Báo thêm (không phải tiêu chí):**
- half-life AR(1) của chênh lệch M1 ở kỳ chọn;
- bản **đánh theo đà** (ngược chiều vào lệnh, cùng cách thoát);
- tương quan lợi suất ngày của rổ với XAUUSD.

## Đối chứng ngẫu nhiên

200 lần cho mỗi kỳ kiểm. Mỗi lần giữ:
- cùng số rổ;
- cùng chiều (mua / bán chênh lệch);
- cùng cấu hình và cùng luật thoát;
- thời điểm vào ngẫu nhiên trong kỳ, trong giờ có dữ liệu.

p = tỷ lệ lần chạy có tổng R ≥ tổng R thật, gộp hai kỳ kiểm.

## Tiêu chí ĐẠT (từng chéo, cấu hình đã chọn)

1. Kiểm 1 và kiểm 2 đều R > 0, PF ≥ 1,2, mỗi kỳ ≥ 20 rổ.
2. p ≤ 0,0167 (0,05 / 3 chéo).
3. Mua và bán chênh lệch đều R ≥ 0, gộp hai kỳ kiểm.
4. Chi phí bi quan: tổng R hai kỳ kiểm vẫn > 0.
5. DD lớn nhất ở hai kỳ kiểm ≤ 1,5 × DD lớn nhất ở kỳ chọn.
6. Láng giềng: ít nhất 2 / 3 cấu hình láng giềng (đổi một trong k, N, cách thoát) có tổng R hai kỳ kiểm > 0.

**Không chỉnh luật sau khi chạy.** Lỗi dữ liệu hay nhìn trước thì sửa, chạy lại toàn bộ và ghi rõ trong báo cáo.

**Nếu có chéo ĐẠT:** chỉ ghi đề xuất. Bước tiếp theo là kiểm lại trên dữ liệu MT5 của broker, có spread và swap thật, rồi mới tới SHADOW. Không đưa
vào EA khi người dùng chưa đồng ý.

## Đầu ra

- Script: `research/long/g166_fx_pair_hedge.py`.
- Kết quả: `research/long/results/g166/summary.json`.
- Báo cáo: `docs/superpowers/reports/2026-11-05-g166-fx-pair-hedge.md`.
- Ghi vào sổ cái: 96 cấu hình, 3 chéo.
