# G136: năm hướng nâng cấp / tạo setup sau G126–G135 — kế hoạch đăng ký trước (21/10/2026)

## Vì sao

Người dùng hỏi nên mở rộng theo hướng nào: indicator, Wyckoff, mô hình nến/hình (morning star, wedge, kênh song song), SMC/ICT, VSA, chấm điểm đa yếu tố. Đối chiếu với G23–G135 cho thấy phần lớn các hướng đó **đã thử và không đạt**:

| Hướng | Đã thử | Kết quả |
|---|---|---|
| SMC/ICT: order block, FVG, quét + CHoCH, Fib OTE, hai đỉnh/đáy | G45, G47 | không đạt; OB + BOS và OTE mất hết sau chi phí ×2 |
| Quét thanh khoản, sweep–reclaim, phá đỉnh thất bại | G85, G126, G132 | âm hoặc ≈ 0; G132-C âm ở kỳ test |
| RSI quá mua/bán, phân kỳ, đỉnh cạn đà | G45, G130, G131 | 2022–2025 âm ở mọi biến thể |
| Hồi về EMA20 / SMA50, scalp EMA5/10/20 | G74, G75, G133 | khung nhỏ âm; H4 SMA50 không hơn ngẫu nhiên |
| Mô hình nến (nhấn chìm, nền → bung) | G86 phần C, G56 | +0,08R/lệnh, không thắng ngẫu nhiên |
| Wedge, sideway, giờ, giá tròn | G56 | walk-forward −0,04R |
| Volume, VSA, volume profile, dòng lệnh từ tick | G110, G121 | không phân biệt được; vàng spot chỉ có tick volume |
| Tin, ADR, chuỗi phiên | G126, G129, MKT02 | không đạt |
| Chấm điểm đa yếu tố, xác suất / EV | G33, G83, G108, G114 | điểm chọn lệnh "êm", không tăng EV; kỳ test sụp |

Lợi thế đã chứng minh đều là **đà sau nén có bối cảnh khung lớn** (S07, T2, S06B lọc USD) và một kiểu đảo chiều duy nhất: **nến V quay về EMA200 khi thị trường nén** (VHedge G119 M5; nến V M30 ở G118/G134). G134/G135 thêm: lệnh cùng trạng thái golden/death cross D1 tốt hơn rõ, lệnh ngược thua.

Vì vậy G136 **không dựng họ setup mới từ đầu**. Năm hướng dưới đây hoặc mở rộng lợi thế đã có (P1–P3), hoặc thử ý tưởng mới dưới dạng **nhãn trên sổ lệnh có sẵn** (P4–P5), là cách rẻ và khó overfit nhất.

## Quy ước chung (áp cho P1–P5)

- **Dữ liệu**: dữ liệu nghiên cứu như G67/G89/G119 (`research/long/data/...`), XAUUSD, giờ server. M15 chỉ có từ 07/2021, M5 từ khoảng 2024.
- **Kỳ**:

| Kỳ | Khoảng | Dùng để |
|---|---|---|
| sớm | 2018-01 → 2021-06 | chỉ báo cáo (M30/H1/H4) |
| train | 2021-07 → 2023-12 | chọn |
| validate | 2024-01 → 2025-06 | chọn |
| test | 2025-07 → 2026-06 | xác nhận; **không còn kín** (đã dùng ở G105–G135), ghi rõ như vậy |
| forward | từ 21/10/2026 | xác nhận cuối trước khi LIVE |

- **Chi phí**: như G135: spread vào/ra (lệnh bán đóng ở giá ask) + trượt 0,5 × spread trung vị mỗi chiều + phí G67/G68. Báo thêm bản chi phí × 1,5.
- **Đối chứng**: vào ngẫu nhiên cùng số lệnh, cùng chiều, cùng khung giờ, cùng cách thoát (200 lần); báo p.
- **Nhiều phép thử**: P1–P5 có tổng cộng 10 ô quyết định (đếm ở từng mục). Ngưỡng p cho một ô là 0,05 / 10 = 0,005.
- **Mô phỏng vốn** (khi tiêu chí cần MAR/DD): như G128/G134: vốn 10.000, 1,5% × trọng số EA, lãi kép; DD p90 một năm từ cửa sổ trượt.
- **Không chỉnh luật sau khi chạy.** Nếu phát hiện lỗi dữ liệu hay nhìn trước (như G108), sửa, chạy lại toàn bộ và ghi rõ trong báo cáo.
- **Đường vào EA**: ô nào đạt thì vào EA **mặc định tắt hoặc SHADOW**, chờ người dùng đồng ý và forward ≥ 30 lệnh (hoặc ≥ 2 tháng), rồi đối chiếu bằng `Tests/live_vs_research.py` sau khi LIVE.

