# Bộ não cho bot và hội đồng AI — thiết kế (24/10/2026)

Tài liệu tổng hợp các trao đổi với người dùng ngày 24/10/2026. Đây là định hướng chung; mỗi bước làm có kế hoạch đăng ký trước riêng (G156…).
Bộ kiến thức nền: [docs/ai-knowledge/knowledge-base.md](../../ai-knowledge/knowledge-base.md).

## 1. Vì sao

- Các bot hiện vào lệnh theo **điều kiện kích hoạt**, đặt trong một khung môi trường tối giản: xu hướng H4/D1, tin tức, giới hạn rủi ro.
  Hệ thống chưa có lớp nào nhận ra kiểu thị trường rồi điều chỉnh.
- G146–G155 cho thấy các lớp lọc môi trường phức tạp (bản đồ rủi ro, chấm điểm nhiều yếu tố, lịch, dòng lệnh) không đứng vững. Tín hiệu môi
  trường duy nhất lặp lại được là **chiều xu hướng D1**.
- Người dùng muốn bot có "bộ não":
  - đọc diễn biến **mỗi giờ**;
  - nhận định **phá giả hay xu hướng đi tiếp**;
  - phối hợp với logic bot để quyết định.

  Người dùng không trực tiếp hỏi: **bot tự đặt câu hỏi**.
- Người dùng không muốn một AI duy nhất (chủ quan, không ai phản biện). Cần **nhiều agent tranh luận, một agent chính phán quyết**, và có
  cách đánh giá.

## 2. Nguyên tắc

1. **Luật chạy những gì có dữ liệu để kiểm; AI chỉ dùng cho chỗ dữ liệu quá khứ không trả lời được**: tình huống lạ, tin tức bằng chữ,
   bất thường.
2. **AI không backtest được.** Mô hình đã thấy lịch sử giá, nên mọi đánh giá AI phải là **forward**.
3. **Quyền của AI lệch một chiều.** AI chỉ được **giảm rủi ro / bỏ tín hiệu / tạm dừng có thời hạn**. Không bao giờ tự mở lệnh hay tăng
   rủi ro. Tăng hoặc mở lại cần người xác nhận.
