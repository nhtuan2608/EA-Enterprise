# G138 — BẢN SƠ BỘ: vì sao bộ lọc D1 golden / death cross vênh giữa dữ liệu PC và Lirunex (21/10/2026)

> **BẢN SƠ BỘ, CHỈ ĐỂ CHẨN ĐOÁN — không có ô quyết định, không dùng để đổi EA.** Nến Lirunex XAUUSD.r của VPS: M30 từ
> 03/2019 và M15 từ 08/2022 (`EEA_ExportDeals`), H1/H4 từ 09/2019 (export nghiên cứu của EA). Dữ liệu PC (XAUUSD-VIP) không
> có trên VPS; phần đối chiếu cần chạy trên PC (prompt ở cuối).

Script: [`research/long/g138_d1_sensitivity.py`](../../research/long/g138_d1_sensitivity.py).

## Câu hỏi

G134 (sổ S07 M30) và G135 (S07 M5…H1) trên dữ liệu PC thấy lệnh **ngược** trạng thái SMA50/SMA200 D1 kém hơn rõ, nên EA có
trọng số D1 × 0,5 và S07AS đứng độc lập chỉ bán khi D1 death cross. Các bản sơ bộ G136 trên Lirunex lại thấy điều ngược lại
ở 07/2021–2023: lệnh mua ngược D1 **tốt hơn** lệnh cùng D1.

## Cách thử

Trạng thái D1 = dấu SMA50 − SMA200 của giá đóng ngày, lấy ngày **đã đóng** trước lúc vào lệnh, tính từ nến M30. Thử năm
cách định nghĩa ngày:

| Cách | Số "ngày" mỗi tuần | Ghi chú |
|---|---|---|
| server 00:00 | 5 | như G134/G135; trùng nến D1 của broker Lirunex mà EA dùng (`EEA_S07D1CrossState`) |
| UTC 00:00 | 6 | có thêm một "ngày" Chủ nhật ngắn (22:00–24:00 UTC) |
| UTC 12:00 | 6 | thử độ nhạy |
| UTC 00:00, gộp Chủ nhật vào thứ Hai | 5 | chỉ đổi giờ ranh giới |
| server 00:00, SMA 42/167 | 5 | chỉ đổi độ dài: 42/167 ngày server ≈ khoảng lịch của 50/200 "ngày" khi tuần có 6 ngày |
| server 00:00, trễ thêm 1 ngày | 5 | thử độ trễ |

Bốn sổ: sổ S07 M30 bản Python G89 (1.119 chân) và S07 G67 thuần (B6, E2X, TP 8, chi phí harsh) trên M30 (835 lệnh), H1 (454),
H4 (148). p hoán vị một phía (cùng D1 > ngược D1), mua và bán gộp, 07/2021–06/2026, 2.000 lần.

## Kết quả

**Tỷ lệ lệnh đổi trạng thái D1** so với "server 00:00": thêm 1 ngày trễ 0,2–0,8%; gộp Chủ nhật 0–0,5%; UTC 00:00 / UTC 12:00 /
SMA 42/167: **5–11%**.

**Chênh R (cùng D1 − ngược D1), 07/2021–06/2026, và p hoán vị**:

| Sổ | server 00:00 (như EA) | UTC 00:00 | gộp Chủ nhật | SMA 42/167 | trễ 1 ngày |
|---|---|---|---|---|---|
| S07 M30 sổ G89 | +0,20 (p 0,12) | +0,43 (p **0,010**) | +0,18 (p 0,16) | +0,43 (p **0,010**) | +0,21 (p 0,12) |
| S07 G67 M30 | +0,38 (p 0,016) | +0,50 (p **0,005**) | +0,40 (p 0,014) | +0,51 (p **0,003**) | +0,39 (p 0,010) |
| S07 G67 H1 | +0,41 (p 0,052) | +0,62 (p **0,007**) | +0,39 (p 0,060) | +0,63 (p **0,006**) | +0,41 (p 0,063) |
| S07 G67 H4 | +0,22 (p 0,32) | +0,69 (p 0,069) | +0,22 (p 0,34) | +0,69 (p 0,077) | +0,22 (p 0,32) |

**Lệnh mua, train 07/2021–2023** (đây là chỗ vênh; validate và test không có lệnh mua ngược D1 vì D1 golden suốt
01/2024–06/2026). Ô: số chân / R cùng D1 so với số chân / R ngược D1:

| Sổ | server 00:00 (như EA) | SMA 42/167 (≈ UTC) |
|---|---|---|
| S07 M30 sổ G89 | 144 / +0,212 vs 131 / **+0,432** | 154 / **+0,395** vs 121 / +0,218 |
| S07 G67 M30 | 75 / +0,158 vs 60 / **+0,464** | 75 / **+0,352** vs 60 / +0,221 |
| S07 G67 H1 | 42 / +0,103 vs 36 / **+0,345** | 43 / **+0,367** vs 35 / +0,028 |
| S07 G67 H4 | 15 / −0,578 vs 10 / **+0,940** | 15 / **+0,281** vs 10 / −0,349 |

Các kỳ khác gần như giống nhau giữa các cách: 06/2019–06/2021 mua ngược D1 âm (sổ G89: 34 chân −0,206); validate và test
không có mua ngược; bán ngược D1 ở validate âm (−0,11 đến −0,32).