## P1. S07 H1 chỉ cùng sóng D1, rủi ro thấp, không chồng M30

**Nguồn**: G134 (S07 H1 dương mọi kỳ, nhưng 50% trùng M30; chạy chung 1,5% làm DD tăng mạnh), G135 (H1 cùng sóng +0,11 / +0,55 / +0,65R).

**Luật**: S07 H1 theo G135 (cửa sổ nén 4 nến, nghỉ 2, giữ tối đa 120, B6, E2X + TP 8R), cộng:
- trạng thái SMA50/SMA200 D1 đã đóng **cùng chiều** lệnh (chưa rõ → không vào);
- **không có chân S07 M30 cùng chiều đang mở** tại lúc vào (dùng sổ G89 M30);
- chỉ chiều mua; chiều bán báo cáo riêng, không quyết định.

**Biến thể rủi ro** (ô quyết định: 2): H1 ở 0,5% và 0,75%; M30 giữ 1,5% với trọng số D1 × 0,5 của G134.

**Đạt khi** (một biến thể, chọn mức rủi ro thấp hơn nếu cả hai đạt):
- R/lệnh của riêng H1 > 0 ở train, validate và test, ≥ 40 lệnh mỗi kỳ, thắng ngẫu nhiên (p ≤ 0,005 gộp train + validate);
- danh mục M30 + H1 có MAR ≥ M30 một mình ở train, validate và test;
- DD p90 một năm của danh mục không vượt M30 một mình quá 3 điểm %.

## P2. Họ lệnh bán S07 chỉ chạy khi D1 đang death cross

**Nguồn**: G69/G71/G80/G81 (bán chưa có lợi thế ở khung nào), G88 (S07S/S07ES/S07RS/S07AS để SHADOW mặc định), G135 (lệnh ngược sóng D1 âm ở M30/H1).

**Sổ**: luật bán của EA: S07S (gốc, vị trí L2), S07ES (sớm), S07RS (vào lại), S07AS (bồi M15/H1/H4), như `S07Tester.mq5` / sổ G89.

**Biến thể** (ô quyết định: 1, là DX):

| Mã | Lệnh bán khi D1 golden cross |
|---|---|
| D0 | giữ như hiện tại (gốc) |
| DX | bỏ (chỉ bán khi D1 death cross) |
| DS | bỏ khỏi sổ thật, ghi SHADOW (về số liệu giống DX) |

**Đạt khi** (DX):
- sổ bán sau lọc dương ở train **và** validate, ≥ 60 lệnh mỗi kỳ, test không âm;
- R/lệnh cao hơn D0 ở cả ba kỳ;
- thắng ngẫu nhiên cùng chế độ D1 (chỉ lấy ngày death cross) với p ≤ 0,005.

Nếu không đạt: báo cáo DS như **khuyến nghị vận hành** (chuyển bán ngược D1 sang SHADOW để đỡ lỗ), không phải setup mới. Tách riêng phần S07AS đứng độc lập (`InpS07AsStandalone`, có từ 20/10, chưa có nghiên cứu): báo số lệnh và R của nó trên cùng sổ, không quyết định.

### Sửa đổi P2 (21/10/2026, ghi trước khi chạy P2)

**Lý do**: kiểm tra khả thi ([báo cáo sơ bộ](../reports/2026-10-21-g136-prelim-h1-vps.md)) cho thấy validate (01/2024–06/2025) **không có ngày D1 death cross nào** và test chỉ có 2 ngày. Luật đạt ở trên (dương ở train **và** validate, ≥ 60 lệnh mỗi kỳ) vì thế không bao giờ thỏa, bất kể setup tốt hay xấu. Người dùng chọn cách sửa sau; luật này **thay** phần "Đạt khi" của DX ở trên. Ô quyết định vẫn là 1.

