# G124 R2: rổ động lượng chậm FX, rủi ro chia theo biến động — kế hoạch đăng ký trước

Ngày 15/10/2026. Đây là bước tiếp theo sau R1. R1 cho thấy lợi thế FX nằm ở **chiều động lượng 120 ngày**, không nằm ở điểm vào bung ra.

## Lưu ý về dữ liệu đã thấy

FX02 (11/10/2026) đã thử động lượng chuỗi thời gian (TSM) trên EURUSD, GBPUSD, USDJPY và 3 cặp chéo tổng hợp, với kỳ test 2021–10/2025. Vì vậy với các cặp có EUR, GBP, JPY, đoạn **2023–10/2025 đã bị nhìn thấy một phần**. Đoạn chưa ai nhìn:
- 10/2025–10/2026 với mọi cặp;
- toàn bộ AUD, NZD, CAD.

Kết quả test sẽ ghi rõ hai phần này.

## Dữ liệu và rổ

- **D1 thật** của 6 cặp chính (`data/fx124`), 2010 → 10/2026.
- **U6:** 6 cặp chính.
- **U21:** U6 thêm 15 cặp chéo tổng hợp từ 7 đồng tiền (USD, EUR, GBP, AUD, NZD, CAD, JPY), chỉ dùng giá đóng cửa. FX02 đã kiểm: cặp chéo tổng hợp khớp cặp thật với tương quan ≥ 0,998.
- **Chi phí:** spread D1 + phí của từng chân, tính theo khối lượng thay đổi khi cân lại. Cột "+1 pip" thêm 1 pip cho mỗi chân.
- **Swap:** theo mức hiện tại cho mỗi đêm giữ lệnh, báo riêng, không dùng để chọn.

| Kỳ | Thời gian |
|---|---|
| Train | 2010–2018 |
| Validate | 2019–2022 |
| Test | 2023 → 10/2026, mở một lần nếu có biến thể đạt |

## Quy tắc

**Tín hiệu mỗi cặp** (dấu lợi nhuận L ngày):

| Mã | Cách tính |
|---|---|
| L60 | dấu lợi nhuận 60 ngày |
| L120 | dấu lợi nhuận 120 ngày |
| L250 | dấu lợi nhuận 250 ngày |
| VOTE | trung bình 3 dấu trên, ra −1, −⅓, +⅓ hoặc +1 |

**Khối lượng:** tín hiệu ÷ độ lệch chuẩn lợi nhuận ngày 60 ngày của cặp, để mỗi cặp góp rủi ro ngang nhau.

**Cân lại:** mỗi tuần, ở giá đóng cửa ngày giao dịch cuối tuần. Giữ nguyên tới lần cân sau.

**Đơn vị:** lợi nhuận rổ là trung bình các cặp. Rổ được nhân một hệ số cố định để biến động năm ở train bằng 10%. Hệ số này lấy từ train, giữ nguyên cho validate và test.

**Biến thể:** {U6, U21} × {L60, L120, L250, VOTE} = **8**.

## Đối chứng

- Với mỗi cặp, tạo chuỗi dấu ngẫu nhiên đổi chiều với cùng tần suất như tín hiệu thật (xích Markov).
- Giữ cùng cách chia khối lượng, cùng chi phí.
- Chạy 200 lần. p là tỉ lệ số lần Sharpe ngẫu nhiên ≥ Sharpe thật.

## Tiêu chí đạt

1. Sharpe (sau chi phí, chưa swap) > 0 ở cả train và validate. Cận dưới 90% của Sharpe train + validate gộp > 0 (bootstrap theo khối tháng).
2. Ở validate, thắng đối chứng ngẫu nhiên với p < 0,10.
3. Giai đoạn 2010–2022 không có quá 2 năm âm liên tiếp. Không cặp nào đóng góp hơn 50% tổng lợi nhuận.
4. Vẫn dương khi thêm 1 pip chi phí, ở cả train và validate.

**Lựa chọn:** biến thể đạt có min(Sharpe train, validate) cao nhất. Biến thể đó được mở test **một lần** ngay trong lượt này, theo sự đồng ý G124 của người dùng.

**Báo cáo:**
- %/năm và sụt vốn ở mức biến động mục tiêu 10%/năm;
- lợi nhuận theo năm và theo cặp;
- ảnh hưởng của swap;
- so với S06B M30 và S07.
