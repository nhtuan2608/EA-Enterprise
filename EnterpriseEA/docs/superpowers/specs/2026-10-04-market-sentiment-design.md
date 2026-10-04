# Market Sentiment từ đường giá và cặp chéo

Ngày 04/10/2026. Trạng thái: **DESIGN — chưa sửa source**. Chờ người dùng chốt các quyết định ở mục 9.

Nguồn: yêu cầu người dùng 04/10/2026 ("với đường giá và cross pair đang có thì nên check market sentiment để hệ thống đánh giá cho thực thi"); master specification mục 4.3 (symbol profile: correlation, exposure), 5 (portfolio risk), 2.3 (đọc Price Action theo context).

---

## 1. Vấn đề

S02 hiện đánh giá từng symbol **riêng lẻ**: vùng giá, xu hướng khung lớn của chính symbol đó và trình tự setup. Hệ thống chưa biết:

- **Sức mạnh từng đồng tiền** lúc vào lệnh. Ví dụ mua EURUSD khi EUR đang yếu trên mọi cặp và USD đang mạnh trên mọi cặp là đi ngược dòng tiền.
- **Tâm lý rủi ro chung** (risk-on / risk-off): khi JPY, CHF và vàng cùng tăng, chỉ số chứng khoán giảm là thị trường đang né rủi ro.
- **Mức xác nhận từ cặp chéo.** Ví dụ setup mua XAUUSD có được USD yếu đi trên EURUSD, GBPUSD và USDJPY xác nhận không.

## 2. Nguyên tắc

- **Chỉ dùng giá**, đều có sẵn trong MT5: các symbol đang chọn cộng một bộ cặp tham chiếu chỉ để đọc. Không dùng nguồn ngoài; nhất quán với REQ-001.
- **Chỉ tính trên nến đã đóng**, nên kết quả không thay đổi khi gỡ EA ra rồi gắn lại.
- **Chỉ giảm, không bao giờ tăng:** sentiment có thể giảm rủi ro hoặc chặn một lệnh, không bao giờ tăng rủi ro vượt mức gốc. Cùng nguyên tắc với hệ số HTF và mức vàng của tin.
- **Thiếu dữ liệu thì trung tính** (`SENTIMENT_UNAVAILABLE`, hệ số 1,0), có ghi lý do. Thiếu sentiment không làm EA ngừng giao dịch, vì S02 và Risk Kernel vẫn đủ bảo vệ.
- **Tính xác định trong EA.** AI (khi có) chỉ diễn giải, không tính và không quyết định.

## 3. Dữ liệu

**Cặp tham chiếu** (chỉ đọc, broker có cặp nào dùng cặp đó; tên được tự resolve như symbol registry):
- FX chính: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD;
- cặp chéo: EURJPY, GBPJPY, EURGBP, AUDJPY;
- tài sản rủi ro: XAUUSD, BTCUSD, và một chỉ số chứng khoán Mỹ nếu broker có (US500 / NAS100 / US30).

**Khung tính:** H1 (4 giờ gần nhất) và D1 (24 giờ gần nhất). Mọi biến động được chuẩn hóa theo ATR14 của chính cặp đó, nên các cặp có độ biến động khác nhau vẫn so sánh được.

## 4. Chỉ số

| Chỉ số | Cách tính | Ý nghĩa |
|---|---|---|
| **Sức mạnh đồng tiền** S(c) cho USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD | Trung bình có dấu của biến động chuẩn hóa ATR trên mọi cặp chứa c (c là đồng tiền base thì +, là quote thì −), tính cho 4 giờ và 24 giờ | > 0: đồng tiền đang mạnh; < 0: đang yếu. Xếp hạng 8 đồng tiền |
| **Chỉ số USD tổng hợp** | S(USD) | Đối chiếu với vàng, BTC và các cặp USD |
| **Risk regime** | Điểm risk-off = trung bình của: S(JPY), S(CHF), biến động chuẩn hóa của vàng, và nghịch dấu biến động của chỉ số chứng khoán | `RISK_ON` / `NEUTRAL` / `RISK_OFF` |
| **Điểm xác nhận của lệnh** A(symbol, hướng) | FX: hướng × (S(base) − S(quote)). Vàng và BTC: hướng × (−S(USD)), cộng thành phần risk regime cho vàng | > 0: dòng tiền ủng hộ hướng lệnh; < 0: đi ngược |
| **Độ đồng thuận** | Tỷ lệ các cặp chứa base hoặc quote cùng xác nhận hướng | Lọc trường hợp một cặp đơn lẻ kéo cả trung bình |
| **Lệch tương quan** | Tương quan 20 nến H1 giữa vàng và S(USD) | Báo khi vàng "tách" khỏi USD (thường là do tin hoặc dòng tiền trú ẩn) |

