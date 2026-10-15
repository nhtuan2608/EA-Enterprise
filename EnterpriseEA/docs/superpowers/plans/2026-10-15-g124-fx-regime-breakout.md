# G124 R1: FX co hẹp → bung ra, chỉ đánh khi có xu hướng — kế hoạch đăng ký trước

Ngày 15/10/2026. Người dùng đồng ý nghiên cứu setup FX mới, bắt đầu với R1.

## Giả thuyết

Trên FX, co hẹp → bung ra (kiểu S06B/S07) chỉ có lãi khi cặp tiền đang có xu hướng ở khung D1. Ví dụ: 2010–2016 và 2021–2025 có lãi, 2017–2020 đi ngang thì không.

Nếu bật setup khi D1 có xu hướng và chỉ đánh theo chiều xu hướng, thì kết quả phải tốt hơn hai thứ:
1. cùng setup không lọc;
2. vào lệnh ngẫu nhiên trong cùng giai đoạn.

## Dữ liệu

**Rổ:** 6 cặp chính thật trong terminal MT5, gồm EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDJPY.
- Khung H4 và D1, từ 01/2010.
- Các cặp chéo chỉ có từ 2024 nên không dùng.

**Chi phí:**
- Spread của nến lúc vào và lúc ra.
- Phí 6 USD/lot khứ hồi (bảng `replay.COMMISSION`).
- Swap tính riêng theo mức hiện tại của broker (3 lần đêm thứ Tư). Swap không dùng để chọn, chỉ báo cáo.

| Kỳ | Thời gian |
|---|---|
| Train | 2010–2018 |
| Validate | 2019–2022 |
| Test | 2023 → 10/2026, **kín** |

## Giai đoạn (D1, chỉ dùng nến D1 đã đóng)

- **Chiều xu hướng:** dấu của lợi nhuận 120 ngày.
- **Độ thẳng ER60** = |C − C₆₀| / tổng |ΔC| trong 60 ngày.

| Cổng | Điều kiện | Vai trò |
|---|---|---|
| G0 | không lọc, đánh cả hai chiều | đối chứng |
| G1 | chỉ theo chiều xu hướng, không xét ER | đối chứng |
| **G2** | theo chiều xu hướng và ER60 ≥ trung vị train (gộp 6 cặp) | biến thể |
| **G3** | theo chiều xu hướng và ER60 ≥ phân vị 2/3 của train | biến thể |

## Vào lệnh (H4)

**Hộp:** đỉnh–đáy của K nến H4 gần nhất, K ∈ {12, 24}.

**Co hẹp:** độ rộng hộp ≤ 0,8 × trung vị độ rộng hộp K nến trong 120 nến trước đó.

**Bung ra:** nến H4 đóng cửa vượt đỉnh hộp thì MUA, dưới đáy hộp thì BÁN, khi hộp trước đó đang co hẹp. Vào ở giá mở nến kế tiếp.

**Stop:** cạnh đối diện của hộp. Rủi ro phải nằm trong khoảng 1–4 ATR14(H4), ngoài khoảng đó thì bỏ lệnh.

Mỗi cặp × biến thể chỉ có một lệnh mỗi lúc.

## Thoát

| Mã | Cách thoát |
|---|---|
| **E1** | TP 3R |
| **E2** | Không TP. Sau khi đạt +1R, dời stop về hòa vốn rồi trailing 3 ATR(H4) theo đỉnh/đáy giá đóng cửa |

Cả hai đóng lệnh sau tối đa 180 nến H4 (khoảng 30 ngày).

**Biến thể:** K {12, 24} × thoát {E1, E2} × cổng {G2, G3} = **8**. G0 và G1 dùng làm đối chứng cho từng K × thoát.

## Đối chứng ngẫu nhiên

- Vào ở nến H4 ngẫu nhiên.
- Cùng cặp, cùng năm, cùng cổng đang bật, cùng chiều.
- Cùng rủi ro tính theo ATR, cùng cách thoát.
- 200 lần.

## Tiêu chí đạt (rổ 6 cặp gộp, chưa tính swap)

1. R/lệnh > 0 ở cả train và validate. Cận dưới 90% (bootstrap) của train + validate gộp > 0.
2. Hơn G0 **và** G1 cùng K × thoát, ở cả train và validate.
3. Ở validate, thắng đối chứng ngẫu nhiên với p < 0,10.
4. Giai đoạn 2010–2022 không có quá 2 năm âm liên tiếp. Không cặp nào chiếm hơn 50% tổng R.

Biến thể đạt có min(train, validate) cao nhất sẽ được chọn. Người dùng đã đồng ý G124, nên kỳ test 2023–2026 được mở **một lần** ngay trong lượt này cho biến thể được chọn.

Báo cáo kèm swap, %/năm và sụt vốn ở 0,5% và 1%/lệnh, và so sánh với S06B M30.