4. **AI lỗi, chậm hoặc trả lời sai khuôn thì giữ quyết định của luật.** Không có AI, hệ thống vẫn an toàn.
5. **Mọi lập luận phải có dẫn chứng.** Mỗi lý do dẫn **mã kiến thức** (A/B…) hoặc số trong gói bối cảnh. Lý do thuộc phần C ("đã thất
   bại") bị loại.
6. **Có mỏ neo bằng số.** Mọi ý kiến AI được so với một mô hình thống kê đơn giản. Không hơn mỏ neo thì không dùng AI.

## 3. Kiến trúc 4 tầng

```
 Mỗi tick (ms)        TẦNG 0 · PHẢN XẠ     SL/TP, giới hạn lỗ, kill switch, News Guard — luôn chạy, không ai ghi đè
 Mỗi nến M30 (s)      TẦNG 1 · BỘ NÃO      phiếu trạng thái → sổ chiến thuật → độ quen; luật cố định, kiểm được
 Mỗi giờ / sự kiện    TẦNG 2 · HỘI ĐỒNG AI bộ phát câu hỏi → các agent tranh luận → thẩm phán
 Khi cần (giờ)        TẦNG 3 · NGƯỜI       xác nhận qua Telegram khi tăng rủi ro hoặc mở lại
```

### 3.1 Tầng 1 — phiếu trạng thái (mỗi nến M30)

| Trục | Đo bằng | Trạng thái |
|---|---|---|
| Xu hướng | chế độ D1 (EMA50 + độ dốc), phía EMA200 H4 | tăng / giảm / trung tính / mâu thuẫn |
| Biến động | ATR14 theo phân vị lịch sử | thấp / bình thường / cao / cực đoan (> p99) |
| Cấu trúc | ADX, độ nén | nén / mở rộng / đã chạy xa |
| Sự kiện | lịch tin, rollover, gap cuối tuần | yên / trước tin / sau tin / gap |
| Thực thi | spread so với trung vị, trượt giá, broker từ chối | tốt / xấu / hỏng |
| Sức khỏe bot | kết quả gần đây so với "dấu vân tay" backtest | bình thường / đáng ngờ / lệch hẳn |

- **Sổ chiến thuật**: mỗi trạng thái đã biết → bot nào chạy, hệ số rủi ro bao nhiêu. **Chỉ những dòng đã kiểm mới được vào sổ** (ví dụ D1
  ngược × 0,5 theo G134; hòa vốn trước tin theo G152).
- **Độ quen**: trạng thái này đã xuất hiện bao nhiêu lần trong 2010–2026. Quen và nhất quán thì bộ não tự quyết. Lạ, mâu thuẫn hoặc bất
  thường thì chuyển lên tầng 2.

### 3.2 Khi nào hội đồng họp

**Bộ phát câu hỏi** viết bằng luật (không phải AI), chạy mỗi giờ:

| Sự kiện | Câu hỏi tự sinh |
|---|---|
| Một mức vừa bị phá (biên Á, đỉnh/đáy ngày trước, đỉnh/đáy tuần, swing H1) | Phá giả hay đi tiếp trong 4 giờ tới? |
| Bot sắp vào lệnh (ví dụ S07 đủ 4/5 điều kiện, CtxLimit sắp đặt limit) | Đồng ý / giảm rủi ro / bỏ? |
| Có lệnh mở và sắp có tin, hoặc biến động bất thường | Giữ hay giảm rủi ro? |
| Trạng thái lạ: biến động > p99, nến > 3 ATR, gap > 2 ATR, spread > 3 lần trung vị, bot lệch dấu vân tay | Có cần tạm dừng không? |
| Không có gì | Chỉ cập nhật ngắn, không họp |

Mục tiêu: hội đồng đầy đủ họp **vài lần mỗi ngày**, không phải mỗi nến.

## 4. Hội đồng agent (chia theo chức năng)

| Agent | Nhìn gì | Kiến thức chính |
|---|---|---|
| **Định lượng** (mỏ neo, **không phải AI**) | Tỷ lệ nền theo bối cảnh + mô hình thống kê nhỏ | phần B, kiểu G110 |
| **Xu hướng** | Chế độ D1/H4, độ dốc, lệnh đã lời bao nhiêu | A5–A8, A16 |
| **Thanh khoản / cấu trúc** | Biên phiên, đỉnh/đáy, cú quét, khoảng cách tới mức, VWAP | B2, B3, B6, B7, B13 |
| **Sự kiện và thực thi** | Lịch tin, spread, biến động bất thường, giờ trong ngày | A13, A14, B5, B12 |
| **Logic bot** | Bot đang chờ gì; câu hỏi có ý nghĩa gì với lệnh của bot | phần D, C11 |
| **Phản biện** | Tấn công kết luận đang chiếm ưu thế: lý do thuộc phần C? quá tự tin? rơi vào giới hạn E? | phần C, E |
| **Thẩm phán** (agent chính) | Tổng hợp và phán quyết theo quy tắc cố định | toàn bộ |

- Mỗi agent chỉ nhận **phần dữ liệu của vai mình** và chỉ được dẫn các mã kiến thức của vai đó.
- Có thể dùng **mô hình khác nhau** cho các vai (ví dụ Opus cho thẩm phán, Sonnet/Haiku cho các vai phân tích) để giảm sai cùng chiều.

### 4.1 Giao thức 2 vòng

```
Vòng 1    Mỗi agent làm ĐỘC LẬP, không thấy ý nhau → xác suất + lý do có dẫn chứng
          Bộ kiểm tra loại lý do không dẫn chứng hoặc thuộc phần C
Vòng 2    Phản biện tấn công ý mạnh nhất; mỗi agent xem tóm tắt của người khác, được sửa MỘT lần, phải nói vì sao
Phán quyết Thẩm phán cân các lý do còn đứng; KHÔNG được đưa lý do mới
```

### 4.2 Quy tắc thẩm phán (cố định, viết trước)

1. Xuất phát từ con số của agent định lượng.
2. Chỉ dịch khỏi con số đó khi có lý do còn đứng sau phản biện. Dịch càng xa thì càng cần nhiều lý do độc lập.
3. Bất đồng mạnh thì hạ mức tự tin; mặc định là **giữ nguyên quyết định của bot**.
4. Luôn ghi lại ý kiến thiểu số.
5. Kết luận chỉ từ menu: **đồng ý / giảm rủi ro / bỏ lệnh / tạm dừng N giờ**.

### 4.3 Khuôn trả lời

JSON cố định, đi qua bộ kiểm tra giống cách Ching-Oracle kiểm AI:
- xác suất cho từng câu hỏi;
- lý do, mỗi lý do kèm mã kiến thức hoặc trường số trong gói bối cảnh;
- mức tự tin;
- đề xuất từ menu.

Sai khuôn thì bỏ, và ghi vào nhật ký.

### 4.4 Quản lý lệnh: kế hoạch có điều kiện + làn nhanh

Hội đồng họp mất khoảng **30–90 giây**, còn quản lý lệnh khi giá giật cần phản ứng trong mili giây. Vì vậy **AI không quản lý lệnh trực
tiếp: AI viết sẵn kế hoạch có điều kiện, EA thực thi ngay khi điều kiện xảy ra.**

| Tốc độ | Ai làm | Làm gì |
|---|---|---|
| Mili giây (mỗi tick) | EA, luật cố định | SL/TP, kill switch, và **thực thi kế hoạch có điều kiện** đang hiệu lực |
| Vài giây | **Làn nhanh**: một agent mô hình nhỏ | Chỉ cho tình huống khẩn chưa có trong kế hoạch (gap lớn, tin bất ngờ, spread nổ); chỉ được "giảm rủi ro / tạm dừng", thời hạn ngắn. Hội đồng xét lại sau |
| Phút | Hội đồng đầy đủ | Đầu mỗi giờ và khi có sự kiện: viết lại kế hoạch cho giờ tới, xét lại các phản ứng nhanh |

Ví dụ một kế hoạch (EA đọc được):

```
Lệnh #123 (S07 mua), hiệu lực tới 15:00:
  NẾU nến M5 đóng lại trong biên Á            → giảm 50% khối lượng
  NẾU giá chạy thêm ≥ 1 ATR theo chiều lệnh   → giữ nguyên, không chốt sớm
  NẾU spread > 3 lần trung vị trước tin       → không bồi
  còn lại                                     → S07 quản lý như thường
Lý do: B2, A8, A14 · tự hết hạn lúc 15:00 hoặc khi lệnh đóng
```

Giới hạn:
1. **Menu hành động cố định**: giảm khối lượng, dời SL về phía an toàn hơn (không bao giờ nới ra), chốt một phần, chặn bồi, giữ nguyên.
2. Điều kiện chỉ dùng đại lượng EA tự đo được: giá đóng so với mức, số ATR, spread, thời gian tới tin.
3. Có thời hạn. Hết hạn, lỗi hoặc thiếu kế hoạch thì quay về luật gốc của bot.
4. Dữ liệu cũ cảnh báo quản lý "thông minh" từng làm hại S07:
   - G135: cách thoát hiện tại gần tối ưu;
   - G70: dời về hòa vốn làm kém đi;
   - G152: hòa vốn trước tin chỉ tốt khi đi ngang.

   Vì vậy ở giai đoạn A, kế hoạch quản lý **chỉ chạy ảo**: EA ghi "nếu làm theo kế hoạch thì lệnh kết thúc ra sao", so với cách bot tự
   quản lý.

### 4.5 Vào sớm hơn setup (chỉ đo, không làm thật)

G73 đã test vào lệnh sớm hơn S07:
- vào giữa nến chỉ sớm khoảng 15 phút, giá tốt hơn +0,02R;
- lệnh chờ đặt trước xác nhận thì dính nhiều phá giả (+0,36R so với +0,50R, DD p90 19 % so với 11 %).

Cho hội đồng kích hoạt sớm còn trái nguyên tắc quyền một chiều. Vì vậy:
- **Giai đoạn A**: khi S07 mới đủ 4/5 điều kiện, hội đồng trả lời "xác suất S07 vào lệnh trong 2 giờ tới, và nếu vào thì có lãi không".
  EA ghi một **lệnh sớm ảo** khi hội đồng đồng ý với xác suất cao.
- So với lệnh S07 thật:
  - giá vào sớm tốt hơn bao nhiêu R;
  - bao nhiêu lần S07 không bao giờ xác nhận;
  - tổng lợi có lớn hơn tổng thiệt không.
- Chỉ khi forward tốt rõ mới bàn **luật vào sớm có giới hạn**:
  - rủi ro nhỏ (ví dụ × 0,5);
  - S07 phải xác nhận trong N nến, không thì tự thoát;
  - khi xác nhận thì nâng lên rủi ro bình thường.

  Luật vẫn quyết cuối cùng.

## 5. Đánh giá

Mọi agent trả lời **bằng xác suất cho cùng câu hỏi**. Sau 4 giờ (hoặc khi lệnh đóng), hệ thống tự gán đáp án và chấm.

| Đo gì | Để biết |
|---|---|
| Điểm từng agent (độ chính xác và độ tự tin đúng mức) | Agent nào có ích, agent nào chỉ làm ồn |
| Thẩm phán so với (a) mỏ neo, (b) agent giỏi nhất, (c) trung bình cộng các agent | Tranh luận có thêm giá trị không. Không hơn (c) thì bỏ thẩm phán; không hơn (a) thì bỏ cả hội đồng |
| Những lần vòng 2 làm đổi kết luận | Đổi xong tốt lên hay tệ đi |
| Mức độ các agent sai cùng lúc | Luôn đồng ý thì hội đồng thừa người |
| Nếu làm theo phán quyết thì kết quả bot ra sao (R) | Giá trị thật, chỉ đo trên lệnh forward |

Bảng xếp hạng agent đưa vào báo cáo thứ Bảy.

### 5.1 Trao quyền theo giai đoạn

| Giai đoạn | AI được làm gì | Chuyển khi |
|---|---|---|
| **A. Chỉ ghi lại** | Trả lời và ghi nhật ký, không tác động lên lệnh | Khoảng 300 câu có đáp án (3–4 tháng) |
| **B. Phủ quyết** | Bỏ tín hiệu bot hoặc giảm rủi ro, có thời hạn | Thẩm phán thắng cả 3 mốc ở mục 5, và việc phủ quyết làm MAR tốt hơn trên lệnh forward |
| Không bao giờ | Tự mở lệnh hoặc tăng rủi ro | — |

## 6. Thứ tự làm

| Bước | Việc | Trạng thái |
|---|---|---|
| 1 | Bộ kiến thức nền v1 (A đứng vững, B tỷ lệ nền, C đã thất bại, D logic bot, E giới hạn) | **xong** 24/10 (`e22f72d`) |
| 2a | Bộ phát câu hỏi + gói bối cảnh + cách chấm đáp án | tiếp theo |
| 2b | Mỏ neo: tỷ lệ nền theo bối cảnh + mô hình thống kê nhỏ, test trên 2018–2026 | sau 2a |
| 3a | Thiết kế agent chức năng: vai, phần dữ liệu, mã kiến thức, khuôn trả lời (theo kết quả 2b) | có thể viết song song 2b, chốt sau 2b |
| 3b | Giao thức 2 vòng + quy tắc thẩm phán + bộ kiểm tra dẫn chứng; thử trên vài ca quá khứ để soát lỗi | sau 3a |
| 4 | **G156**: hội đồng chạy trên demo, giai đoạn A (chỉ ghi lại), chấm so với mỏ neo | sau 3b |

**Vì sao mỏ neo đi trước agent:**
- không có mỏ neo thì không chấm được agent;
- mỏ neo dựng luôn đường ống (câu hỏi, bối cảnh, đáp án) mà agent dùng lại;
- mỏ neo kiểm được ngay trên quá khứ;
- mỏ neo cho biết yếu tố nào thật sự đổi xác suất, để chia dữ liệu đúng cho từng agent.

## 7. Phần có sẵn và phần cần làm

**Có sẵn:**
- News Guard, trọng số D1, kill switch, Portfolio Guard;
- nhật ký bot (`logs/bots-*.jsonl`), MCP server;
- Telegram AI bridge (`bridge/ai_bridge.py`);
- khung `edge_monitor`;
- lịch nhắc thứ Bảy.

**Cần làm:**
- gói bối cảnh mỗi giờ (EA ghi JSON);
- bộ phát câu hỏi;
- mỏ neo;
- bộ điều phối hội đồng (Python, gọi Claude API theo khuôn JSON);
- bộ kiểm tra dẫn chứng;
- script chấm điểm;
- phiếu trạng thái và sổ chiến thuật của tầng 1.

## 8. Rủi ro và câu hỏi mở

- **Chi phí API**: chỉ họp khi có câu hỏi thật. Cần đo số lần họp mỗi tuần ở giai đoạn A.
- **Dữ liệu một chu kỳ tăng** (E2): mỏ neo và agent đều có thể sai khi vàng giảm dài; phải hạ mức tự tin ở chế độ đó.
- **Agent tự lừa nhau**: giảm bằng vòng 1 độc lập, phản biện bắt buộc, thẩm phán không được đưa lý do mới, và chấm từng agent.
- **Câu hỏi mở cho người dùng**:
  - hội đồng chạy trên demo hay cả VPS cent;
  - mô hình nào cho từng vai;
  - ngân sách API mỗi tháng.
