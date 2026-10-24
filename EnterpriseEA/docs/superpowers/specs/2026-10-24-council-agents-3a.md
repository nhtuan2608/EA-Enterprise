# Hội đồng AI — thiết kế các agent (bước 3a, 24/10/2026)

Bổ sung cho [thiết kế bộ não + hội đồng](2026-10-24-ai-brain-council-design.md). Dựa trên kết quả G156a–G157:

| Phát hiện | Nguồn | Hệ quả cho thiết kế |
|---|---|---|
| Phá giả hay đi tiếp, tính từ giá hiện tại: vàng 51 %, FX 49–51 %, BTC 54 %. Không trường bối cảnh giá nào đoán tốt hơn | G156a2, G157 | **Không có agent "đọc chart đoán hướng".** Câu này do mỏ neo trả lời bằng tỷ lệ nền |
| 12 tình huống có tên (tin, quét, volume, đa khung, key level) không báo trước hướng, ở 4 / 5 thị trường | G156c, G157 | Tình huống chỉ dùng để **cảnh báo và giải thích** |
| Không bối cảnh nào xếp hạng được lệnh S07 | G156b | Không agent nào được "lọc" S07 bằng thông tin giá |
| Vào sớm khi S07 mới 4/5: tốt nhất 48 %, cần khoảng 78 % | G156b | Không có quyền vào sớm; chỉ đo bằng lệnh ảo |
| Lệnh S07 đang lời đi tiếp +1R trước khi lùi 1R: 61 % | G156a2 | Mặc định **để lệnh lời chạy**; mọi đề xuất cắt sớm phải thắng 61 % |

**Kết luận thiết kế:** hội đồng chỉ có giá trị ở **thông tin ngoài giá**. Đó là tin tức, bất thường thực thi, sức khỏe bot, và việc giải
thích cho người dùng.

## 1. Danh sách agent

| # | Agent | Loại | Câu hỏi chính | Mô hình |
|---|---|---|---|---|
| 1 | **Định lượng** (mỏ neo) | luật + thống kê, **không phải AI** | Tỷ lệ nền của mọi câu hỏi; gắn tên tình huống (detector G156c) | — |
| 2 | **Tin tức** | AI | Sự kiện sắp / vừa xảy ra nguy hiểm tới đâu cho từng bot? | mô hình lớn |
| 3 | **Thực thi và bất thường** | luật phát hiện + AI diễn giải | Thị trường / broker có đang "bất thường" không? | mô hình nhỏ (làn nhanh) / lớn (họp) |
| 4 | **Giám sát bot** | thống kê tuần tự + AI diễn giải | Bot nào đang lệch khỏi dấu vân tay backtest? | mô hình vừa |
| 5 | **Logic bot** | AI có ràng buộc | Đề xuất của hội đồng có trái luật bot hay bằng chứng không? | mô hình vừa |
| 6 | **Phản biện** | AI | Lý do nào thiếu dẫn chứng, thuộc phần C, hoặc tự tin hơn mỏ neo? | mô hình lớn, khác họ với thẩm phán nếu được |
| 7 | **Thẩm phán** | AI theo quy tắc cố định | Phán quyết từ menu + kế hoạch có điều kiện | mô hình lớn nhất |
| 8 | **Người kể** | AI | Viết tóm tắt tiếng Việt cho Telegram / báo cáo thứ Bảy | mô hình nhỏ |

Không còn các vai "xu hướng" và "thanh khoản / cấu trúc" của bản thiết kế đầu. Thông tin xu hướng, mức và tình huống vẫn có trong gói bối
cảnh, nhưng là **dữ liệu do agent 1 cung cấp**, không phải chỗ để AI suy đoán hướng.

## 2. Chi tiết từng agent

### Agent 1 — Định lượng (mỏ neo, không phải AI)

- **Nhận:**
  - gói bối cảnh (G156a);
  - mô hình mỏ neo (G156b / G156a2);
  - detector 12 tình huống (G156c);
  - tỷ lệ nền theo thị trường (G157).
- **Trả:**
  - Q1b: 51 % (vàng), 54 % (BTC), 50 % (FX);
  - Q2: R kỳ vọng như nhau cho mọi lệnh S07;
  - Q3: xác suất mô hình M2;
  - Q4: 61 % với lệnh đang lời (bảng M1);
  - danh sách tình huống đang có, mỗi cái kèm câu "không báo trước hướng (G156c)";
  - phiếu trạng thái 6 trục (tầng 1).
