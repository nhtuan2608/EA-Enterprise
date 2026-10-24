# G157 — FX và BTC: phá giả / đi tiếp và các tình huống có tên (24/10/2026)

Kế hoạch: [2026-10-24-g157-fx-btc-predictability.md](../plans/2026-10-24-g157-fx-btc-predictability.md) (commit `a94ebec`). Script
[`g157_markets.py`](../../research/long/g157_markets.py), kết quả `research/long/results/g157/`.

**Kiểm code:** chạy vàng M30 qua cùng đường code thì cả 11 tình huống khớp tuyệt đối với G156c.

Khung H1: EURUSD, GBPUSD, USDJPY từ 2010; BTCUSD từ 2018. Kết quả đo: từ giá đóng, ± 1 ATR H1 trong 4 giờ.

## 1. Phá giả hay đi tiếp

| Thị trường | Số cú phá | Đi tiếp (đã phân định) | Theo năm | Mỏ neo | Bối cảnh có giá trị |
|---|---|---|---|---|---|
| EURUSD | 16.126 | 50,0 % | 44–56 % | tỷ lệ nền | **không** (mọi mô hình thua tỷ lệ nền, AUC 0,50–0,51) |
| GBPUSD | 16.257 | 48,6 % | 44–53 % | tỷ lệ nền | **không** (AUC 0,51) |
| USDJPY | 15.293 | 51,0 % | 44–55 % | tỷ lệ nền | **không** (AUC 0,50–0,52) |
| BTCUSD | 9.320 | **54,3 %** | **52–59 % mọi năm** | tỷ lệ nền | **không** (AUC 0,51–0,54) |

Giống vàng: **bối cảnh giá không đoán được** cú phá đi tiếp hay quay đầu, ở cả 4 thị trường.

Riêng **BTC có thiên hướng đi tiếp nhẹ nhưng rất đều**: 54 %, mọi năm ≥ 52 %. Đây là tính chất chung của thị trường (động lượng của BTC,
khớp với G41: bám xu hướng hợp crypto), không phải bối cảnh.

## 2. Tình huống có tên (11 tình huống × 4 thị trường, CI 99,89 %)

43 / 44 ô là "chỉ cảnh báo / giải thích". Tỷ lệ đi theo nằm trong khoảng 47–54 %, chênh so với đối chứng ≤ 5 điểm.

**Ô duy nhất đạt: USDJPY T4 "quét rồi rút cùng chiều D1"**
- 47,4 % đi theo, so với 50,7 % của chỉ đi theo D1;
- chênh −3,3 điểm, CI [−6,5; −0,4];
- âm ở cả 3 kỳ.

Cùng dấu ở **4 / 5 thị trường**: vàng −2,7, GBPUSD −2,5, BTC −2,9, USDJPY −3,3; EURUSD +0,1. Đây là một quy luật **liên thị trường** khá
nhất quán: **sau khi giá quét đỉnh/đáy rồi rút lại theo đúng chiều xu hướng D1, xác suất đi tiếp theo xu hướng còn thấp hơn bình
thường**. Trực giác "bẫy rồi chạy đúng hướng" sai một chút, đều đặn.

Các điểm gần đạt nhưng chưa đạt:
- BTC T11 "key level đã test nhiều lần" +5,0 điểm, CI [−0,1; +10,2];
- GBPUSD T2 nến tin +3,5;
- BTC T1 trước tin −3,7.

## 3. Có trade được không

Ước tính lợi thế trước phí với hai mốc ± 1 ATR: (2P − 1) × 1R, tính trên các lần đã phân định.

| Ứng viên | P | Lợi thế trước phí | Spread / ATR H1 (trung vị; 2024+) | Sau phí |
|---|---|---|---|---|
| USDJPY: làm ngược "quét rồi rút cùng D1" | 52,6 % | khoảng +0,05R | 0,089; 0,066 | **âm** |
| BTC: đi theo mọi cú phá | 54,3 % (2023–26: 52–55 %) | +0,04 tới +0,09R | 0,063; 0,034 | **khoảng 0** (còn chưa tính 20 % lần lưỡng lự cũng mất phí) |

Cả hai **quá nhỏ để trade**. Theo kế hoạch, chỉ một kế hoạch setup riêng (G158) mới quyết được. Nhưng với lợi thế cỡ này, gần như chắc
chắn không qua được chi phí harsh. **Không đề xuất G158.**

## Kết luận

1. **FX và BTC giống vàng**: với thông tin trong giá, phá giả hay đi tiếp không đoán được tốt hơn tỷ lệ nền. Các tình huống có tên (tin,
   quét, volume, đa khung, key level) không báo trước hướng đủ để trade.
2. Hai kiến thức mới (thêm vào bộ kiến thức):
   - **B22**: cú phá trên BTC H1 đi tiếp khoảng 54 % (52–59 % mọi năm). Thiên hướng động lượng nhẹ, quá nhỏ để trade đứng riêng; hợp với
     việc bám xu hướng trên crypto.
   - **C18 mở rộng**: "quét rồi rút cùng chiều xu hướng" hơi **kém** hơn chỉ đi theo xu hướng, ở 4 / 5 thị trường. Đừng coi cú quét là
     tín hiệu xác nhận.
3. Về trade FX / BTC: kết quả này **không mở ra** setup mới.
   - FX: giữ kết luận cũ (chỉ S06B M30 EUR / GBP chạy ảo).
   - BTC: hướng có cơ sở vẫn là bám xu hướng (T2), không phải bắt cú phá trong ngày.
4. Hội đồng AI (bước 3a): kết luận "giá trị phải đến từ thông tin ngoài giá" giờ đúng cho cả **vàng, FX và BTC**.