## Diễn giải

1. **Nguyên nhân là độ dài SMA tính theo lịch, không phải giờ ranh giới.** Gộp phiên Chủ nhật vào thứ Hai (cùng ranh giới UTC,
   5 ngày/tuần) cho kết quả gần như y hệt "server 00:00". Ngược lại, giữ ngày server nhưng rút SMA còn 42/167 thì cho kết quả
   như UTC. Khi tuần có 6 "ngày", SMA50/200 chỉ phủ khoảng 8,3 / 33 tuần thay vì 10 / 40 tuần, nên đường cắt sớm hơn.
2. **Dấu của bộ lọc ở 07/2021–2023 phụ thuộc vào độ dài này.** Đây là giai đoạn D1 đổi trạng thái 7 lần (08/2021 → 12/2023).
   Ở đó, rút ngắn SMA khoảng 16% đủ làm đổi nhãn khoảng 10% lệnh, và đổi luôn kết luận cùng / ngược. Ngoài giai đoạn này
   (2019–2021, 2024–2026) kết quả không phụ thuộc cách tính.
3. **Hệ quả cho EA đang chạy**: EA tính trạng thái D1 bằng nến D1 của broker. Trên Lirunex (giờ server GMT+2/+3, khớp giờ
   đóng cửa New York) mỗi tuần có 5 nến D1, tức là đúng biến thể "server 00:00": biến thể **yếu nhất** trong bảng trên
   (p 0,05–0,32 tùy sổ). Nếu dữ liệu PC mà G134/G135 dùng có nến Chủ nhật (6 ngày/tuần), thì kết quả G134/G135 thực chất
   ứng với SMA khoảng 42/167 chứ không phải luật mà EA đang chạy.
4. **Không chọn lại tham số từ bảng này.** Chọn SMA 42/167 vì nó đẹp hơn trên chính dữ liệu này là chọn sau khi nhìn. Kết
   luận an toàn là: **bộ lọc D1 SMA50/200 không vững với tham số ở 2021–2023**, nên trọng số D1 × 0,5 và điều kiện D1 của
   S07AS đứng độc lập nên được coi là độ tin cậy thấp cho đến khi đối chiếu xong trên PC.

## Cần PC trả lời

1. Dữ liệu `research/long/data/m30v/XAUUSD.csv` trên PC có nến vào thứ mấy theo giờ server; trung bình bao nhiêu ngày mỗi tuần
   (5 hay 6)?
2. Nến D1 của XAUUSD-VIP trong terminal PC có nến Chủ nhật không?
3. Chạy `g138_d1_sensitivity.py` trên dữ liệu PC: bảng cùng / ngược D1 có lặp lại hiện tượng "server 50/200 yếu, 42/167
   mạnh" không?
4. Với G134 phần 1 (trọng số D1 × 0,5 trên sổ G89): MAR theo kỳ khi trạng thái D1 tính đúng như EA (nến D1 của broker, 5
   ngày/tuần nếu là Lirunex) có còn ủng hộ × 0,5 không?

## Prompt cho agent trên PC

```text
Repo EA-Enterprise, pull branch docs/g138-d1-divergence (đọc docs/superpowers/reports/2026-10-21-g138-d1-divergence-prelim.md).
Việc chỉ đọc dữ liệu và chạy nghiên cứu, không sửa EA, không gửi gì vào terminal.

1. Với EnterpriseEA/research/long/data/m30v/XAUUSD.csv (và m15v, h1v): in phân bố nến theo thứ trong tuần theo cột time
   (giờ server), số ngày server trung bình mỗi tuần, có nến Chủ nhật hay không; in độ lệch giờ server so với UTC mà
   g67_dmi_ema.load giả định và kiểm lại bằng một mốc biết trước (ví dụ giờ ra tin NFP).
2. Dùng MetaTrader5 Python (chỉ đọc, copy_rates_from_pos) lấy 400 nến D1 XAUUSD-VIP: in thứ trong tuần của từng nến và cho
   biết có nến Chủ nhật không.
3. Chạy: python EnterpriseEA/research/long/g138_d1_sensitivity.py EnterpriseEA/research/long/data <out.json>
   (script tự đọc data/m30v, m15v, h1v, h4v; cần thư mục h4v có XAUUSD.csv, nếu không có thì dựng từ h1v theo nến 4 giờ
   căn 00/04/08/12/16/20 giờ server và ghi rõ).
4. Lặp lại G134 phần 1 (trọng số chân S07 ngược D1 × 1 / × 0,5 / × 0 trên sổ G89, MAR theo kỳ) với ba cách tính trạng thái
   D1: (a) như G134 (ngày server của m30v), (b) ngày server nhưng gộp nến Chủ nhật vào thứ Hai nếu có, (c) SMA 42/167.
5. Ghi báo cáo docs/superpowers/reports/2026-10-xx-g138-d1-divergence-pc.md: các bảng như báo cáo sơ bộ, cộng câu trả lời
   cho bốn câu hỏi ở mục "Cần PC trả lời". Không đổi luật, không chọn tham số mới. Commit lên branch docs/g138-d1-divergence
   và push.
```
