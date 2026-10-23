# G153b: SHADOW forward hai ứng viên G153 — kế hoạch đăng ký trước (23/10/2026)

## Vì sao

G153 không có ô nào đạt. Hai ứng viên gần nhất, chỉ lấy lệnh cùng chế độ D1:
- **SQZ**, squeeze breakout M30: thắng lệnh ngẫu nhiên cùng chế độ (p 0,005), dương trên BTC; 2022–23 và lệnh bán âm;
- **W1**, phá đỉnh/đáy tuần trước: dương trên BTC, nhưng chưa tách khỏi phần ăn theo xu hướng (p 0,13).

Người dùng đồng ý (23/10) chạy SHADOW để có dữ liệu forward thật, không bị nhìn trước.

## Cách chạy

- Module `Bots/ShadowCandidates.mqh` trong EnterpriseEA_Bots. Input `InpShadowSqueeze`, `InpShadowWeekly`, mặc định bật.
- Chỉ lệnh ảo: không đặt lệnh, không có cờ Active, không tính vào rủi ro danh mục.
- Ghi vào `logs/bots-YYYYMM.jsonl` với mã `SQZ` và `W1`. Đọc bằng `/botlog sqz`, `/botlog w1` hoặc MCP `read_bot_log`.
- Luật đóng băng như code nghiên cứu: `g139_hybrid.csq` và `g149_repeating.w1` (không TP). Cổng chế độ là luật R1 của XauRegime, trạng thái D1 của ngày đã đóng.
- Lệnh cùng chế độ: `ENTRY` / `EXIT`, có `r`. Lệnh ngoài cổng vẫn theo dõi (SQZ: vẫn chiếm chỗ "một lệnh một lúc" như nghiên cứu), ghi `SKIP` / `MANAGE` với `r_ungated`.
- R tính bằng giá thật (mua theo ask, bán theo bid), chưa trừ commission.
- Giữ **cả hai chiều**. Lệnh bán được báo riêng, không bỏ.

## Khi nào xét

Mốc xét, mỗi ứng viên riêng: **≥ 30 lệnh cùng chế độ**, hoặc **12 tháng** từ ngày EA mới được nạp, tùy cái nào đến trước. Ước lượng theo nghiên cứu:
- SQZ khoảng 44 lệnh/năm, nên đủ 30 lệnh sau khoảng 8 tháng;
- W1 khoảng 23 lệnh/năm, nên thường tới mốc 12 tháng trước.

Xem sớm sau 4–6 tuần, chỉ để kiểm tra code chạy đúng, không dùng để quyết định.

## Kiểm tra code (trước khi đọc kết quả)

1. Chạy lại `csq` / `w1` của Python trên nến forward (data MT5 export cùng kỳ). So với nhật ký:
   - ≥ 80 % lệnh Python có lệnh SHADOW cùng chiều, vào cùng nến M30 (W1: cùng ngày);
   - ngược lại cũng ≥ 80 %.
2. Nếu dưới 80 %: sửa module, ghi lại, và đếm lại từ đầu. Kết quả trước khi sửa không dùng để quyết định.

## Tiêu chí (chỉ lệnh cùng chế độ)

**Đạt, được bàn LIVE rủi ro nhỏ** khi cùng đúng:
1. R/lệnh trung bình ≥ +0,10R sau khi trừ 0,05R/lệnh cho phí;
2. tổng R dương khi bỏ lệnh lãi lớn nhất;
3. lệnh mua và lệnh bán đều được báo cáo; nếu có ≥ 8 lệnh bán thì R/lệnh bán ≥ −0,10R;
4. lệnh cùng chế độ tốt hơn lệnh ngoài cổng (R/lệnh). Chỉ báo cáo, không bắt buộc.

LIVE cần người dùng đồng ý, rủi ro ≤ 0,25 %/lệnh lúc đầu.

**Dừng sớm**:
- sau ≥ 20 lệnh cùng chế độ mà R/lệnh ≤ −0,30R, thì dừng ứng viên đó và ghi báo cáo;
- module lỗi.

**Không đạt nhưng không dừng**: ghi báo cáo, người dùng quyết chạy tiếp hay tắt (input = false).

Không chỉnh luật trong lúc chạy. Muốn đổi luật thì mở G mới và đếm lại từ đầu.