- **Được dẫn:** phần A, B của bộ kiến thức.
- **Chấm:** chính là mốc của mọi agent khác.

### Agent 2 — Tin tức

- **Nhận:**
  - lịch tin 48 giờ (tên, mức độ, giờ, dự báo, kỳ trước, thực tế khi đã ra);
  - độ lệch kỳ vọng chuẩn hóa (cách G129);
  - lịch sử phản ứng của vàng với từng loại tin (biên độ trung bình 1 giờ sau tin, theo ATR);
  - trạng thái bot và lệnh đang mở;
  - **nội dung tin bằng chữ, nếu có nguồn** (xem mục 6).
- **Câu hỏi:**
  - (a) biến động 1 giờ quanh tin sẽ lớn hơn mức thường của loại tin này không;
  - (b) lệnh đang mở có nên giảm rủi ro / hòa vốn trước tin không (theo A15: chỉ có lợi khi thị trường đi ngang);
  - (c) có sự kiện ngoài lịch (phát biểu, địa chính trị) đáng dừng không.
- **Được dẫn:** A14, A15, B12, C4, C18, E2.
- **Không được:** đoán hướng giá sau tin (A14, C4: tin đã phản ánh ngay trong nến tin).
- **Chấm:**
  - (a) Brier so với mỏ neo "biên độ lịch sử của loại tin";
  - (b) R của lệnh nếu làm theo đề xuất, so với để nguyên (đo ảo).

### Agent 3 — Thực thi và bất thường

- **Phát hiện bằng luật** (chạy mỗi tick / mỗi phút, làn nhanh):
  - spread > 3 lần trung vị cùng giờ;
  - trượt giá lệnh thật > 0,2R;
  - broker từ chối lệnh;
  - mất tick > 2 phút trong giờ mở cửa;
  - nến > 3 ATR;
  - gap cuối tuần > 2 ATR;
  - lệch đồng hồ server;
  - file trạng thái EA cũ quá 2 phút.
- **AI diễn giải** khi có phát hiện:
  - nguyên nhân có thể (tin, thanh khoản mỏng, lỗi broker);
  - kéo dài bao lâu;
  - bot nào bị ảnh hưởng.
- **Được đề xuất:** dừng lệnh mới N phút, chặn bồi lệnh.
- **Được dẫn:** A12, A13, E5.
- **Chấm:**
  - tỷ lệ cảnh báo đúng (sau cảnh báo, lệnh vào trong cửa sổ đó có chi phí / trượt cao hơn thật);
  - số cảnh báo sai mỗi tuần.

### Agent 4 — Giám sát bot

- **Dấu vân tay** của mỗi bot (từ backtest và sổ ảo):
  - tỷ lệ thắng, phân bố R;
  - chuỗi thua p95 / p99;
  - sụt vốn 30 ngày p90;
  - số lệnh mỗi tuần;
  - thời gian giữ;
  - tỷ lệ mua / bán.
- **Kiểm định tuần tự**, chạy mỗi khi có lệnh đóng: CUSUM trên R, so với dấu vân tay. Cảnh báo ở 2 mức "đáng ngờ" và "lệch hẳn".
- **AI diễn giải:**
  - lệch vì thị trường đổi chế độ (ví dụ D1 chuyển giảm kéo dài, E2), vì lỗi thực thi, hay chỉ là chuỗi xấu bình thường;
  - đề xuất giảm rủi ro bot đó.
- **Được dẫn:** A1, A5–A9, A17 (giảm rủi ro chỉ tương đương giảm rủi ro chung), E2, E3.
- **Chấm:**
  - số cảnh báo sai (bot hồi lại bình thường);
  - độ trễ phát hiện khi lệch thật.

  Kiểm được một phần trên quá khứ bằng cách bơm chuỗi xấu giả vào sổ.

### Agent 5 — Logic bot

- **Nhận:**
  - luật từng bot (phần D);
  - trạng thái điều kiện S07 (4/5 hay 5/5);
  - lệnh đang mở, R đang có;
  - đề xuất của các agent khác.
