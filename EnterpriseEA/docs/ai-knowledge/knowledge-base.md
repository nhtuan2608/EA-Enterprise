# Bộ kiến thức nền cho AI phân tích vàng (v1, 24/10/2026)

Đây là phần chắt lọc từ các nghiên cứu G1–G155 (báo cáo trong `docs/superpowers/reports/`). AI dùng nó làm nền khi đọc thị trường mỗi giờ
và khi nhận xét tín hiệu của bot. Ngoài bộ này, AI chỉ được dùng **số liệu trong gói bối cảnh của giờ đó**. Mọi nhận định phải dẫn **mã**
(ví dụ `A5`, `B2`).

**Mức tin cậy:**
- **cao**: kiểm trên dữ liệu chưa nhìn, nhiều giai đoạn;
- **vừa**: đứng vững nhưng có ngoại lệ, hoặc mẫu ngắn;
- **thấp**: quan sát ổn định nhưng chưa qua phép thử quyết định.

Thị trường: XAUUSD, giờ **server** (GMT+2 / +3 theo giờ mùa hè Mỹ), chi phí "harsh" G68 trừ sẵn. **R** = lãi/lỗ tính theo khoảng
stop của lệnh.

---

## Phần A. Điều đã kiểm và đứng vững (được dùng để lập luận)

