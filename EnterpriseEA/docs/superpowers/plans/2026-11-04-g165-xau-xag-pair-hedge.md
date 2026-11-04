# G165: bot hedge liên thị trường XAU / XAG (hồi quy chênh lệch) — kiểm tra khả thi trên 2,6 năm — kế hoạch đăng ký trước (04/11/2026)

## Bối cảnh

Người dùng muốn một **bot hedging mới, độc lập** với các bot đang chạy. G158–G163 cho thấy: hedge trên cùng một mã vàng thì thua khi vàng chạy một
chiều dài (2011–2015). Cặp vàng / bạc là hedge đúng nghĩa:
- hai chân ngược chiều trên hai kim loại thường đi cùng nhau;
- rổ lệnh gần như **không phụ thuộc vàng tăng hay giảm**.

**Giới hạn dữ liệu.** Broker MT5 demo chỉ có XAGUSD-VIP từ **20/02/2024** (đã kiểm qua MT5 Python ngày 04/11). Người dùng chọn làm **bản thăm dò** trên
2,6 năm trước.
- G165 **không thể "đạt"**. Nó chỉ trả lời câu hỏi: **có đáng lấy dữ liệu dài (lựa chọn 1) để kiểm thật không**.
- Kiểm thật (G165b, có stress 2010–2018) chỉ viết sau, khi có lịch sử XAG dài từ một broker MT5 khác.

## Dữ liệu

- XAUUSD-VIP và XAGUSD-VIP, H1, 20/02/2024 → 04/11/2026, đọc từ terminal MT5 demo qua MT5 Python (dữ liệu MT5). Lưu kèm kết quả.
- Ghép theo giờ H1 chung của hai mã.
- **Kỳ thăm dò:**
  - chọn: 20/02/2024 → 30/06/2025;
  - kiểm: 01/07/2025 → 04/11/2026.
- **Chi phí lấy từ thông số mã trong MT5** (`symbol_info`):
  - spread theo từng nến;
  - trượt giá 0,5 × spread trung vị mỗi chân, mỗi chiều;
  - phí 6 USD / lot mỗi chân;
  - **swap thật** của từng chân (swap_long / swap_short, ×3 vào ngày broker quy định).

## Cơ chế bot (cố định)

**Chênh lệch:** s = ln(XAU) − β × ln(XAG).
- **M1:** β = 1 (tỷ lệ vàng / bạc thuần).
- **M2:** β = hệ số hồi quy ln(XAU) theo ln(XAG) trên N nến H1 trước. Chỉ dùng dữ liệu đã có.

**z-score:** z = (s − TB_N(s)) / ĐLC_N(s), với N ∈ {240; 480} nến H1 (≈ 10 / 20 ngày giao dịch). Mọi thống kê tính đến nến đã đóng; lệnh vào ở giá
mở nến kế tiếp.

**Vào lệnh** (một rổ tại một thời điểm):
- z ≥ +k: **bán chênh lệch**: bán vàng, mua bạc;
- z ≤ −k: **mua chênh lệch**: mua vàng, bán bạc;
- k ∈ {2,0; 2,5}.

**Khối lượng:**
- hai chân cân theo giá trị: giá trị chân bạc = β × giá trị chân vàng (M1: bằng nhau);
- quy mô rổ sao cho đi thêm 2 × ĐLC_N(s) ngược chiều thì lỗ = 1 R = 1 % vốn.

**Thoát:**
- z về 0: chốt lời;
- hoặc chênh lệch đi ngược thêm 2 ĐLC kể từ lúc vào (z ≈ ± (k + 2)): **SL tổng 1 R**, kiểm theo giá đóng H1, khớp ở giá mở nến sau;
- hoặc hết giờ: 240 nến H1.

Không bồi, không đảo chân. Một bot đơn giản trước.

**Cấu hình:** 2 β × 2 N × 2 k = **8 cấu hình**.

## Đối chứng

- **Ngẫu nhiên:** cùng số rổ, cùng tỷ lệ mua / bán chênh lệch, cùng luật thoát, vào ở nến ngẫu nhiên. 200 lần.
- **Đảo chiều (đà):** cùng điểm vào nhưng đánh **theo** chiều z (z ≥ k thì mua chênh lệch). Đối chứng này trả lời: chênh lệch hồi quy hay chạy đà.

## Thước đo

- **Theo kỳ và cả kỳ:** số rổ, tỷ lệ thắng, R TB, PF, tổng R, DD R, MAR, thời gian giữ, lý do thoát.
- **Mua / bán chênh lệch** riêng.
- **Chi phí:** swap / lãi gộp.
- **Độ trung tính:** tương quan giữa R hằng ngày của bot và lợi suất ngày của vàng. |ρ| càng nhỏ thì bot càng là hedge thật.
- **Chênh lệch:** half-life hồi quy của s (AR(1) trên Δs) và độ lệch chuẩn theo kỳ, để biết chênh lệch có hồi quy thật không.