- **Câu hỏi:** đề xuất có trái luật bot hay trái bằng chứng không. Ví dụ:
  - cắt lệnh S07 đang lời (B21: 61 % đi tiếp);
  - "lọc" S07 bằng thông tin giá (G156b);
  - áp luật "đừng làm" của lệnh ngẫu nhiên cho S07 / VHedge (C11);
  - vào sớm (G156b).
- **Trả:** đồng ý / phản đối từng đề xuất, kèm mã kiến thức.
- **Chấm:** các phản đối của agent này, nếu bị bỏ qua, có làm kết quả tệ đi không (đo trên lệnh ảo).

### Agent 6 — Phản biện

- **Nhận:** mọi ý kiến vòng 1, mỏ neo, phần C và E của bộ kiến thức.
- **Bắt buộc kiểm:**
  - mọi ý kiến về **hướng giá** có tự tin hơn mỏ neo không (vàng 51 %, BTC 54 %, FX 50 %); nếu có, dẫn chứng ở đâu;
  - lý do có thuộc phần C không (C1–C18);
  - có rơi vào giới hạn E không (dữ liệu một chu kỳ tăng, lệnh theo cụm);
  - có dùng tình huống có tên để đoán hướng không (C18).
- **Chấm:** những lần phản biện làm đổi phán quyết thì kết quả tốt lên hay tệ đi.

### Agent 7 — Thẩm phán

Như thiết kế chung, mục 4.2: xuất phát từ mỏ neo, chỉ dịch khi có lý do còn đứng sau phản biện, không đưa lý do mới, kết luận từ menu.
**Thêm:**
- câu hỏi về **hướng giá** không bao giờ được đưa đi xa mỏ neo quá ± 5 điểm % khi chưa có bằng chứng forward;
- xuất **kế hoạch có điều kiện** (thiết kế chung, mục 4.4) cho lệnh đang mở.

**Chấm:**
- so với (a) mỏ neo, (b) agent giỏi nhất, (c) trung bình các agent;
- R của lệnh ảo nếu làm theo phán quyết.

### Agent 8 — Người kể

- Viết tóm tắt tiếng Việt cho Telegram và báo cáo thứ Bảy, chỉ từ phán quyết và lý do đã được duyệt. Không thêm nhận định.
- **Chấm:** người dùng đánh giá. Không chấm tự động.

## 3. Khi nào hội đồng họp

So với G156a (khoảng 6 giờ / ngày), bỏ việc họp cho mọi cú phá mức (Q1b) và mọi trạng thái 4/5 (Q3): hai câu này do mỏ neo trả lời.

| Kích hoạt | Ai họp | Tần suất ước tính |
|---|---|---|
| 60 phút trước tin USD HIGH, và ngay sau nến tin | 2, 3, 5, 6, 7 | khoảng 3–6 lần / tuần |
| Phát hiện bất thường (agent 3) | làn nhanh: 3; sau đó họp 3, 5, 6, 7 | hiếm, chưa ước được |
| Bot sắp vào lệnh (Q2: S07, VHedge, CtxLimit) | 2, 3, 5, 6, 7 (agent 1 trả R kỳ vọng) | khoảng 2–5 lần / tuần |
| Lệnh đang mở mỗi giờ (Q4) | **chỉ agent 1**, trừ khi có tin hay bất thường trong giờ tới thì họp đủ | mỗi giờ (rẻ) |
| Bot lệch dấu vân tay (agent 4) | 4, 5, 6, 7 | hiếm |
| Báo cáo sáng / thứ Bảy | 8, lấy từ nhật ký | 1 lần / ngày |

Mục tiêu: hội đồng đầy đủ **dưới 2 lần / ngày** trung bình, thay vì 6 giờ / ngày.

## 4. Dữ liệu mỗi agent nhận (để tránh agent đọc thứ không cần)