| Mã | Nội dung | Số liệu | Nguồn | Tin cậy |
|---|---|---|---|---|
| A1 | **S07 có lợi thế thật trên vàng** | 1.208 chân (05/2018–06/2026), +0,34R/chân; theo kỳ +0,11 / +0,29 / +0,57R. Bản Python khớp tester MT5: 83 % lệnh tester có trong sổ, 97 % cùng setup, R lệch trung vị 0,002 | G89, G151, tính lại 24/10 | cao |
| A2 | S07 là lợi thế **riêng của vàng** | Chỉ số Mỹ ≈ 0 (NAS100 +0,03, DJ30 −0,02, SP500 −0,16); BTC mỏng (+0,09, âm sau trừ 0,1R) | MKT01 | cao |
| A3 | Lợi thế S07 nằm ở **pha nén** trước cú bung | M30 nén chặt +0,42–0,54R; nén nới +0,29–0,34; bỏ nén +0,17–0,24 | G81 | cao |
| A4 | Lọc **EMA200 H4** cho lệnh mua S07 có tác dụng thật | M30: giữ +0,35R, bỏ +0,03R (p 0,028); H1 +0,39 vs −0,21. Lệnh bán: không tác dụng | G79 | cao |
| A5 | Lệnh S07 **cùng chiều D1** (SMA50/200) tốt hơn lệnh ngược | Cùng +0,43R vs ngược +0,11R (2018–26). Giảm nửa rủi ro lệnh ngược: DD 32,5 % → 23,9 %, lãi 69 → 67 %/năm | G133, G134, G138, tính lại 24/10 | vừa |
| A6 | **Ngoại lệ của A5**: khi D1 đổi chiều liên tục (như 07/2021–2023), bộ lọc D1 kém vững, lệnh mua ngược D1 có lúc tốt hơn | 2022–23: ngược D1 +0,53R vs cùng +0,12R | G138, tính lại 24/10 | vừa |
| A7 | **Chế độ D1** (giá so với EMA50 + độ dốc EMA50 10 ngày) là tín hiệu môi trường duy nhất lặp lại được | S07 cùng chế độ dương cả 3 kỳ (+0,21 / +0,17 / +0,65R); ngược chế độ âm 2/3 kỳ. Lọc theo chế độ cải thiện 4/7 ứng viên khác | G153 | vừa |
| A8 | Sau khi lệnh S07 đã lời +1R, **đi cùng sóng D1 dễ đi tiếp hơn** | M30: tới +3R 51 % (cùng) vs 42 % (ngược); lệnh ngược quay về giá vào 58–59 % vs 44–49 %. Thoát hiện tại (E2X + TP 8R) gần tối ưu | G135 | cao |
| A9 | **Lệnh bán yếu** ở mọi setup trong 2018–2026 | S07S 30 chân −0,35R; mọi họ bán âm hoặc ≈ 0. Chỉ dương trong năm vàng giảm (2018, 2022, 2023, 2026) | G69–G81, G89, G106, G153 | cao |
| A10 | Kiểu đảo chiều có lợi thế thật **duy nhất**: nến V quay về EMA200 khi thị trường nén (VHedge G119) | M5 05/2024–10/2026: dương 6/6 nửa năm; hơn nến ngẫu nhiên khoảng +0,3U/nhóm; 2026 dương ngoài mẫu | G119, G132, audit | vừa (2,4 năm) |
| A11 | S07 + VHedge chạy chung cho tỷ lệ lãi/sụt tốt nhất (ít đi cùng chiều) | DD chung khoảng 10 % ở 0,75 %/chân VHedge | G120, kiểm lại UTC | vừa |
| A12 | **Scalp chết vì phí** | SL ≤ 0,5 ATR M15 không lọt top 20 trong 4.699 tổ hợp; scalp của mọi setup âm sau phí | G23, G125, G154 | cao |
| A13 | Phí rẻ nhất trong **cửa sổ NY 08–10 giờ New York** | Spread/ATR M5 0,07–0,08 so với 0,14–0,24 ngoài giờ; 3 giờ này chiếm 19,6 % biên độ ngày | G95 F3 | cao |
| A14 | **Tin tức được phản ánh ngay trong nến tin** | Nến M30 chứa tin đi cùng chiều bất ngờ 54–56 %. Sau khi nến đóng, dấu bất ngờ không còn thông tin. Đứng ngoài quanh tin (News Guard) là đúng | G129, FX01 | cao |
| A15 | Hòa vốn trước tin là **đánh đổi theo chế độ** | Xu hướng mạnh (2024–26): bỏ hòa vốn tốt hơn (MAR 13,1 vs 9,2). Đi ngang / giật (2018–23): hòa vốn tốt hơn (0,99 vs 0,84; 3,20 vs 2,42) | G152 | vừa |
| A16 | **Không chặn S07 vì ngày đã chạy xa** | Chân vào khi ngày đã dùng ≥ 0,8 ADR tốt hơn: +0,43 vs +0,10 (train), +0,46 vs +0,38 (validate) | G126 | vừa |
| A17 | Luật "giảm rủi ro khi đang xấu" (theo sụt vốn, chuỗi thua) **chỉ tương đương giảm rủi ro chung** | Giảm DD và giảm lãi gần tỷ lệ nhau; không chọn được lúc xấu tốt hơn một mức rủi ro thấp cố định | G128 | cao |
| A18 | **ATR thấp là vùng xấu** cho mọi setup, nhất là stop hẹp; biến động cao tốt hơn | Ổn định qua các năm trong 21 yếu tố | G147, G148 | vừa |
| A19 | Bám xu hướng (T2) hiệu quả trên **hàng hóa và crypto**, không trên cặp tiền | 4 tài sản mới +0,17R (ngoài mẫu); 8 cặp tiền −0,27R | G41, G43 | vừa |

## Phần B. Tỷ lệ nền (đúng về thống kê, tự nó không thành lợi thế giao dịch)

AI **bắt đầu ước lượng từ đây**, rồi mới điều chỉnh theo bối cảnh có dẫn chứng.

**Tỷ lệ nền chung**

| Mã | Nội dung | Số liệu | Nguồn | Tin cậy |
|---|---|---|---|---|
| B1 | **Hướng giá ngắn hạn gần như ngẫu nhiên** (15 phút – 4 giờ) | Variance ratio 0,94–1,08; sau cú chạy ≥ 1,5–3 ATR, các nến kế đi tiếp 48–51 %. Trạng thái M15 không đoán được nến H1 đang chạy (46–50 %) | G95 F1, G97 | cao |
| B4 | Lệnh trong ngày đã lời +1 ATR: chỉ khoảng **30 %** tới +2 ATR; 70 % quay về giá vào trước | Ổn định 8–9 năm | G149 | cao |
| B5 | Đỉnh/đáy ngày hay hình thành lúc **01:00** và **15–17:00** giờ server | Ổn định 8–9 năm | G149 | cao |

