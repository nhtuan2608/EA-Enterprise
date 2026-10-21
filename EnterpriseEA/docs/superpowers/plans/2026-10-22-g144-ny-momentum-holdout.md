# G144: động lượng giờ đầu phiên New York (G143 "NY") kiểm ngoài mẫu trên 03/2018–07/2021 — kế hoạch đăng ký trước (22/10/2026)

## Vì sao

G143 ô NY (di chuyển 15:30 → 16:30 server ≥ 0,4 × ATR20 D1, vào theo chiều đó lúc 16:30, đóng 20:30 server, SL = giá mở 15:30) không đạt
theo luật:
- train +0,195R (66 lệnh), validate −0,011R (28), test +0,279R (10);
- dưới 40 lệnh mỗi kỳ.

Nhưng nó thắng đối chứng "cùng ngày, cùng chiều, cùng giờ" với **p 0,010**, và ở train cả mua lẫn bán đều dương. G143 chỉ dùng nến M15,
tức từ 20/07/2021. Nến M30 có từ **19/03/2018**, nên khoảng 03/2018–07/2021 **chưa từng được nhìn** với giả thuyết này. Đó là kỳ
ngoài mẫu sạch, khoảng 3,3 năm.

## Luật (nguyên văn G143 NY, chỉ đổi độ phân giải nến)

- Nến M30 `data/m30v/XAUUSD.csv`. Cửa sổ 15:30 → 16:30 server = hai nến M30 lúc 15:30 và 16:00.
  - di chuyển = close nến 16:00 − open nến 15:30;
  - vào khi |di chuyển| ≥ 0,4 × ATR20 D1 (ngày server đã đóng).
- Vào ở giá mở nến 16:30, theo chiều di chuyển, cả mua và bán.
- SL = open nến 15:30. Ra ở giá đóng nến 20:00 (= 20:30 server). Không TP.
- SL được kiểm trên nến M30. Chi phí harsh G68, bản × 1,5.

## Đạt khi (1 ô, kỳ 19/03/2018 → 19/07/2021)

- ≥ 40 lệnh;
- R/lệnh > 0 ở **cả hai nửa**: 03/2018–12/2019 và 01/2020–07/2021;
- R/lệnh toàn kỳ > 0 với chi phí × 1,5;
- thắng đối chứng p ≤ 0,05. Đối chứng 200 lần như G143: ngày ngẫu nhiên cùng nửa, cùng chiều, cùng giờ vào/ra, SL cùng khoảng cách
  theo ATR20 D1.

Báo thêm (không quyết định):
- mua / bán;
- cùng luật trên M30 cho 07/2021–06/2026, để so với M15 (G143) và thấy ảnh hưởng của độ phân giải nến;
- theo năm 2018–2026.

## Nếu đạt

Hai lần thắng độc lập (G143 train trên M15, G144 ngoài mẫu trên M30) là đủ để đề xuất setup trong ngày **"NY momentum"**:
- bot riêng hoặc chế độ trong bots host;
- mặc định SHADOW, rủi ro thấp, forward ≥ 30 lệnh;
- người dùng đồng ý mới đưa vào EA.

Validate G143 ≈ 0 vẫn là điểm yếu cần ghi rõ.

Script `research/long/g144_ny_holdout.py`. Không chỉnh luật sau khi chạy.
