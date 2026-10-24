# G156c — thư viện tình huống, đa khung, key level: không tình huống nào báo trước hướng (24/10/2026)

Kế hoạch: [2026-10-24-g156c-situation-library.md](../plans/2026-10-24-g156c-situation-library.md) (commit `25f9434`). Script
[`g156c_situations.py`](../../research/long/g156c_situations.py), kết quả `research/long/results/g156c/summary.json`.

Kết quả đo: từ giá đóng lúc tình huống xảy ra, giá đi **theo** chiều tình huống 1 ATR M30 trước hay đi **ngược** 1 ATR trước, trong 4 giờ.
P = tỷ lệ "theo" trong các lần đã phân định. Gộp 05/2018–06/2026. Khoảng tin cậy 99,6 % (Bonferroni 12 tình huống), bootstrap khối tuần.

## Kết quả

| Tình huống | Số lần | P tình huống | P đối chứng | Chênh | CI 99,6 % | Chênh theo kỳ (2018–21 / 22–23 / 24–26) | Phân loại |
|---|---|---|---|---|---|---|---|
| T1 trước tin | 1.922 | 50,1 % | 49,5 % | +0,6 | [−3,1; +4,1] | +0,8 / +1,3 / −0,3 | cảnh báo |
| T2 nến tin | 1.771 | 50,6 % | 50,1 % | +0,5 | [−2,7; +4,0] | −0,5 / +0,1 / +2,2 | cảnh báo |
| T3 tin đã ra, chưa mở phiên Mỹ | 771 | 48,9 % | 50,0 % | −1,1 | [−7,0; +5,2] | −2,7 / −8,2 / +7,1 | cảnh báo |
| T4 quét rồi rút **cùng** chiều D1 | 2.684 | 48,5 % | 51,2 % | **−2,7** | [−5,4; +0,1] | −3,2 / −2,2 / −2,3 | cảnh báo |
| T5 quét rồi rút **ngược** D1 | 2.937 | 50,7 % | 48,8 % | +1,9 | [−0,6; +4,4] | +3,5 / −0,3 / +1,4 | cảnh báo |
| T6 giá chạy mà volume giảm | 3.999 | 50,3 % | 50,9 % | −0,7 | [−3,0; +1,8] | −1,2 / +1,2 / −1,4 | cảnh báo |
| T7 vàng và USD cùng chiều | 1.738 | 51,9 % | 50,2 % | +1,7 | [−2,0; +5,0] | — / +2,4 / +0,8 | cảnh báo |
| T8 phản ứng ngược kỳ vọng tin | 371 | 47,7 % | 50,8 % | −3,1 | [−11,9; +7,7] | −5,7 / −1,4 / −1,6 | cảnh báo |
| T9 đồng thuận 4 khung | 1.952 | 50,8 % | 49,4 % | +1,4 | [−2,9; +5,6] | +2,0 / +2,4 / −0,2 | cảnh báo |
| T10 key level hợp lưu | 2.949 | 50,9 % | 50,4 % | +0,6 | [−1,7; +2,9] | −1,1 / +1,2 / +2,5 | cảnh báo |
| T11 key level đã test ≥ 3 lần | 1.762 | 50,6 % | 49,7 % | +0,9 | [−2,5; +4,5] | +0,2 / +1,6 / +1,3 | cảnh báo |
| T12 phá + retest giữ | 885 | 53,8 % | 53,3 % | +0,5 | [−4,0; +5,9] | −3,2 / +4,1 / +2,6 | cảnh báo |

(Chênh tính bằng điểm %.)

**Không tình huống nào có giá trị dự báo.** Mọi tỷ lệ nằm trong khoảng 48–54 %, chênh so với đối chứng ≤ 3 điểm %, và mọi khoảng tin cậy
chứa 0.

## Đáng chú ý

- **T4 "quét rồi rút đúng hướng D1" còn hơi kém** so với việc chỉ đi theo D1 (−2,7 điểm, âm ở cả 3 kỳ, khoảng tin cậy chạm sát 0). Trực
  giác "bẫy ngược rồi chạy đúng hướng" không đứng trên dữ liệu vàng 2018–2026. Khớp G85.
- **Đa khung (T9) và key level (T10–T12) không thay đổi kết quả** sau cú phá. Khớp G109: loại mức không quan trọng.
- **Tin tức (T1–T3, T8)**: sau tin, hướng tiếp theo vẫn là tung đồng xu. Khớp A14: tin đã được phản ánh trong nến tin.

## Chỉ báo cáo, không quyết định: lệnh gốc S07 trùng tình huống

R trung bình lệnh gốc S07 (toàn bộ: 702 lệnh, +0,32R):

| Tình huống | Lệnh S07 trùng | R TB |
|---|---|---|
| T1 trước tin | 78 | **+1,04** |
| T11 key level đã test nhiều lần | 64 | +0,82 |
| T4 quét cùng D1 | 60 | +0,77 |
| T3 tin đã ra, chưa mở Mỹ | 30 | +0,61 |
| T9 đồng thuận đa khung | 133 | +0,52 |
| T12 phá + retest | 4 | −0,37 |

Đây **không** phải phát hiện:
- mỗi nhóm chỉ 4–133 lệnh, và lệnh S07 đi theo cụm (bài học G155);
- có 12 nhóm được nhìn cùng lúc;
- G156b không tìm được bối cảnh nào xếp hạng được lệnh S07.

Riêng "S07 vào lệnh ngay trước tin" (+1,04R) có thể ghi làm **giả thuyết forward**: nhãn trong nhật ký, không đổi luật.

## Kết luận và hệ quả cho bước 3a

1. Với thông tin giá, nhận diện tình huống (kể cả đa khung và key level) **không cải thiện** dự báo hướng so với tung đồng xu. Hội đồng
   **không được dùng** các tình huống này để đoán hướng.
2. Các tình huống vẫn có ích ở vai **cảnh báo và giải thích**: "đang trước CPI, spread có thể nổ", "vừa quét đáy ngày trước", "4 khung
   đang cùng chiều". Có điều kiện: luôn kèm câu "tình huống này không báo trước hướng (G156c)".
3. Bộ kiến thức thêm dòng C18 (tình huống có tên không báo trước hướng).
4. Cùng G156a2 / G156b: giá trị duy nhất hội đồng AI có thể thêm vào phải đến từ **thông tin ngoài giá**:
   - nội dung tin;
   - bất thường thực thi / broker;
   - bot lệch dấu vân tay;
   - giải thích.

   Bước 3a nên thiết kế agent theo các mảng này.