**Mức giá và phá vỡ**

| Mã | Nội dung | Số liệu | Nguồn | Tin cậy |
|---|---|---|---|---|
| B2 | **Phá biên phiên Á rồi bị kéo về** | 80–92 % số lần (ổn định 8–9 năm). Biên Á và biên 30 phút đầu phiên Mỹ "bật" 80–87 %; biên 30 phút đầu phiên Âu bị xuyên nhiều nhất (18–24 %) | G149, G109 | cao |
| B6 | Xác suất **chạm một mức trong ngày chỉ phụ thuộc khoảng cách**, không phụ thuộc loại mức | < 0,25 ATR D1: 80–85 %; 0,5–1 ATR: khoảng 25 %; > 1 ATR: khoảng 5 %. "Mức gần hơn chạm trước" đúng 65–78 % | G109 | cao |
| B7 | **Đỉnh/đáy ngày trước không cho biết hướng** | Phá 27 % ≈ bật 26–28 %. Giá đóng cửa ngày trước giữ giá kém hơn mức giả 15–34 điểm %. 2024–25 đáy giữ nhiều hơn, đỉnh bị phá nhiều hơn (có thể do chu kỳ tăng) | G95 F6, G109 | vừa |
| B8 | **Phá giả hay đi tiếp, tính từ giá hiện tại, gần như tung đồng xu** | ± 1 ATR M30 trong 4 giờ sau khi phá mức: đi tiếp khoảng 51 % (45–54 % theo năm, 48–55 % theo loại mức). Không trường bối cảnh giá nào đoán tốt hơn (AUC 0,50–0,52). AUC 0,70 của G110 / G156b là **hình học** của định nghĩa "giữ được mức" (nến đóng càng xa mức càng dễ "giữ") | G156a2, G156b, G110 | cao |
| B21 | Lệnh S07 **đang lời** đi tiếp +1R trước khi lùi 1R: **61 %** (54–69 % theo năm) | Là lợi thế xu hướng của S07, không phải bối cảnh; chia theo R đang có và D1 không cải thiện chắc chắn | G156a2 | vừa |
| B22 | Cú phá mức trên **BTC H1** đi tiếp khoảng **54 %** (52–59 % mọi năm 2019–2026); FX H1 khoảng 49–51 % | Thiên hướng động lượng nhẹ của BTC; bối cảnh không cải thiện; sau phí ≈ 0, không trade đứng riêng | G157 | vừa |
| B10 | Phiên Mỹ đẩy tiếp thì hôm sau phá cực trị hôm nay cùng chiều **56–68 %**; phiên Mỹ đảo mạnh thì chỉ 0–30 % | Phần lớn là cơ học (giá đã xa cực trị) | G126 | vừa |
| B13 | **Lần phá EMA200 H4 đầu tiên thường bị kéo ngược** | Vào ở nến thứ hai: −0,13 đến −0,54R | G130 | vừa |
| B14 | Trong chu kỳ tăng, "đỉnh cạn đà sau nhiều lần RSI quá mua" **phần lớn chỉ là nhịp nghỉ** | Bán đỉnh 2022–25: −0,05 đến −0,77R | G131c | cao |
| B17 | Sát EMA200 D1 (0–1 ATR D1) là vùng xấu cho lệnh ngẫu nhiên; quét đỉnh/đáy hôm qua rồi quay về là điểm vào tốt hơn | 7/8 ô, chưa qua phép thử quyết định | G148 | thấp |

**VWAP, tin tức và trạng thái chung**