**Chia lại dữ liệu cho P2**:

| Phần | Khoảng | Dùng để |
|---|---|---|
| chọn | mọi ngày D1 death cross từ 01/2018 đến 12/2023, gộp lại | quyết định |
| nửa đầu / nửa sau | ngày death cross trước / từ 07/2021 | kiểm tra ổn định |
| golden 2018–2026 | mọi ngày D1 golden cross | chỉ báo cáo (phần DX bỏ đi, căn cứ cho DS) |
| forward | từ 26/06/2026 (death cross hiện tại) | xác nhận |

**Lưu ý về forward**: kết quả lệnh bán S07 H1 từ 07/2026 (20 lệnh, −0,384R) **đã được xem** trong báo cáo sơ bộ H1. Phần 26/06–20/10/2026 vì thế không còn kín cho H1; phần forward kín bắt đầu từ **21/10/2026**. Báo cáo ghi riêng hai phần.

**DX đạt khi**:
- phần chọn: R/lệnh > 0, ≥ 60 lệnh, R/lệnh cao hơn D0 (mọi lệnh bán cùng khoảng 01/2018–12/2023);
- cả nửa đầu và nửa sau đều không âm;
- thắng ngẫu nhiên chỉ trong ngày death cross: p ≤ 0,005 (200 lần như quy ước chung);
- vẫn dương khi chi phí × 1,5;
- forward: ≥ 30 lệnh (hoặc ≥ 2 tháng) từ 26/06/2026 với R/lệnh > 0, **và** phần kín từ 21/10/2026 không âm sau ≥ 30 lệnh. Trước khi đủ forward, DX chỉ được để SHADOW.

**Bản sơ bộ trên VPS** (khác nguồn dữ liệu, không dùng để quyết định): không có sổ M30 của các luật bán EA, nên chạy S07 bán của G67 (B6, E2X, TP 8) trên H1 (nén 4, nghỉ 2, giữ 120 như G135) và H4 (nén 8, nghỉ 4, giữ 240 như G81/G83), nến Lirunex từ 09/2019.

## P3. Họ VHedge sang M15 / M30 với tín hiệu morning / evening star

**Nguồn**: G116–G119 (nến V quay về EMA200 khi nén, M5), G118 ứng viên A và G134 (nến V M30 +0,42U, dương 9/9 năm, chưa có nhóm forward), G86 (mô hình nến đứng riêng không đủ). Ý tưởng: đưa mô hình nến đảo chiều vào **đúng bối cảnh duy nhất từng thắng**.

**Bối cảnh** (giữ nguyên G118 A): EMA21/55/100 xòe ngược chiều tín hiệu, ADX < 25, dốc EMA200 ngược chiều tín hiệu, giá chạm hoặc cắt EMA200 trong 3 nến trước tín hiệu.

**Tín hiệu** (ô quyết định: 2, M15 và M30):

| Mã | Tín hiệu |
|---|---|
| V | nến V như G118 A (đối chứng) |
| MS | morning star (mua) / evening star (bán): nến 1 thân ≥ 0,6 ATR ngược chiều lệnh; nến 2 thân ≤ 0,3 ATR; nến 3 thân ≥ 0,5 ATR cùng chiều lệnh, đóng vượt 50% thân nến 1 |
| V∪MS | lấy cả hai, một nhóm cho mỗi lần chạm EMA200 |

**Quản lý**: hedge và stop ± 2 ATR như G116/G118 (đơn vị U), giữ nguyên.

**Đạt khi** (MS hoặc V∪MS, từng khung):
- MS dương ở train, validate và test, ≥ 30 nhóm mỗi kỳ, thắng ngẫu nhiên p ≤ 0,005;
- V∪MS có tổng U cao hơn V ở cả ba kỳ và U/nhóm không thấp hơn V quá 0,05U (tức MS **thêm** lệnh mà không làm loãng).

## P4. Wyckoff spring / upthrust làm nhãn trên lệnh S07

