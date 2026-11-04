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
