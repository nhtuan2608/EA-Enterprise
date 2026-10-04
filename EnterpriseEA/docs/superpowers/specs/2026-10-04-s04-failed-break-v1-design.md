# Đặc tả S04 Failed Break v1 (G9)

Ngày 04/10/2026. Trạng thái: **DESIGN — chưa sửa source**. Chờ người dùng chốt các quyết định ở mục 12. Mọi con số ở mục 9 là seed PROPOSED.

Nguồn:
- master specification v1.4: mục 4.4 (S04 Failed Break: *Break → no acceptance → return inside → rejection/reclaim*; invalidation: *acceptance lại theo hướng break*), TC-005 (*S04 chỉ kích hoạt sau return inside/reclaim, không chỉ từ wick đơn*), TC-006, mục S2 của lộ trình ("ưu tiên S02 và S04 để kiểm tra sequence đối lập");
- S02 Break Retest v1 design;
- Trade Manager v1, News Guard, Market sentiment, Live session authorization.

---

## 1. Ý tưởng

S02 và S04 là **hai kết cục ngược nhau của cùng một lần phá vùng**:

| | S02 Break Retest | S04 Failed Break |
|---|---|---|
| Sau khi giá phá vùng | Được **chấp nhận** (đóng cửa giữ phía ngoài vùng) | **Không được chấp nhận**: đóng cửa quay lại trong vùng |
| Hướng lệnh | **Theo** hướng phá | **Ngược** hướng phá |
| Ví dụ | Phá lên trên vùng, retest, mua | Phá lên trên vùng, rơi lại vào vùng, từ chối, **bán** |

Phần thua của S02 chính là cơ hội của S04. Dùng chung vùng hợp lưu giúp hai setup không bao giờ đánh giá cùng một vùng theo hai cách khác nhau.

## 2. Dùng lại từ S02 v1 (không đổi)

- **Vùng hợp lưu (Location):** PDH/PDL, đỉnh/đáy phiên, swing H1/H4; dung sai 0,25×ATR; ≥ 2 nguồn khác loại; bề rộng ≤ 0,5×ATR.
- **Profile:** SCALP (M5, context H1) và SWING (H1, context H4); mỗi profile một engine riêng.
- **Xu hướng khung lớn (HTF):** lệnh ngược HTF thì rủi ro × 0,5.
- **Đường rủi ro:** O-04, FTMO, giới hạn tiền tệ và tương quan, giới hạn lỗ nội bộ ngày/tuần, spread guard, chi phí, lot theo rủi ro.
- **News Guard** đỏ/vàng, **Market sentiment** (chỉ giảm), **giới hạn lệnh/ngày của phiên** theo profile, **chọn kiểu lệnh tự động**, **Trade Manager**, **command queue**: tất cả áp nguyên như với S02.

## 3. Chuỗi sự kiện và trạng thái (ví dụ phá lên rồi thất bại → lệnh BÁN; chiều ngược lại đối xứng)

| Bước | Trạng thái | Điều kiện (trên nến **đã đóng** của khung entry) | Thất bại |
|---|---|---|---|
| 1 | `BREAK_ATTEMPT` | Nến đóng cửa **trên** đỉnh vùng ≥ 0,10×ATR, thân ≥ 50% biên độ (giống điều kiện phá của S02) | — |
| 2 | `RETURNED` | Trong **3 nến** sau nến phá, có nến **đóng cửa trở lại ≤ đỉnh vùng** (vào trong vùng hoặc thấp hơn). Đây là "no acceptance + return inside" | 2 nến liên tiếp đóng trên đỉnh vùng → phá vỡ **được chấp nhận** → hủy (`BREAK_ACCEPTED`; trường hợp này thuộc về S02) |
| 3 | `TRIGGERED` | Trong **3 nến** sau `RETURNED`, có nến **giảm**, thân ≥ 40%, đóng cửa **dưới đáy của nến RETURNED** ít nhất 0,05×ATR (từ chối / reclaim) | Hết 3 nến → `TRIGGER_EXPIRED` |
| — | `INVALIDATED` | Bất kỳ lúc nào: nến đóng trên **đỉnh cao nhất của nhịp phá** + 0,10×ATR, hoặc 2 nến đóng trên đỉnh vùng | `THESIS_INVALIDATED` |

