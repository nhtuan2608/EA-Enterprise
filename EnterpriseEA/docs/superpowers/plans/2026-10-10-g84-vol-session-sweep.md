# G84: Biến động nở ra + giờ phiên + nến tròn giờ, và chờ quét khi giao phiên — kế hoạch đăng ký trước (10/10/2026)

## Vì sao

G83: chỉ ba đặc trưng cùng dấu ở cả 3 kỳ cho lệnh mua:
- ATR đang nở (ATR ÷ ATR 48–96 nến trước);
- vùng nén rộng (÷ ATR);
- volume nến bung.

Ngoài ra, tín hiệu mua lúc 11–16h UTC (London–New York) tốt hơn.

Người dùng thêm hai ý:
- **Vùng tròn giờ / đóng nến M30** có nhiều cơ hội.
- **Lúc giao phiên** giá có thể **quét ngược trước** rồi mới chạy đúng chiều.

**Trung thực về dữ liệu:** các đặc trưng và giờ đến từ G83 trên cùng dữ liệu. G84 kiểm việc kết hợp và độ vững, không phải ngoài mẫu.

## Phần A — nhãn trên tín hiệu S07

Tín hiệu S07 chuẩn ở M15, M30, H1. Mua có lọc H4 trên EMA200; bán không lọc khung lớn. Thoát E2X, TP 8R, chi phí khắt khe G68.

| Mã | Nhãn |
|---|---|
| VX | **biến động nở:** ít nhất 2/3 điều sau — ATR ratio > trung vị train, bề rộng vùng nén > trung vị train, volume nến bung > trung vị train (trung vị tính riêng từng khung) |
| SES | giờ đóng nến tín hiệu 11:00–16:59 UTC |
| R00 | nến tín hiệu đóng **tròn giờ** (:00). Với M30 là so :00 với :30; với M15 là so :00 với :15/:30/:45. H1 luôn :00 nên không xét |
| VX·SES | cả hai |
| VX·SES·R00 | cả ba (M15, M30) |

**Cách chấm:** như G79, trên tập con lệnh gốc. So nhóm có nhãn với nhóm không nhãn theo từng kỳ (2018–2021 nếu có, train, validate, test), kèm hoán vị 5000 lần.

**Một nhãn đạt** khi đủ cả ba:
- nhóm có nhãn tốt hơn nhóm không nhãn ở **mọi kỳ có dữ liệu**;
- R/lệnh nhóm có nhãn ≥ +0,5 ở validate và test;
- p < 0,05/30 (5 nhãn × 3 khung × 2 chiều).

## Phần B — chờ quét khi giao phiên (M30, nến nhỏ M15 như G73)

**Tín hiệu giao phiên:** nến tín hiệu đóng trong 06:00–08:59 hoặc 12:00–14:59 UTC (London mở, New York mở).

So hai cách vào:

| Mã | Cách vào |
|---|---|
| MK | vào ngay ở giá mở nến kế tiếp (như hiện tại) |
| LQ | đặt lệnh chờ ngược chiều 0,5 ATR so với giá đóng tín hiệu (mua: thấp hơn), hiệu lực 4 nến M15 (1 giờ). Khớp thì SL như S07 (đáy/đỉnh cửa sổ ∓ 0,1 ATR, 1–4 ATR; nếu giá khớp đã nằm ngoài SL thì bỏ). Không khớp thì **bỏ lệnh** |

**LQ thay MK** cho tín hiệu giao phiên khi, ở cả train, validate và test:
- tổng R ≥ MK;
- R/lệnh > MK.

Báo cáo thêm: tỉ lệ khớp; tỉ lệ cú quét đi quá SL; bản kiểm tra M5 từ 05/2024.

## Phần C — rủi ro (chỉ khi Phần A có nhãn đạt, sổ lệnh gốc M30, không bồi)

| Mức | Nhóm có nhãn | Lệnh còn lại |
|---|---|---|
| R0 | 1,5% | 1,5% |
| R2 | 2,0% | 1,5% |
| R25 | 2,5% | 1,5% |
| R3 | 3,0% | 1,5% |

Một mức được chấp nhận khi, ở cả 09/2018–06/2026 và 07/2021–06/2026:
- chạm 30% trong cửa sổ 1 năm ≤ 5%;
- DD p90 ≤ 25%;
- tỉ số %/năm ÷ DD p90 > R0.

Chọn mức cao nhất đạt.

## Đầu ra

`research/long/g84_vol_session.py`, báo cáo `reports/2026-10-10-g84-vol-session-sweep.md`.
