# G67: Nén → bung theo DMI + dải EMA (XAUUSD M15) — kế hoạch đăng ký trước (09/10/2026)

## Vì sao

Người dùng đưa 4 ví dụ XAUUSD M15 (bán 23/9 và 25–28/9/2026, mua 05/8 và 19/8/2026). Phân tích chung (DMI 14/14, EMA 21/55/100/200, giờ, tick volume) cho cùng một chuỗi: **nén** (ADX về đáy, hai DI chụm, volume dưới mức thường của giờ đó) → **kích hoạt** (giá đóng hẳn về một phía của 4 EMA, DI theo chiều đó, ADX quay lên) → **xu hướng** (dải EMA mở rộng cùng ADX) → **cạn đà** (EMA21 dốc về 0, ADX quay đầu). Người dùng yêu cầu: một quy tắc chung chỉ gồm các điều kiện này; thử **lần lượt từng** bộ chặn rủi ro, không gộp tất cả; giữ lệnh theo dải EMA mở rộng càng lâu càng tốt, có TP xa.

4 ví dụ nằm trong 07–10/2026: giai đoạn này **không dùng để quyết định**, chỉ báo cáo riêng.

## Dữ liệu (chỉ MT5)

- XAUUSD M15 kèm tick volume: file MT5 gốc 20/07/2021 → 08/10/2025, nối với terminal (XAUUSD-VIP) tới nay.
- Kiểm tra ngoài symbol: XAGUSD, USDJPY, BTCUSD, EURUSD, GBPUSD M15 (cùng nguồn, độ dài tùy file).
- Chi phí: spread của từng nến (sàn ở trung vị 2024–2025) + commission USD 6/lot khứ hồi (vàng 0,06/oz), như G10/G23.

## Giai đoạn

| Kỳ | Thời gian | Dùng để |
|---|---|---|
| Train | 20/07/2021 – 31/12/2023 | chọn cách thoát và bộ chặn |
| Validate | 01/01/2024 – 30/06/2025 | kiểm tra lần 1 |
| Test | 01/07/2025 – 30/06/2026 | kiểm chứng cuối |
| Ví dụ | 01/07/2026 – nay | chỉ báo cáo (chứa 4 ví dụ) |

## Quy tắc gốc (viết trước khi chạy, không đổi sau khi xem kết quả)

Chỉ báo trên M15: EMA 21/55/100/200 (giá đóng), DMI 14/14 (Wilder), ATR 14.

Tín hiệu tại lúc nến M15 *i* đóng, chiều *d* (mua = +1):
1. **Nén:** trong 16 nến trước (4 giờ), ADX thấp nhất ≤ 20, và tại nến đó |+DI − −DI| ≤ 6.
2. **ADX quay lên:** ADX[i] > ADX[i−1] và ADX[i] − ADX đáy ≤ 10.
3. **DI theo chiều:** mua thì +DI > −DI và khoảng cách (+DI − −DI) lớn hơn nến trước; bán ngược lại.
4. **Giá ở hẳn một phía:** mua thì giá đóng trên cả 4 EMA; bán thì dưới cả 4.

Vào lệnh: giá mở nến kế tiếp (mua ở ask, bán ở bid). Mỗi symbol một lệnh; sau khi đóng lệnh chờ 8 nến.

SL: đáy thấp nhất của 16 nến trước − 0,1 ATR (bán: đỉnh cao nhất + 0,1 ATR). Khoảng dừng < 1 ATR thì nới thành 1 ATR; > 4 ATR thì bỏ tín hiệu.

Thoát (chọn trên train trong 9 tổ hợp):
- **Bám EMA:** {E1: nến đóng ngược qua EMA21 trong khi ADX đã thấp hơn đỉnh kể từ lúc vào ≥ 5 điểm; E2: nến đóng ngược qua EMA55; E3: trail 3 ATR từ đỉnh/đáy kể từ lúc vào}
- **TP xa:** {5R, 8R, không có TP}
- Giới hạn thời gian 480 nến (5 ngày giao dịch). Trong một nến, chạm SL tính trước TP.

## Bộ chặn rủi ro: thử từng cái một trên quy tắc gốc + cách thoát đã chọn

| # | Bộ chặn |
|---|---|
| B1 | Chỉ kích hoạt trong giờ mở phiên: 00–03, 07–09, 12–15 UTC |
| B2 | Chỉ kích hoạt khi nến M15 đóng đúng :00 hoặc :30 |
| B3 | Nén có volume thấp: volume trung bình 16 nến nén < volume trung bình cùng khung giờ 20 ngày trước |
| B4 | Cắt sớm nếu 4 nến đầu sau khi vào có volume < 0,9 × mức thường của giờ đó |
| B5 | Dời SL về hòa vốn khi lãi đạt 1R |
| B6 | Cùng chiều H4: giá đóng H4 trên EMA200 H4 khi mua, dưới khi bán |
| B7 | Bỏ tín hiệu khi spread > 2 × trung vị |

Một bộ chặn được **giữ** khi, so với quy tắc gốc: R/lệnh tăng ở **cả train và validate**, và giữ ≥ 50% số lệnh. Quy tắc cuối = quy tắc gốc + bộ chặn tốt nhất được giữ. Nếu hai bộ cùng được giữ thì thử thêm đúng một tổ hợp hai bộ. Không gộp nhiều hơn.

## Tiêu chí đạt (quy tắc cuối)

- R/lệnh dương ở train, validate **và** test.
- Thắng vào lệnh ngẫu nhiên (cùng số lệnh, cùng chiều, cùng khoảng dừng theo ATR, cùng cách thoát): p < 0,05/9.
- Phí ×2 + trượt 0,1R/lệnh vẫn > 0.
- Các symbol ngoài mẫu không âm trung bình; báo cáo từng symbol.
- Báo cáo thêm: tỷ lệ thắng, R trung bình của lệnh thắng, sụt giảm tối đa (R), thời gian giữ lệnh, theo năm.

Không đạt → báo cáo trung thực, không đưa vào EA.

## Đầu ra

`research/long/g67_dmi_ema.py`, báo cáo `reports/2026-10-09-g67-dmi-ema-compression.md`.