- **Râu nến đơn lẻ không tạo S04 (TC-005):** râu vượt vùng nhưng đóng cửa trong vùng không phải là "break attempt", nên không có candidate.
- **Bảo vệ nến:** nến trùng hoặc lùi thời gian bị bỏ qua, giống S02. Engine lưu checkpoint và khôi phục khi gắn lại EA, không tạo candidate trùng.
- **Nối với S02:** engine S02 đã ghi nhận `ACCEPTANCE_FAILED` đúng lúc bước 2 của S04 xảy ra. S04 dùng chung bộ phát hiện "phá vùng" và vùng hợp lưu với S02, nhưng giữ máy trạng thái riêng để hai setup không ảnh hưởng nhau.

## 4. Entry, SL, TP

- **SL:** sau **cực trị của nhịp phá thất bại** (đỉnh cao nhất từ `BREAK_ATTEMPT` tới `TRIGGERED` với lệnh bán) cộng buffer = max(0,10×ATR, 1,5×spread). Làm tròn theo tick, phải thỏa stops/freeze level.
- **TP:** level cấu trúc gần nhất theo hướng lệnh, **phía bên kia của vùng** (với lệnh bán: dưới đáy vùng), cách entry ≥ 1R thô. Không có target cấu trúc thì bỏ lệnh (`NO_STRUCTURAL_TARGET`).
- **RR ròng tối thiểu:** 1,5 (SCALP) / 2,0 (SWING), tính đủ chi phí như S02.
- **Kiểu lệnh tự động**, cùng khuôn với S02:

| Tình huống khi `TRIGGERED` | Lệnh |
|---|---|
| Giá đã vượt cực trị nến trigger (từ chối đã xác nhận) | MARKET |
| SCALP, cùng chiều HTF, giá chưa hồi quá 0,25×ATR so với close nến trigger | MARKET |
| SWING, ngược HTF, hoặc giá đã hồi sâu hơn | STOP cách cực trị nến trigger 1 tick |
| Giá đã chạy quá 0,5×ATR | Bỏ (`ENTRY_AUTO_CHASE_TOO_FAR`) |

S04 **không** dùng LIMIT trong v1: điểm vào tốt nhất của S04 là lúc từ chối đã được xác nhận, không phải lúc giá còn ở trong vùng.

## 5. Quan hệ với S02 trên cùng symbol

- **Không bao giờ có hai vị thế ngược chiều trên cùng symbol do hai setup mở:** khi đang có vị thế hoặc lệnh chờ S02 theo một hướng, candidate S04 theo hướng ngược lại trên cùng symbol bị bỏ (`OPPOSITE_SETUP_ACTIVE`), và ngược lại. (D4)
- **Cùng hướng:** hai setup cùng hướng trên cùng symbol vẫn bị giới hạn bởi giới hạn tương quan và tổng rủi ro mở của O-04 như hiện nay.
- **Giới hạn lệnh/ngày của phiên** đếm chung theo profile (SCALP 10 / SWING 5 như bạn đã đặt), không tách theo setup.

## 6. Trade Manager

- Dùng chung profile SCALP/SWING (chốt một phần, dời SL hòa vốn, trail, time stop).
- **Structure invalidation cho S04:** trước khi dời SL hòa vốn, một nến đóng cửa **trở lại trên đỉnh vùng** (với lệnh bán) nghĩa là phá vỡ đã được chấp nhận → đóng lệnh sớm.
- Mọi bản ghi lệnh mang `setup_id = S04`, để thống kê và Trade Manager phân biệt được với S02.

## 7. Dashboard và audit

- **Tab Market:** cột setup hiện cả hai, ví dụ `SC: S02 ARMED · S04 RETURNED`. Rê chuột xem chi tiết vùng và nhịp phá.
- **Audit:** mỗi chuyển trạng thái của S04 có `setup_id`, vùng, cực trị nhịp phá, lý do. Candidate được lưu cùng cấu trúc với S02 (`strategy_<symbol>_<tf>_s04.json`).
- **Tab Settings → System:** hiện chế độ S04 đang chạy (`SHADOW` / `LIVE` / `OFF`).

## 8. Kiểm chứng

| Cách | Nội dung |
|---|---|
| **Replay lịch sử (D6)** | Chạy engine S04 (và S02 để so sánh) trên nến lịch sử từ 01/01/2026, giống backfill của bộ ghi tin. Ghi mọi candidate: tần suất theo symbol/profile, MFE/MAE theo R, thời gian tới 1R, tỷ lệ chạm SL trước TP. **Chỉ đo, không giao dịch.** |
| **Shadow forward (D5)** | 1–2 tuần đầu S04 chỉ phát hiện và ghi candidate kèm kế hoạch lệnh (entry/SL/TP/lot giả định), **không gửi lệnh**. |
| **Bật live** | Chỉ sau khi người dùng xem số liệu replay + shadow và đồng ý. |

