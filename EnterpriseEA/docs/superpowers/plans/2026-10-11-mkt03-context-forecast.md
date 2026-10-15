# MKT03: dự báo theo ngữ cảnh → lệnh limit hoặc market cho chỉ số Mỹ và crypto — kế hoạch đăng ký trước (11/10/2026)

## Vì sao

MKT01 và MKT02 cho thấy setup cố định (của vàng hay theo phiên) không có lợi thế trên chỉ số và crypto. Người dùng muốn **một phương pháp mới**, không dùng lại setup cũ:
- ưu tiên **lệnh limit**;
- nếu không được thì **lệnh market theo tín hiệu và dự báo**, dựa trên ngữ cảnh đã có hoặc ngữ cảnh tự tính.

Cách làm:
1. Tính một bộ **ngữ cảnh** ở mỗi nến đóng.
2. Gắn nhãn kết quả thật của hai **kế hoạch lệnh** chuẩn (limit và market) cho cả hai chiều.
3. Học mối liên hệ giữa ngữ cảnh và kết quả bằng LightGBM, **huấn luyện cuốn chiếu**: mô hình chỉ thấy quá khứ.
4. Chỉ vào lệnh khi dự báo vượt ngưỡng.

## Dữ liệu (MT5, MKT01)

**Nến M30** (điểm ra quyết định ở mỗi nến đóng), có thêm H4/D1 dựng từ M30 theo giờ server.

| Nhóm | Symbol | Có từ |
|---|---|---|
| Chỉ số | NAS100, DJ30, SP500 | 02/2024 |
| Crypto lớn | BTCUSD | 02/2019 |
| Crypto lớn | ETHUSD | 02/2024 |

Altcoin bị loại: spread 65–215% biên độ nến.

**Chi phí khắt khe:**
- lệnh market: ask/bid + trượt 0,5 × spread trung vị mỗi chiều;
- lệnh limit: vào đúng mức giá khi giá **xuyên qua** mức (giá ask thấp nhất < mức, với lệnh mua), ra có trượt;
- phí hoa hồng 0.

## Ngữ cảnh (chỉ dùng dữ liệu đến lúc nến đóng)

| Nhóm | Thành phần |
|---|---|
| Động lượng | lợi nhuận 1, 4, 16, 48 nến ÷ ATR |
| Dải EMA M30 | (giá − EMA21), (EMA21 − EMA55), (EMA55 − EMA200), tất cả ÷ ATR |
| Khung lớn | phía và khoảng cách tới EMA200 của nến H4 và D1 đã đóng (ngữ cảnh S07) |
| ADX/DI | ADX14, DI+ − DI−, RSI14 |
| Biến động | ATR14 ÷ ATR100; biên độ 16 nến ÷ ATR (nén) |
| Vị trí | khoảng cách tới đỉnh/đáy ngày server trước; vị trí trong biên độ ngày đang chạy; khoảng cách tới VWAP ngày; vị trí so với số tròn |
| Thời gian | giờ New York, thứ trong tuần, phút từ lúc mở cửa NY |
| Volume | tick volume ÷ trung bình cùng khung giờ 20 ngày |
| Đầu tàu | lợi nhuận 1 và 4 nến của NAS100 (nhóm chỉ số) hoặc BTC (nhóm crypto) |
| Symbol | mã symbol |

## Kế hoạch lệnh (nhãn) — mỗi chiều mua/bán

| Mã | Kế hoạch |
|---|---|
| M (market) | vào ở giá mở nến kế; SL 1,0 ATR, TP 1,5 ATR; tối đa 16 nến rồi đóng |
| L (limit) | chờ mua ở giá đóng − 0,5 ATR (bán: + 0,5 ATR) trong 4 nến; SL 1,0 ATR, TP 1,5 ATR tính từ giá khớp; tối đa 16 nến |

- Với L: nếu chính nến khớp chạm SL thì tính thua; TP chạm trong nến khớp không được tính.
- R = lời/lỗ ÷ 1 ATR, sau chi phí. Lệnh không khớp thì không có nhãn.

## Mô hình

- LightGBM hồi quy kỳ vọng R, cố định không tinh chỉnh: 15 lá, mỗi lá ≥ 200 mẫu, học 0,03, 300 cây, lấy mẫu 0,8.
- Mô hình riêng cho mỗi (nhóm × kế hoạch × chiều): 8 mô hình.
- Huấn luyện cuốn chiếu:
  - Huấn luyện lại mỗi 3 tháng trên toàn bộ dữ liệu trước đó.
  - Bỏ 20 nến sát mốc để nhãn không chồng lên kỳ dự báo.
  - Dự báo ngoài mẫu bắt đầu từ: chỉ số 01/2025; crypto 01/2021 (trước 2024 chỉ có BTC).

## Kỳ

| Kỳ | Chỉ số | Crypto |
|---|---|---|
| Validate (chọn ngưỡng) | 01/2025 – 09/2025 | 01/2021 – 09/2025 |
| Test (không dùng để chọn) | 10/2025 – 10/2026 | 10/2025 – 10/2026 |

## Luật vào lệnh

- Ở mỗi nến, vào chiều có dự báo cao hơn nếu dự báo > θ và > 0.
- Một lệnh mỗi lúc trên mỗi symbol.
- θ chọn trên validate: phân vị 80% / 90% / 95% của các dự báo validate. Lấy phân vị cho R/lệnh validate cao nhất, với ≥ 60 lệnh. Giá trị θ đó giữ nguyên cho test.

## Đối chứng

- **Không điều kiện**: cùng kế hoạch, vào ở mọi nến (một lệnh mỗi lúc), chiều chọn ngẫu nhiên.
- **Hoán vị**: chọn ngẫu nhiên cùng số lệnh trong các điểm của kỳ test, 2.000 lần. p = tỷ lệ lần ngẫu nhiên có R ≥ mô hình.

## Tiêu chí (4 ô = 2 nhóm × 2 kế hoạch, trên test)

Ô đạt khi đủ cả năm:
1. ≥ 60 lệnh;
2. R/lệnh > 0;
3. cận dưới bootstrap 90% > 0;
4. sau trừ 0,10R vẫn > 0;
5. p hoán vị < 0,05.

Chỉ đề xuất SHADOW khi cận dưới Bonferroni (0,10/4, tức 97,5%) cũng > 0.

**Báo cáo thêm:**
- từng symbol;
- tỷ lệ khớp limit;
- 10 thành phần ngữ cảnh quan trọng nhất;
- BTC 2021–2025 (validate dài) như bằng chứng phụ.

## Đầu ra

`research/markets/mkt03_context.py`, báo cáo `reports/2026-10-11-mkt03-context-forecast.md`.
