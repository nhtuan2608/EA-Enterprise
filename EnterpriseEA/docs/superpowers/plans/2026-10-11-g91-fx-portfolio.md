# G91: Phối hợp các setup hiện có thành sổ FX — chọn trên 2010–2020, kiểm tra trên 2021–2025 (đăng ký trước, 11/10/2026)

## Vì sao

Người dùng hỏi có thể phối hợp các setup của mình (S02, S04, S06, S06B, S06B_USD, T2, S07) để có lợi nhuận từ FX không, và setup nào tốt hơn.

- G55 có bảng điểm từng setup × cặp. Một vài ô FX dương, nhưng xét cả 3 kỳ thì rất ít ô dương đều.
- G90: các setup swing kiểu mới và S07 H4 đều âm trên FX.

G91 làm một phép thử **ngoài mẫu thật**: chọn thành phần chỉ bằng dữ liệu cũ, rồi xem sổ gộp trên dữ liệu mới.

## Thành phần ứng viên

18 ô = 6 setup × 3 cặp có lịch sử dài:
- setup: S02, S04, S06, S06B, S06B_USD (H1, quản lý lệnh như EA), T2 (H4);
- cặp: EURUSD, GBPUSD, USDJPY.

Tính đúng như G55 (`research/long/scorecard.py`: cùng chi phí, cùng cách quản lý lệnh). Chi phí này là chi phí thường, chưa gồm trượt khắt khe và swap.

## Quy tắc chọn (chỉ dùng 2010–2020)

Một ô được chọn khi R/lệnh > 0 ở **cả** train 2010–2016 và validate 2017–2020, với ≥ 20 lệnh trong hai kỳ đó.

## Kiểm tra (2021–10/2025, không dùng để chọn)

Sổ gộp các ô được chọn, mỗi lệnh cùng rủi ro. **Đạt** khi đủ cả ba:
1. R/lệnh của sổ > 0 ở 2021–2025.
2. Cận dưới bootstrap 90% của R/lệnh 2021–2025 > 0.
3. Vẫn > 0 sau khi trừ thêm **0,10R mỗi lệnh**. Đây là bù ước lượng cho trượt khắt khe và swap, vì G90 đo chi phí khắt khe FX khung H1 khoảng 0,05–0,1R.

Báo cáo thêm:
- từng ô được chọn trên 2021–2025;
- %/năm và DD của sổ gộp ở 0,5% và 1%/lệnh (lãi kép theo ngày vào lệnh);
- S07 FX (G90, H4) để so.

Không đạt → FX không đưa vào EA. Đạt → đề xuất chạy SHADOW các ô được chọn trước khi LIVE.

## Đầu ra

`research/long/g91_fx_portfolio.py`, báo cáo `reports/2026-10-11-g91-fx-portfolio.md`.