| Mã | Nội dung | Số liệu | Nguồn | Tin cậy |
|---|---|---|---|---|
| B3 | **Giá đã xa VWAP thường chạy tiếp**, ít quay về | Xa ≥ 1,5 ATR: chỉ 25–38 % quay về; đi tiếp 54–71 %. Phiên Mỹ xa ≥ 3 ATR M15: tiếp tục chạy | G149, MKT02 | cao |
| B9 | **Kiểu ngày** (xu hướng hay đi ngang) đoán được một phần lúc 10:00, nhưng chọn setup theo đó không hơn ngẫu nhiên | AUC 0,67 (vàng) | G113 | vừa |
| B11 | Bối cảnh trong ngày tới 15:15 **không dự báo** được phiên New York | Ngày "giống nhau" không có phiên NY giống nhau hơn ngẫu nhiên | G146 | cao |
| B12 | Cú phản ứng tin ≥ 4 ATR trong 15 phút đầu có xu hướng bị kéo lại sau 60–120 phút | 2024–25 −1,7 ATR (n 37, t −1,8); 2021–23 ≈ 0. Chỉ dùng làm luật "đừng đuổi cú tin" | G95 F7 | thấp |
| B18 | Vàng tăng trong khi USD cũng tăng, rồi phá đỉnh thất bại: khả năng có cú giảm ≥ 10 ATR cao hơn 1,3–1,7 lần | Chưa vượt mức may; luật dựng từ đó thua ở kỳ test | G99, G132 | thấp |

**Đặc điểm riêng của lệnh S07**

| Mã | Nội dung | Số liệu | Nguồn | Tin cậy |
|---|---|---|---|---|
| B15 | Gần như mọi lệnh gốc S07 **hồi chạm lại EMA21 M30** | Trung vị sau 5 nến, lúc đó đã lời +0,32R; 97 % chạm EMA55; hồi sâu về EMA100 thì yếu hơn hẳn | G74 | cao |
| B16 | Lệnh mua S07 bị quét SL: **31 %** chạy tiếp ≥ 2R trong 1 ngày | Nhưng luật vào lại không vững (train âm) | G78 | vừa |
| B19 | **Nhãn chất lượng S07 mua** (chưa đủ để đổi rủi ro) | DXY bung xuống cùng lúc: +1,09R/chân (50 chân) vs +0,52; dải EMA xếp thứ tự 21 > 55 > 100: +0,47 vs +0,22 (p 0,10) | G77, G81, G82 | thấp |
| B20 | Biến động **đang nở ra** tương quan dương nhẹ với R của S07; xu hướng **đã chạy xa** tương quan âm | ρ khoảng +0,1; tín hiệu yếu | G83 | thấp |

## Phần C. Đã test và thất bại: không được dùng làm lý do

Nếu lập luận của AI dựa vào một trong các ý dưới đây, câu trả lời bị loại.