## Chọn và ngưỡng "đáng lấy dữ liệu dài"

**Chọn:** cấu hình có MAR kỳ chọn cao nhất trong các cấu hình có ≥ 15 rổ ở kỳ chọn. Chỉ xét cấu hình này.

**Đáng lấy dữ liệu dài khi cả 6:**
1. Kỳ kiểm: tổng R > 0, PF ≥ 1,2, ≥ 15 rổ.
2. Mua và bán chênh lệch đều có tổng R ≥ 0, cả kỳ.
3. Cả kỳ: tổng R > p90 của đối chứng ngẫu nhiên.
4. Cả kỳ: hơn bản đánh theo đà.
5. |ρ| với lợi suất ngày của vàng < 0,3.
6. Chi phí × 1,5 (cả swap): tổng R cả kỳ > 0.

**Kết quả:**
- **Thỏa cả 6:** báo người dùng lấy lịch sử XAU / XAG dài từ một broker MT5 khác, rồi viết G165b (đăng ký trước, có stress 2010–2018, ngưỡng thống kê
  thật).
- **Không thỏa:** ghi lại lý do. Dừng XAU / XAG ở dạng này; vẫn ghi giới hạn dữ liệu 2,6 năm.

## Tệp

- Script `research/long/g165_xau_xag_pair.py`; dữ liệu và kết quả ở `research/long/results/g165/`.
- Kiểm code trước:
  - dựng lại giá trị rổ từ hai chân theo giá thật;
  - một rổ mẫu tính tay khớp với engine.

Không chỉnh luật sau khi chạy. Sổ cái: 8 cấu hình, đánh dấu "thăm dò".

## Sửa đổi trước khi chạy (04/11/2026, chưa có kết quả nào)

Người dùng đưa thêm dữ liệu `D:\Work\Project Research\Ingest-data\ingest-20261104` và yêu cầu gộp vào luồng test. Kết quả kiểm khớp
(`research/long/ingest_merge.py`, `results/g165/ingest_validation.json`):

- **XAU ingest = MT5:** chênh giá đóng TB 0,014 %, tương quan lợi suất ngày 0,997.
- **XAG ingest không phải giá spot MT5:**
  - nến ghi 04:00 UTC; giá đóng khớp nhất với giá MT5 lúc **18:00 UTC** cùng ngày, lệch trung vị 0,25 %;
  - nhiều khả năng là giá settlement hợp đồng tương lai.
  - Dùng được cho tín hiệu: z-score theo trung bình trượt khử phần lệch basis biến đổi chậm. Nhưng đây là nguồn khác MT5, ghi rõ trong báo cáo.

Vì vậy G165 chuyển từ **H1 2,6 năm** sang **D1, 06/2016 → 11/2026 (~10 năm)**.

**Dữ liệu D1, mọi giá lấy tại 18:00 UTC mỗi ngày giao dịch:**
- **XAG:**
  - 06/2016 → 25/06/2026: ingest;
  - sau đó: MT5 H1 (đóng của nến 17:00 UTC).
- **XAU:**
  - từ 19/03/2018: MT5 H1 (đóng của nến 17:00 UTC). Giờ server = UTC + 3 trong mùa DST Mỹ, UTC + 2 ngoài mùa;
  - **trước 19/03/2018:** chỉ có D1 MT5. Dùng giá đóng D1 server, nên **hai chân lệch giờ khoảng 3–4 tiếng**. Đánh dấu và báo cáo riêng.
- **Vào / thoát:** ở giá của lần lấy mẫu kế tiếp (18:00 UTC ngày sau), cả hai chân cùng thời điểm.
- **Chi phí:**
  - spread trung vị MT5 của từng mã (XAU 0,28 USD, XAG 0,031 USD);
  - trượt giá 0,5 × spread mỗi chân, mỗi chiều;
  - phí 6 USD / lot mỗi chân;
  - **swap thật hiện tại** của broker (XAU mua −74,18 / bán +28,54 USD / lot / đêm; XAG mua −47 / bán +23,2 USD / lot / đêm), × 3 đêm thứ Tư.
  - Swap của 2016–2021 (lãi suất thấp) có thể khác. Đây là giả định thận trọng.

**Tham số chuyển sang D1:**
- N ∈ {10; 20} ngày;
- M2: β hồi quy trên 120 ngày trước;
- hết giờ: 10 ngày giao dịch.

**Kỳ:**
- chọn 07/2016 → 2021;
- kiểm 2022 → 11/2026.

Các luật khác giữ nguyên: k, SL tổng ± 2 ĐLC, chốt khi z về 0, đối chứng, 6 điều kiện.

**Thêm báo cáo (không phải tiêu chí):**
- kết quả 02/2024 → 11/2026 khi **cả hai chân đều là MT5 spot** (H1 lúc 18:00 UTC), để đo ảnh hưởng của nguồn XAG khác;
- kết quả riêng đoạn trước / sau 19/03/2018.