| Trường | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Gói bối cảnh giá (G156a) | ✔ | — | phần biến động | — | phần S07 | ✔ | ✔ (tóm tắt) |
| Tình huống có tên (G156c) | ✔ | — | — | — | — | ✔ | ✔ |
| Lịch tin + độ lệch kỳ vọng + phản ứng lịch sử | — | ✔ | — | — | — | — | tóm tắt |
| Nội dung tin bằng chữ | — | ✔ | — | — | — | — | — |
| Spread, trượt giá, từ chối, tick, đồng hồ | — | — | ✔ | — | — | — | tóm tắt |
| Sổ lệnh, dấu vân tay, CUSUM | — | — | — | ✔ | — | — | tóm tắt |
| Luật bot, điều kiện S07, lệnh mở | — | — | — | — | ✔ | — | ✔ |
| Ý kiến vòng 1 của các agent | — | — | — | — | ✔ | ✔ | ✔ |
| Bộ kiến thức: mã được dẫn | A, B | A14, A15, B12, C4, C18, E2 | A12, A13, E5 | A1, A5–A9, A17, E2, E3 | D, B21, C11 | C, E | toàn bộ |

## 5. Khuôn trả lời chung (JSON)

```json
{
  "agent": "tin_tuc",
  "cau_hoi_id": "2026-10-30T15:00Z#news#CPI",
  "xac_suat": {"bien_dong_1h_lon_hon_thuong": 0.62},
  "de_xuat": "giam_rui_ro_50",
  "thoi_han_phut": 90,
  "ly_do": [
    {"noi_dung": "CPI lệch kỳ vọng lần trước +2,1 độ lệch chuẩn", "dan_chung": ["ctx.news.surprise_z_prev"]},
    {"noi_dung": "thị trường đang đi ngang, hòa vốn trước tin có lợi", "dan_chung": ["A15", "ctx.state.trend"]}
  ],
  "muc_tu_tin": "vua"
}
```

Bộ kiểm tra loại câu trả lời khi:
- sai khuôn;
- lý do không có dẫn chứng;
- dẫn chứng không tồn tại;
- dẫn một mã thuộc phần C làm lý do;
- `de_xuat` ngoài menu.

## 6. Câu hỏi mở cần người dùng quyết

1. **Nguồn tin bằng chữ.** MT5 chỉ có lịch và con số, **không có nội dung tin** cho EA đọc. Không có nguồn chữ thì agent 2 chỉ làm việc
   với lịch và con số, và phần giá trị "ngoài giá" lớn nhất bị thiếu. Cần chọn một nguồn tin (RSS / API). Đây là dữ liệu ngoài MT5 nên
   cần người dùng đồng ý.
2. **Mô hình cho từng vai và ngân sách API** mỗi tháng.
3. **Phạm vi:** chỉ demo, hay cả VPS cent; chỉ XAUUSD trước, hay cả BTC.

### Quyết định của người dùng (25/10/2026)

| Câu hỏi | Quyết định |
|---|---|
| Nguồn tin bằng chữ | **Làm sau.** Ghi lại yêu cầu (bên dưới); đến khi có nguồn, agent 2 chỉ dùng lịch và con số |
| Ngân sách API | **Dưới 20 lần gọi mô hình mỗi ngày** cho toàn hệ thống. Một cuộc họp đầy đủ khoảng 5–6 lần gọi, nên tối đa khoảng 3 cuộc họp mỗi ngày; làn nhanh và người kể tính chung vào hạn mức này |
| Phạm vi | **Demo và VPS cent**; **vàng trước**, thị trường khác sau |

**Yêu cầu cho nguồn tin, khi làm:**
- tiêu đề và tóm tắt tin có dấu thời gian UTC;
- nguồn ổn định, có lưu trữ để đối chiếu;
- lọc theo USD, vàng, Fed, địa chính trị;
- người dùng duyệt nguồn trước khi nối.

Nếu cần dữ liệu ngoài MT5 thì phải ghi rõ trong kế hoạch.

**Hệ quả của hạn mức 20 lần / ngày:**
- bộ điều phối giữ một bộ đếm ngày;
- khi gần hết hạn mức chỉ họp cho bất thường và tin lớn;
- nếu hết hạn mức thì quay về luật và mỏ neo (an toàn, như khi AI lỗi);
- Q4 mỗi giờ luôn do agent 1 trả lời, không tốn lượt gọi.

## 7. Bước tiếp theo (3b)

- Giao thức 2 vòng chạy được (điều phối Python gọi Claude API).
- Bộ kiểm tra dẫn chứng.
- Detector cho agent 3 và CUSUM cho agent 4.
- Gói bối cảnh mở rộng (tin, thực thi).

Thử trên vài ca quá khứ chỉ để soát lỗi, không dùng để chấm. Sau đó là G156: chạy forward trên demo, giai đoạn A (chỉ ghi lại).
