# G128: phân bổ rủi ro cho S07 + VHedge G119 — kế hoạch đăng ký trước (20/10/2026)

## Vì sao

Vàng có hai setup có lợi thế: **S07** (M30, sổ G89/G107) và **VHedge G119** (M5, giữ tới 5R). Mọi hướng tìm tín hiệu mới đã đóng (G121–G127). Phần còn chưa tối ưu là **chia rủi ro**:
- rủi ro theo biến động;
- trần rủi ro đang mở;
- tỷ trọng giữa hai bot;
- giảm rủi ro khi sụt vốn hoặc thua liên tiếp.

G128 không tạo lệnh mới. Nó chỉ đổi **khối lượng** của các lệnh đã có.

## Dữ liệu

- **Chân lệnh S07**: `g107_portfolio.s07_legs()`, gồm R khắt khe và trọng số 1,0 / 0,67 như EA. Thời gian là UTC.
- **Nhóm lệnh VHedge G119**: `g120_combo.vhedge()["G119"]`, R mỗi nhóm sau chi phí. Thời gian server, đổi sang UTC theo luật g67.
- **Giá dùng cho biến động**: M30 vàng, ngày UTC. ATR14 ngày của hôm trước ÷ giá mở hôm nay (ATR%).

**Kỳ:**

| Phần | Chọn | Test (mở một lần, cho cả bộ đã chọn) |
|---|---|---|
| S07 một mình | train 03/2018–2021; validate 2022–2025 | 2026 |
| S07 + VHedge | 05/2024–12/2025 (VHedge chỉ có từ 05/2024) | 2026 |

- Kết quả thô của từng bot trên 2026 đã được xem trước đây (G122, G127). Các **luật phân bổ** dưới đây thì chưa từng chạy trên 2026.

## Mô phỏng

- Vốn đầu 10.000, lãi kép. Xử lý sự kiện vào/ra theo thời gian.
- Tiền rủi ro của một lệnh = vốn đã chốt lúc vào × rủi ro gốc × trọng số × các hệ số của luật. Lời/lỗ lúc ra = tiền rủi ro × R.
- **Gốc (R0)**:
  - S07: 1,5% × trọng số EA (1,0 / 0,67);
  - VHedge: 1,5% mỗi nhóm (như G120).
- **Chỉ số chính**: **MAR** = %/năm (CAGR) ÷ DD lớn nhất.
- **Chỉ số phụ**: DD p90 bằng bootstrap khối 1 năm (như G89); %/năm.

## Luật (mỗi luật thêm riêng lên gốc)

| Mã | Luật | Biến thể |
|---|---|---|
| A | **Theo biến động**: hệ số = trung vị ATR% 250 ngày trước ÷ ATR% hôm nay, kẹp trong [0,5; 1,5] | — |
| B | **Trần rủi ro đang mở** (mọi bot cộng lại): lệnh mới bị thu nhỏ cho vừa trần; còn < 0,25% thì bỏ | trần 4,5% / 6% |
| C | **Theo sụt vốn**: khi vốn thấp hơn đỉnh ≥ X, mọi lệnh × 0,5 tới khi sụt vốn < X/2 | X = 8% / 12% |
| D | **Tỷ trọng VHedge** (S07 giữ 1,5% × trọng số) | VHedge 1,0% / 2,0% mỗi nhóm |
| E | **Chuỗi thua theo từng bot**: sau 3 lệnh thua liên tiếp của một bot, 3 lệnh kế của bot đó × 0,5 | — |

Phạm vi kiểm:
- **S07 một mình**: A, C, E.
- **S07 + VHedge**: A, B, C, D, E.

## Chọn

- **S07 một mình**: luật được giữ khi MAR **cao hơn gốc ở cả train và validate**, và DD p90 validate không cao hơn gốc.
- **S07 + VHedge**: luật được giữ khi MAR trên 05/2024–12/2025 cao hơn gốc chung, và DD p90 không cao hơn.
  - Với B, C, D có hai biến thể: lấy biến thể có MAR cao hơn trong các biến thể được giữ.
- **Bộ cuối**: áp **tất cả luật được giữ** cùng lúc. Báo cáo bộ cuối trên kỳ chọn. Nếu bộ cuối kém luật tốt nhất đứng riêng, ghi rõ.

## Test 2026 (mở một lần)

- So bộ cuối với gốc trên 2026, cho S07 + VHedge (và S07 một mình nếu có luật S07 được giữ).
- **Đạt** khi đủ cả hai:
  1. MAR 2026 ≥ gốc;
  2. DD lớn nhất 2026 ≤ gốc.
- Báo cáo thêm %/năm 2026.
- Không có luật nào được giữ thì không mở 2026.

## Nếu đạt

- Đề xuất đưa luật vào `Bots/PortfolioGuard` của EnterpriseEA, ở chế độ ghi nhận trước (ghi "khối lượng theo luật" bên cạnh khối lượng thật).
- Deploy cần người dùng đồng ý.

## Đầu ra

`research/long/g128_risk_alloc.py`, báo cáo `reports/2026-10-20-g128-risk-allocation.md`.
