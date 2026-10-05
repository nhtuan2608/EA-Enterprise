# G25: mô phỏng tài khoản FTMO 1-Step, lot cố định và rủi ro cố định (05/10/2026)

Script `research/long/fixed_lot.py`; lệnh từ nghiên cứu dài hạn G23 (cùng mô hình), ghép theo thời gian trên tài khoản 10.000 USD với giới hạn FTMO_1_STEP của EA: 0,3%/lệnh, tổng lệnh mở 1,2%, lỗ ngày nội bộ 1,2%, lỗ tuần 2,4%, quota 10 SCALP / 5 SWING mỗi ngày, mỗi symbol + chiều + khung một lệnh, không mở ngược chiều; sàn FTMO 3% ngày / 10% tổng. Lot cố định (quyết định người dùng 05/10): mỗi symbol một mức, lệnh nào lỗ tại SL vượt 0,3% hoặc vượt phần còn lại của trần 1,2% thì bỏ. Mức lot mặc định là mức lỗ khoảng 0,3% tại SL trung vị SWING của symbol: **EURUSD 0,08, GBPUSD 0,06, USDJPY 0,08, XAUUSD 0,03, BTCUSD 0,05**. Giới hạn ngày tính trên kết quả đã chốt (chưa tính lỗ đang mở).

| Phương án | Lot | Lệnh vào | Lợi nhuận | Sụt giảm tối đa | Vi phạm sàn FTMO |
|---|---|---|---|---|---|
| Toàn bộ cấu hình live (có SCALP), 06/2024–10/2025 | rủi ro 0,3% | 1.127 | **−53%** | 53% | **08/2024** (sau khoảng 2 tháng) |
| | lot cố định | 1.058 | −8,1% | 9,4% | không (bỏ 245 lệnh vượt trần) |
| SWING live (S02 + S04 + S06), 2010–2025 | rủi ro 0,3% | 2.893 | −58% | 61% | 12/2011 |
| | lot cố định | 1.637 | −8,4% | 17% | 05/2018 |
| Chỉ S04 SWING, 2010–2025 | rủi ro 0,3% | 157 | +5,4% (+0,34%/năm) | 2,8% | không |
| | lot cố định | 89 | +3,9% (+0,24%/năm) | 1,0% | không |
| S04 SWING + S06 hộp 24, 2010–2025 | rủi ro 0,3% | 321 | **+18,7% (+1,10%/năm)** | 3,2% | không |
| | lot cố định | 140 | +7,5% (+0,46%/năm) | 1,8% | không |

## Kết luận
1. **Cấu hình live hiện tại làm hỏng tài khoản FTMO** khi dùng rủi ro 0,3%/lệnh: chạm sàn sau khoảng 2 tháng ở giai đoạn 2024–2025. Thua chủ yếu ở S02 SCALP, S04 SCALP và S02 SWING.
2. **Lot cố định không sửa được setup thua**: nó chỉ giảm mức tiếp xúc (bỏ mọi lệnh có SL xa hơn trung vị). Cấu hình live vẫn âm và vẫn chạm sàn trên lịch sử dài.
3. **Với setup có lợi thế, lot cố định + bỏ lệnh vượt trần làm mất khoảng một nửa số lệnh** (những lệnh SL xa) và khoảng một nửa lợi nhuận (S04 + S06 hộp 24: +7,5% so với +18,7%). Kỷ luật "mỗi lệnh thua mất như nhau" vẫn được giữ bởi cách hiện tại: rủi ro cố định 0,3%.
4. Ngay cả tổ hợp tốt nhất cũng chỉ khoảng **+1%/năm ở 0,3%/lệnh**, rất xa mục tiêu lợi nhuận của một bài thi FTMO. Lợi thế có thật nhưng nhỏ và ít lệnh; cần tìm thêm lợi thế (G24: đổi giả thuyết, thêm thông tin liên thị trường) trước khi nói tới việc qua bài thi.