| Mã | Ý tưởng | Vì sao loại | Nguồn |
|---|---|---|---|
| C1 | Hiệu ứng lịch: thứ trong tuần, đầu/cuối tháng, âm lịch, sóc/vọng, tiết khí | Không vượt mức may (p 0,59–0,72); đổi dấu theo năm | G147, G155, FX03 |
| C2 | Chấm điểm nhiều yếu tố (EMA, MACD, RSI, ADX, DI, phiên, volume...) | "Yếu tố tốt" của năm này là "yếu tố xấu" của năm khác (147 trạng thái, 50 yếu tố) | G33, G56, G108, G114, G139, G147, G148 |
| C3 | Chuỗi phiên Á–Âu–Mỹ, đánh ngược khi chạm ADR | Âm 9/9 biến thể, không hơn ngẫu nhiên | G126, G127 |
| C4 | Đánh theo số liệu tin sau khi nến tin đóng | Âm, ngang đối chứng | G129, FX01 |
| C5 | Dòng lệnh tick, volume profile, "lực chủ động", "hấp thụ" | Cả 6 tín hiệu âm hoặc ≈ 0 | G121–G123 |
| C6 | Đảo chiều ở vùng / mức / Fibonacci; quét rồi lấy lại | Mức giả cho kết quả như mức thật; mọi bộ âm sau phí | G45, G47, G85, G109, G111 |
| C7 | RSI quá mua/quá bán, cạn đà, đỉnh/đáy RSI | Validate âm ở mọi biến thể | G130, G131 |
| C8 | Setup 5 lớp / hybrid theo cố vấn; squeeze, pullback, nến, mô hình | Không đạt trên dữ liệu chưa nhìn | G136–G139, G140–G144 |
| C9 | Lọc S07 M30 bằng DXY; S07 lấy tín hiệu từ DXY | Làm tệ hơn | G76, G77 |
| C10 | Nới điều kiện S07, vào sớm bằng lệnh Stop, vào lại sau SL | Kém hơn hoặc chỉ tốt trong 2024–26 | G73, G78, G81 |
| C11 | Luật "đừng làm" của lệnh ngẫu nhiên áp cho bot | **S07 và VHedge lại tốt hơn đúng chỗ lệnh ngẫu nhiên tệ** | G150 |
| C12 | Bộ lọc giờ / ngày riêng cho từng bot | Không đạt | G151 |
| C13 | Setup bán riêng (mọi khung, mọi cách giữ) | Âm ở validate | G69–G71, G80, G100–G104 |
| C14 | Ngày "tương tự" trong quá khứ để đoán phiên | Không hơn ngẫu nhiên | G146 |
| C15 | Scalp ghép luật tự động | Lãi chỉ do ăn theo xu hướng D1; âm trên BTC và bạc | G154 |
| C16 | Setup FX (USD dẫn, sức mạnh tiền tệ, động lượng rổ) | Không đạt | FX01–FX03, G90–G93, G124 |
| C17 | Quẻ Kinh Dịch, gieo ngẫu nhiên | Tương đương lệnh vào ngẫu nhiên | G155 (lý do) |
| C18 | Tình huống có tên để đoán hướng: trước / sau tin, tin ra chưa mở phiên Mỹ, quét rồi rút (cùng hay ngược D1), giá chạy volume giảm, vàng và USD cùng chiều, phản ứng ngược kỳ vọng tin, đồng thuận 4 khung, key level hợp lưu, key level test nhiều lần, phá + retest giữ | 48–54 % đi theo, chênh với đối chứng ≤ 3 điểm, mọi CI chứa 0. Chỉ dùng để **cảnh báo / giải thích**. "Quét rồi rút đúng hướng D1" còn hơi kém hơn chỉ theo D1, cùng dấu ở 4 / 5 thị trường (vàng, GBPUSD, USDJPY, BTC). FX và BTC cũng không có tình huống nào trade được | G156c, G157 |

## Phần D. Logic các bot (trạng thái 24/10/2026, demo 1223006)

| Bot | Chế độ | Vào lệnh khi | Thoát / rủi ro | Ghi chú |
|---|---|---|---|---|
| **S07** | LIVE | M30, đủ 5 điều kiện: (1) trong cửa sổ nén có lúc ADX ≤ 20 và |DI+ − DI−| ≤ 6; (2) ADX quay lên, chưa quá 10 điểm từ đáy; (3) DI đúng chiều và đang tách; (4) giá đóng vượt cả EMA21/55/100/200; (5) nến H4 đóng cùng phía EMA200 H4 | E2X + TP 8R; 1,5 % × trọng số; ngược D1 × 0,5; hòa vốn trước tin (mọi tin USD HIGH, lời ≥ 0,3R) | Biến thể (G89, 10/2016–10/2026): S07 +0,31R (336), bồi S07A +0,40R (480), vào sớm S07E +0,48R (186), vào lại S07R +0,19R (129), bán S07S −0,35R (30) |
| **VHedge G119** | LIVE | M5: nến V cắt EMA200 rồi quay lại vùng; EMA21–200 bó sát + volume lớn | 0,75 %/chân; đặt cặp hedge, một chân bị cắt thì giữ chiều còn lại và bồi; TP 5R, hòa vốn ở +1R, đóng hết sau 288 nến M5 (24 giờ) | Cần tài khoản hedging |
| **CtxLimit** | LIVE | Mỗi giờ dự báo R cho mua/bán theo bối cảnh (MKT04); vào limit khi > 0,38R; cổng S07 | 0,5 % × trọng số | Kỳ test +0,31R (77 lệnh) nhưng validate ≈ 0: **phụ thuộc chế độ**; 94 % lệnh mua (audit) |
| **XauRegime (XRT)** | SHADOW | Đầu ngày, chế độ D1 tăng (giá > EMA50, EMA50 dốc lên) | Stop 3 ATR D1, trail 3 ATR; thoát khi chế độ đổi | G96 **chưa đạt luật của nó** (audit) → về SHADOW 24/10 |
| **SQZ** | ảo | Squeeze Bollinger M30 + phá 20 nến + cùng EMA200 M30 + SMA50/200 D1; chỉ tính lệnh cùng chế độ D1 | SL SMA20 ± 0,1 ATR, TP 3R, tối đa 96 nến | G153b forward |
| **W1** | ảo | Thứ Hai–thứ Năm, chạm đầu tiên đỉnh/đáy tuần trước; chỉ tính lệnh cùng chế độ D1 | SL giữa biên tuần, thoát thứ Sáu 21:30 | G153b forward |

