# G24: vì sao các setup thua (05/10/2026)

Dữ liệu và mô hình như G23 (`research/long`, 2010–2025 H1; M5 06/2024–10/2025). Script: `research/long/diagnose.py`. Chỉ xét lệnh MARKET (S02 không gồm nhánh LIMIT). Kết quả theo R mỗi lệnh, không phải tài khoản.

## Số liệu
| | S02 SWING | S02 SCALP | S04 SWING | S06 SWING | Ngẫu nhiên SWING / SCALP |
|---|---|---|---|---|---|
| Trước phí / sau phí | −0,12 / −0,15 | −0,18 / −0,26 | +0,13 / +0,12 | +0,00 / −0,01 | — / −0,06, −0,19 |
| Chi phí mỗi lệnh | 0,03R | 0,07R | 0,02R | 0,01R | |
| Giá đi theo hướng lệnh (ATR) sau 1 / 3 / 6 / 24 nến | +0,01 / −0,03 / −0,06 / −0,20 | +0,04 / −0,01 / −0,13 / −0,06 | +0,11 / +0,14 / +0,06 / +0,21 | +0,02 / +0,02 / +0,04 / +0,13 | |
| Chạm +1R trước / −1R trước | 47% / 51% | 48% / 48% | 47% / 45% | 43% / 44% | |
| Lệnh chạm SL từng lời ≥ 0,5R | 75% | 70% | 61% | 51% | |
| SL trung vị | 1,3 ATR | 1,3 ATR | 2,4 ATR | 3,5 ATR | |
| SL rộng hơn (đệm 1 ATR, TP 3R) | −0,07 | −0,20 | 0,00 | −0,01 | |
| Nhóm tốt nhất | biến động trung bình +0,01 | biến động cao −0,09 | cùng HTF +0,15, phiên Á +0,22 | biến động trung bình +0,04 | |

Với S02 cả hai khung, nhánh LIMIT (vào ở mép vùng khi ARMED) còn kéo kết quả xuống thêm: S02 SWING như live (MARKET + LIMIT) là −0,32R so với −0,15R chỉ MARKET (G23).

## Chẩn đoán
1. **S02 không có tín hiệu hướng (khả năng 1).** Âm ngay cả trước phí; giá sau trigger không đi theo hướng lệnh, sau 6–24 nến còn nghiêng ngược lại; cuộc đua +1R/−1R gần như tung đồng xu. Chỉnh SL/TP chỉ kéo về gần 0 (tốt nhất −0,07), không thành dương; không có nhóm điều kiện nào dương rõ. Ý chính: **phá vùng hợp lưu trên H1 thường không đi tiếp**, và đó cũng là lý do S04 (bắt phá vỡ thất bại, đi ngược) lại dương. S02 đang đứng sai phía của hành vi giá quanh các vùng này.
2. **SCALP thua chủ yếu vì chi phí cộng không có tín hiệu (khả năng 1 + 2).** Vào lệnh ngẫu nhiên trên M5 đã −0,19R chỉ vì chi phí; S02 SCALP −0,26R còn tệ hơn ngẫu nhiên. Với SL khoảng 1,3 ATR M5, chi phí chiếm phần quá lớn của 1R.
3. **Quản lý lệnh không phải nguyên nhân gốc.** 70–75% lệnh thua của S02 từng lời ≥ 0,5R, nhưng MFE và MAE đối xứng: không có lợi thế vào lệnh thì Trade Manager không tạo ra được lợi thế.
4. **S04 có tín hiệu hướng thật** (+0,11..0,14 ATR sau 1–3 nến), dương trước phí, tốt hơn khi cùng HTF; mẫu nhỏ (157 lệnh/16 năm).
5. **S06 gần như không có lợi thế**: có xu hướng đi tiếp nhẹ về dài (+0,13 ATR sau 24 nến) nhưng SL 3,5 ATR (mép xa của hộp 12 nến) làm lợi thế tính theo R gần bằng 0.

## Hướng điều chỉnh phương pháp (thay vì tối ưu tham số)
- **Đổi giả thuyết của S02, không tinh chỉnh tham số** (lưới 430 biến thể không cái nào dương ổn định). Giả thuyết cần kiểm: "ở vùng hợp lưu H1, giá thường bật lại" → **đi ngược nhánh S02** (nghĩa là S04 mở rộng: vào lệnh khi phá vỡ không được chấp nhận), và kiểm tra trên khung H4/D1 nơi phá vùng có thể có lực hơn.
- **Bỏ nhánh LIMIT của S02** dù S02 còn chạy hay không.
- **Bỏ SCALP M5** với mức chi phí hiện tại; nếu muốn khung ngắn, dùng M15/M30 với SL lớn hơn để chi phí ≤ 0,03R.
- **Tăng mẫu cho S04**: thêm symbol (các cặp tham chiếu sentiment), thêm khung H4; giữ lọc cùng HTF.
- **S06**: thử SL giữa hộp hoặc hộp lớn hơn (biến thể hộp 24 vào ngay ở G23) để lợi thế đi tiếp không bị pha loãng bởi SL quá xa.
- Mọi biến thể kiểm bằng cùng quy trình 3 giai đoạn (2010–16 / 2017–20 / 2021–25) và đối chứng ngẫu nhiên; chỉ chọn trên giai đoạn đầu.