**Nguồn**: G85 (quét đáy đứng riêng không đạt), G126 (ngày đã dùng ADR lớn thì S07 tốt hơn). Không dựng engine Wyckoff đầy đủ: các pha A–E có nhiều cách hiểu và không đo được volume thật. Chỉ thử phần đo được nhất, **trong cửa sổ nén mà S07 đã dùng**.

**Nhãn** (tại nến tín hiệu S07 M30 và H1):
- **spring** (cho lệnh mua): trong cửa sổ nén (M30: 8 nến, H1: 4 nến), có ít nhất một nến có đáy thấp hơn đáy của phần cửa sổ trước nó ≥ 0,3 ATR **và** đóng lại phía trên đáy đó;
- **upthrust** (cho lệnh bán): đối xứng;
- không có → nhãn trống.

**So sánh** (ô quyết định: 2, mua M30 và mua H1; bán chỉ báo cáo): R/lệnh có nhãn so với không nhãn, trên sổ G89 (M30) và sổ P1 (H1), kiểm định hoán vị nhãn.

**Đạt khi**: có nhãn tốt hơn không nhãn ở train, validate và test, chênh ≥ 0,15R mỗi kỳ, ≥ 25 lệnh có nhãn mỗi kỳ, p ≤ 0,005. Nếu đạt, dùng làm **trọng số rủi ro** (ví dụ lệnh không nhãn × 0,67 như G87) và mô phỏng lại sổ (MAR, DD theo kỳ); không dùng để chặn lệnh.

## P5. Phá kênh hồi (flag / kênh song song) làm điểm bồi cho S07A

**Nguồn**: G70 (bồi khung khác có ích ở sổ mua), G74/G75 (bồi khi hồi EMA21/EMA55 không hơn A1), G101–G103 (giữ theo cấu trúc/hộp nghỉ có ích).

**Định nghĩa kênh hồi** (sau khi lệnh gốc S07 M30 mua đã đạt +1R): trên M15, từ đỉnh cao nhất sau khi vào lệnh, dựng hồi quy tuyến tính của giá đóng trên ≥ 6 nến:
- độ dốc âm (ngược chiều lệnh), R² ≥ 0,6;
- độ sâu hồi ≤ 0,618 của nhịp từ giá vào tới đỉnh;
- **điểm bồi**: nến M15 đầu tiên đóng trên đường biên trên của kênh (biên = đường hồi quy + 1 độ lệch chuẩn phần dư); SL dưới đáy kênh − 0,1 ATR (1–4 ATR như S07).

**So sánh** (ô quyết định: 3): A1 (bồi theo tín hiệu S07 khung khác, hiện tại), C1 (thay A1 bằng phá kênh), C2 (A1 + phá kênh, tối đa 2 lần bồi và 3 lệnh mở như G72).

**Đạt khi** (C1 hoặc C2):
- tổng R mỗi lệnh gốc cao hơn A1 ở train, validate và test;
- DD p90 một năm không cao hơn A1;
- giữ nguyên khi chi phí × 1,5.

## Không làm trong G136 (đã có kết quả)

Chấm điểm đa yếu tố 0–100; VSA / volume > trung bình / volume profile; SMC/ICT tổng hợp (OB, FVG, CHoCH, OTE); RSI quá mua/bán và phân kỳ; mean reversion; Elliott Wave; Harmonic. Lý do ở bảng đầu kế hoạch. Muốn mở lại hướng nào phải có kế hoạch riêng nêu rõ điểm khác với lần thử trước.

## Thứ tự và đầu ra

1. P1 và P2 trước: dùng lại sổ G89/G135, ít code, khả năng đạt cao nhất.
2. P3: cần dựng mô hình nến trên M15/M30 và chạy lại khung G118.
3. P4, P5: nhãn trên sổ có sẵn.

Script: `research/long/g136_extensions.py` (một hàm cho mỗi mục, đọc dữ liệu một lần). Báo cáo: `docs/superpowers/reports/2026-10-xx-g136-setup-extensions.md` với một mục cho mỗi P, mỗi mục có bảng theo kỳ, đối chứng ngẫu nhiên, chi phí × 1,5 và dòng **Kết luận theo luật: ĐẠT / KHÔNG ĐẠT**.