Lớp bảo vệ chung (không phải đọc thị trường): giới hạn lỗ ngày 6 %, rủi ro mở ≤ 12 %, phiên live ký 7 ngày, kill switch, News Guard.

## Phần E. Giới hạn của dữ liệu và các bẫy đã gặp

| Mã | Nội dung | Nguồn |
|---|---|---|
| E1 | Dữ liệu trong ngày thật chỉ có từ **03/2018** (trước đó file M30/H1 là nến D1); M15 từ 07/2021; M5 từ 05/2024 | intraday-data, G140 |
| E2 | Gần như toàn bộ dữ liệu trong ngày nằm trong **một chu kỳ vàng tăng**. S07 trên D1 âm ở 2011–2017. Kinh nghiệm cho thị trường giảm hoặc đi ngang nhiều năm **rất ít** → hạ mức tự tin khi D1 giảm kéo dài | audit, G140–G144 |
| E3 | Lệnh S07 **đi theo cụm**: 1.208 chân chỉ khoảng 200 đợt. Một ô có t = −4 vẫn có thể là may (G155). Đừng tin một tỷ lệ tính trên vài chục chân | G155 |
| E4 | Nhiều "lợi thế" phụ thuộc **vài lệnh cực lớn**; luôn xem kết quả khi bỏ 1–2 lệnh lớn nhất | G140–G144 |
| E5 | Bẫy nhìn trước: cửa sổ nến trượt của terminal, lẫn giờ UTC với giờ server, nến khớp limit | G108, G125, G113 |
| E6 | Nến D1 khác nhau giữa broker (5 hay 6 nến/tuần) làm lệch SMA50/200 khoảng 16 % | G138 |
| E7 | Giai đoạn **07/2021–2023** (D1 đổi chiều 7 lần) là nơi nhiều bộ lọc đổi dấu | G138, G153 |
| E8 | AI **không backtest được** (mô hình đã thấy lịch sử giá); mọi đánh giá AI phải **forward** | thiết kế G156 |

---

## Quy tắc dùng (tóm tắt; bản đầy đủ ở bước 3)

1. Bắt đầu từ tỷ lệ nền ở phần B, rồi điều chỉnh. Mỗi điều chỉnh phải dẫn mã A/B hoặc số trong gói bối cảnh.
2. Lý do thuộc phần C thì bị loại.
3. Tình huống thuộc E2 (D1 giảm kéo dài) hoặc biến động chưa từng thấy thì hạ mức tự tin và nói rõ.
4. Không nhắc lại "đừng làm" của lệnh ngẫu nhiên cho tín hiệu S07 / VHedge (C11).
5. Với tín hiệu bot, AI chỉ được chọn: **đồng ý / giảm rủi ro / bỏ lệnh**. Không bao giờ tự mở lệnh.

Cập nhật: mỗi khi có G mới; các tỷ lệ phần B sẽ được script tính lại từ dữ liệu (bước 2).
