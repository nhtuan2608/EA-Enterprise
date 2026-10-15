# FX01: vào lệnh EUR/GBP theo USD, vùng cung/cầu, tin tức — lệnh limit, M15/M30/H1 — kế hoạch đăng ký trước (11/10/2026)

## Vì sao

G93 cho thấy hai điều:
- Với FX, setup vào lệnh thị trường ở khung nhỏ bị chi phí ăn hết.
- Dòng USD có ích, nhưng mới chỉ dùng làm bộ lọc.

Người dùng đồng ý thử hướng mới:
- **USD test lại đỉnh/đáy** để phát hiện sớm điểm vào;
- **USD phá cấu trúc / phá xu hướng**;
- **vùng cung/cầu**;
- **vào bằng lệnh limit**, kết hợp khung thời gian và **giờ tròn**;
- **tin tức**.

## Dữ liệu (MT5, không tải ngoài)

- Cặp vào lệnh: EURUSD + GBPUSD, gộp sổ.
- Chỉ số USD dựng trên chính khung vào lệnh: trung bình của −log EURUSD, −log GBPUSD và +log USDJPY (như `filters.usd_index`), chỉ dùng nến có đủ 3 cặp. ATR của chỉ số tính trên nến của nó.
- Lịch tin: lịch MT5 do EA xuất (`research/calendar`, 2010–2026, mức HIGH, có số thực tế và dự báo, giờ server khớp nến như G54).
- Khung và kỳ như G93:

| Khung | Train | Validate | Test (không dùng để chọn) |
|---|---|---|---|
| H1 | 2010–2016 | 2017–2020 | 2021–10/2025 |
| M30 | 10/2017–2019 | 2020–2021 | 2022–10/2025 |
| M15 | 10/2021–2022 | 2023 | 2024–10/2025 |

- Chi phí như G55.
  - Lệnh limit: khớp khi giá chạm mức (mua tính theo giá ask = bid + spread).
  - Nếu chính nến khớp chạm SL thì tính thua −1R.
  - Lệnh chờ hết hạn sau 3 nến.
- Tiêu chí cuối trừ thêm 0,10R/lệnh.
- Một lệnh mỗi lúc trên mỗi (biến thể × cặp).

## Setup (tín hiệu tại lúc nến đóng; d = chiều lệnh trên EUR/GBP)

**U1 — USD test lại đỉnh/đáy (cung/cầu của USD)**
- Đỉnh/đáy swing của chỉ số USD: fractal 3 nến mỗi bên, xác nhận xong mới dùng, trong 120 nến gần nhất.
- Tín hiệu khi nến USD chạm vùng ±0,25 ATR quanh một đỉnh cũ rồi đóng lại dưới đỉnh, và thân nến ngược lên ≥ 40%: USD bị từ chối ở kháng cự, nên **mua** EUR/GBP.
- Đối xứng ở đáy: USD bật lên khỏi hỗ trợ, nên **bán** EUR/GBP.

**U2 — USD phá cấu trúc**
- Chỉ số USD đóng vượt đỉnh swing gần nhất (hoặc thủng đáy swing gần nhất) thêm ≥ 0,1 ATR.
- Lần phá đó phải **ngược** với phía EMA50 của chỉ số ở nến trước, tức là đổi xu hướng.
- USD phá lên thì bán EUR/GBP; phá xuống thì mua.

**U3 — vùng cung/cầu của chính cặp**
- Nền: 2–4 nến có biên độ mỗi nến ≤ 0,8 ATR.
- Ngay sau nền là cú rời đi ≥ 2 ATR trong ≤ 3 nến.
- Vùng = cao/thấp của nền. Chỉ dùng lần quay lại đầu tiên, trong 100 nến.
- Mua ở vùng cầu (sau cú rời đi lên), bán ở vùng cung.

**N — lực đẩy sau tin**
- Tin HIGH của USD, EUR hoặc GBP có cả số thực tế và dự báo, thực tế ≠ dự báo.
- Hướng tin: thực tế > dự báo là tốt cho đồng tiền, trừ tên có "unemployment", "jobless", "claims" thì đảo chiều.
- Tin USD: trade cả EURUSD và GBPUSD theo chiều ngược hướng tin USD. Tin EUR: chỉ EURUSD. Tin GBP: chỉ GBPUSD.
- Nến chứa giờ ra tin phải đóng cùng chiều hướng tin, thân ≥ 50%, biên độ ≥ 1 ATR. Tín hiệu ở lúc nến đó đóng.

## Cách vào và thoát

**Vào lệnh:**

| Mã | Cách vào |
|---|---|
| E0 | lệnh thị trường ở giá đóng nến tín hiệu |
| E1 | limit ở 50% nến tín hiệu (với U3: mép gần của vùng) |

- SL: đầu xa của nến tín hiệu (với U3: mép xa của vùng) ± max(0,1 ATR; 1,5 spread).
- Với U3, limit E1 đặt sẵn ở mép gần ngay khi vùng hình thành, còn hiệu lực 100 nến; E0 là lệnh thị trường khi một nến đóng trong vùng.

**Thoát:**

| Mã | Cách thoát |
|---|---|
| T1 | cố định 2R + quản lý lệnh SWING trên nến khung vào |
| T2 | cố định 1,5R, chỉ SL/TP |

Mỗi setup × khung có 4 biến thể (E0/E1 × T1/T2). Riêng U3 có thêm U0/U1: dòng USD bắt buộc cùng chiều, nên U3 có 8 biến thể.

**Chọn:** như G93.
- Biến thể đạt khi R > 0 ở cả train và validate, và có ≥ 60 lệnh trong train+validate.
- Lấy biến thể có min(train, validate) cao nhất.

## Bộ lọc thời gian / chỉ báo (chấm như G79, luật như G93)

| Mã | Lọc |
|---|---|
| F1 | giờ London–New York 07:00–16:59 UTC |
| F2 | nến tín hiệu đóng đúng giờ tròn (hh:00); chỉ áp ở M15/M30 |
| F3 | cùng phía EMA200 H4 |
| F4 | dòng USD H1 cùng chiều; bỏ với N, U1, U2 vì vốn đã dựa trên USD |
| F5 | không có tin HIGH của hai đồng tiền trong 60 phút tới; bỏ với N |
| F6 | ADX14 khung vào > 20 |

## Kiểm tra cuối

Có 12 ô (4 setup × 3 khung). Ô đạt khi đủ cả ba trên kỳ test của khung đó:
1. R/lệnh > 0;
2. cận dưới bootstrap 90% > 0;
3. sau trừ 0,10R vẫn > 0.

Chỉ đề xuất SHADOW khi cận dưới Bonferroni (0,10/12, tức 99,2%) cũng > 0.

Báo cáo thêm:
- so sánh limit và thị trường trên cùng tín hiệu (E1 so với E0);
- tỷ lệ khớp limit;
- từng cặp;
- %/năm và DD ở 0,5%.

## Đầu ra

`research/fx/fx01_usd_led.py`, báo cáo `reports/2026-10-11-fx01-usd-led-limit.md`.