## 5. Dùng khi thực thi (đề xuất)

Đặt trong vòng live **sau News Guard, trước Risk Kernel**, giống hệ số HTF:

| Điểm xác nhận A (cả 4 giờ và 24 giờ) | SCALP | SWING |
|---|---|---|
| Ủng hộ (A ≥ +0,3) | rủi ro × 1,0 | × 1,0 |
| Trung tính (−0,3 < A < +0,3) | × 1,0 | × 1,0 |
| Ngược (A ≤ −0,3) | × 0,5 | × 0,5 |
| Ngược mạnh (A ≤ −0,8 **và** đồng thuận ngược ≥ 70%) | × 0,5 | **chặn** (`SENTIMENT_STRONGLY_AGAINST`) |

- **Hệ số dồn:** rủi ro gốc × HTF × tin vàng × sentiment. Nếu tích các hệ số < 0,25 thì bỏ lệnh (`RISK_MODIFIERS_TOO_LOW`), để tránh vào lệnh quá nhỏ mà vẫn tốn chi phí.
- **Exposure:** sentiment không thay giới hạn tiền tệ và tương quan của O-04; hai cơ chế cùng áp dụng.
- **Audit:** mỗi candidate ghi `sentiment_score`, `consensus`, `risk_regime`, hệ số đã áp và lý do.

## 6. Hiển thị

- **Tab Market** thêm phần "Sentiment":
  - bảng xếp hạng 8 đồng tiền theo 4 giờ và 24 giờ, có thanh màu;
  - nhãn risk regime;
  - với mỗi symbol: điểm xác nhận cho chiều mua và chiều bán.
- **Tab Overview:** một dòng tóm tắt, ví dụ `USD strong · RISK_OFF · XAUUSD buy against (−0,6)`.
- **Dữ liệu cho AI:** bảng sức mạnh và risk regime được đưa vào ngữ cảnh của AI (PRE_SESSION_REVIEW).

## 7. Kiểm chứng

- **Đo trước khi áp:** mỗi candidate S02 và mỗi bản ghi phản ứng tin đều lưu điểm sentiment, nên có thể so: lệnh thuận sentiment có kết quả tốt hơn lệnh ngược không (đo bằng MFE/MAE và R).
- **Replay từ đầu năm:** tính lại sentiment tại thời điểm từng tin trong `news_reactions.jsonl`, để xem sentiment trước tin có liên quan tới hướng phản ứng không. Đây chỉ là nghiên cứu, không tạo tín hiệu.
- **Test:** oracle Python cho công thức sức mạnh, xử lý thiếu cặp, hệ số dồn và trường hợp ngược mạnh.

## 8. Ngoài phạm vi

- Không dùng sentiment để **tạo** tín hiệu hay đặt lệnh; nó chỉ lọc hoặc giảm rủi ro của tín hiệu S02 (và các setup sau này).
- Không dùng dữ liệu COT, positioning của broker hay tin tức tâm lý từ bên ngoài. Có thể xem xét sau qua AI Bridge.

## 9. Quyết định cần người dùng chốt

| ID | Câu hỏi | Đề xuất |
|---|---|---|
| M1 | Áp vào thực thi ngay hay chạy "đo trước" | **Áp ngay ở chế độ chỉ giảm** (bảng mục 5); đồng thời đo để đánh giá sau 2 tuần |
| M2 | Khung tính | 4 giờ (H1) và 24 giờ (D1); "ngược" phải đúng ở **cả hai** khung mới giảm rủi ro |
| M3 | Ngưỡng | Ngược ≤ −0,3; ngược mạnh ≤ −0,8 với đồng thuận ≥ 70% |
| M4 | Hành động khi ngược mạnh | SWING chặn, SCALP × 0,5 |
| M5 | Cặp tham chiếu | Danh sách ở mục 3; tự bỏ cặp broker không có |
| M6 | Hệ số dồn tối thiểu | 0,25; dưới mức này thì bỏ lệnh |