## 9. Tham số seed (PROPOSED)

| Tham số | SCALP (M5) | SWING (H1) |
|---|---|---|
| Phá: buffer / thân nến | 0,10×ATR / 50% | 0,10×ATR / 50% |
| Cửa sổ quay lại trong vùng (D2) | 3 nến | 3 nến |
| Cửa sổ trigger (D3) | 3 nến | 3 nến |
| Trigger: thân nến / vượt đáy nến RETURNED | 40% / 0,05×ATR | 40% / 0,05×ATR |
| Invalidation buffer | 0,10×ATR | 0,10×ATR |
| TTL candidate sau trigger | 2 nến | 2 nến |
| SL buffer | max(0,10×ATR, 1,5×spread) | max(0,10×ATR, 1,5×spread) |
| RR ròng tối thiểu | 1,5 | 2,0 |

## 10. Kiểm thử

| ID | Kịch bản → kết quả mong đợi |
|---|---|
| TC-S04-01 (TC-005) | Râu vượt vùng nhưng đóng cửa trong vùng → không có candidate |
| TC-S04-02 | Phá (đóng trên vùng) → nến kế đóng lại trong vùng → nến giảm thân ≥ 40% đóng dưới đáy nến RETURNED → `TRIGGERED SHORT` |
| TC-S04-03 | Phá rồi 2 nến đóng trên vùng → `BREAK_ACCEPTED`, không có candidate S04 (đây là S02) |
| TC-S04-04 | Sau `RETURNED`, nến đóng trên đỉnh nhịp phá + 0,10×ATR → `INVALIDATED` |
| TC-S04-05 | `RETURNED` nhưng 3 nến không có trigger → `TRIGGER_EXPIRED` |
| TC-S04-06 | SL đặt sau đỉnh nhịp phá; TP là level cấu trúc dưới vùng ≥ 1R; không có target → `NO_STRUCTURAL_TARGET` (TC-006) |
| TC-S04-07 | Đang có vị thế S02 BUY trên XAUUSD → candidate S04 SELL XAUUSD bị bỏ `OPPOSITE_SETUP_ACTIVE` |
| TC-S04-08 | Gắn lại EA giữa chừng → engine khôi phục đúng trạng thái, không tạo candidate trùng |
| TC-S04-09 | Chế độ SHADOW → có candidate và kế hoạch lệnh trong audit, không có `EXECUTION_REQUESTED` |
| TC-S04-10 | Replay lịch sử cho số liệu giống hệt khi chạy hai lần (xác định, không phụ thuộc thời điểm chạy) |

## 11. Kế hoạch triển khai

1. Module thuần `Setups/FailedBreak.mqh` (máy trạng thái S04) + oracle Python + test TC-S04-01..05.
2. Nối vào strategy runtime: S04 chạy cạnh S02 trên cùng vùng/profile, có checkpoint riêng (TC-S04-08).
3. Kế hoạch lệnh S04 (SL/TP/RR, kiểu lệnh) qua đường rủi ro hiện có; quy tắc ngược chiều với S02 (TC-S04-06, 07).
4. Chế độ `InpS04Mode = SHADOW / LIVE / OFF` (mặc định SHADOW) và audit kế hoạch lệnh (TC-S04-09).
5. Replay lịch sử S02 + S04 từ 01/01/2026, chỉ đo (TC-S04-10).
6. Dashboard: tab Market và System. Compile, test, deploy.

## 12. Quyết định cần người dùng chốt

| ID | Câu hỏi | Đề xuất |
|---|---|---|
| D1 | Định nghĩa "phá" của S04 | Giống S02: đóng cửa ngoài vùng ≥ 0,10×ATR, thân ≥ 50% |
| D2 | Cửa sổ "quay lại trong vùng" | 3 nến khung entry (SCALP 15 phút, SWING 3 giờ) |
| D3 | Điều kiện trigger | Nến thân ≥ 40% đóng vượt cực trị của nến RETURNED ≥ 0,05×ATR, trong 3 nến |
| D4 | Ngược chiều với S02 trên cùng symbol | Không cho hai vị thế ngược chiều; setup đến sau bị bỏ |
| D5 | Chế độ bắt đầu | **SHADOW** 1–2 tuần (chỉ ghi candidate và kế hoạch lệnh), sau đó người dùng quyết định LIVE |
| D6 | Replay lịch sử | Có: chạy S02 + S04 trên nến từ 01/01/2026, chỉ đo |
