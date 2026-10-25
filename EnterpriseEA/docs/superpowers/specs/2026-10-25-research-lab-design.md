# Phòng nghiên cứu tự động — thiết kế (25/10/2026)

Bổ sung cho [thiết kế bộ não + hội đồng](2026-10-24-ai-brain-council-design.md) và [các agent bước 3a](2026-10-24-council-agents-3a.md).
Làm **sau** bước 3b, khi hội đồng đã có nhật ký vài tuần. Riêng sổ cái và cơ chế khóa giả thuyết có thể dựng sớm.

## 1. Vì sao

Người dùng (25/10) muốn hệ thống tự tính toán, tự so sánh thêm yếu tố để tìm sự lặp lại, theo các hướng:
- chuỗi sự kiện gắn kết từ quá khứ;
- hành vi giá–volume;
- khung giờ và phiên.

Từ đó tự tinh chỉnh ra setup mới, không chỉ dựa vào setup có sẵn.

**Rủi ro chính:** một hệ thống tự ghép yếu tố rồi tự chọn cái tốt nhất chính là máy dò G154, nhưng chạy mãi. G154:
- dò 4.700 tổ hợp, cái tốt nhất chỉ vượt mức may sát ngưỡng;
- khi kiểm kỹ thì thua lệnh ngẫu nhiên và âm trên thị trường khác.

Tự dò rồi tự sửa trên cùng dữ liệu gần như chắc chắn sẽ "tìm ra" setup đẹp nhờ may. Vì vậy phòng nghiên cứu phải **tách khỏi hội đồng
giao dịch** và chạy theo luật cứng.

## 2. Năm luật cứng

1. **AI chỉ đề xuất, máy chấm.** AI không đánh giá giả thuyết của chính nó. Phần kiểm là script cố định.
2. **Chỉ chấm trên dữ liệu chưa nhìn.** Dữ liệu 2010–10/2026 đã bị G1–G157 nhìn gần hết. Một giả thuyết đăng ký lúc T chỉ được chấm trên
   dữ liệu **sau T** (forward), hoặc trên thị trường / loại dữ liệu chưa từng dùng để chọn (khai báo khi đăng ký).
3. **Sổ cái phạt việc thử nhiều.** Mọi phép thử, kể cả thất bại, đều vào sổ. Ngưỡng đạt siết dần theo số phép thử đã làm (mục 5).
4. **Không tự tinh chỉnh bot đang chạy.** Đổi tham số S07, VHedge, CtxLimit... là một giả thuyết mới: đi đủ vòng, người dùng duyệt.
5. **Lên lệnh thật luôn do người dùng quyết.** Giả thuyết đạt chỉ được tự động chạy **ảo**.

## 3. Vòng làm việc (mỗi tuần, cuối tuần khi thị trường đóng)

```
1. ĐỀ XUẤT   AI đọc: nhật ký bot (thật + ảo), phán quyết và bất thường của hội đồng, dữ liệu mới trong tuần, bộ kiến thức
             → tối đa 3 giả thuyết mới / tuần, mỗi cái viết theo khuôn (mục 4)
2. LỌC       máy loại giả thuyết: trùng hoặc là biến thể của một dòng phần C / sổ cái;
             cần dữ liệu không có; không đủ cỡ mẫu ước tính trong 12 tháng
3. ĐĂNG KÝ   giả thuyết còn lại được khóa: file JSON + mã băm SHA-256 + giờ khóa (UTC), commit vào repo
4. THEO DÕI  máy ghi sự kiện của giả thuyết trên dữ liệu forward (như SQZ / W1), không gửi lệnh
5. CHẤM      khi đủ cỡ mẫu đăng ký, hoặc hết hạn: script chấm theo đúng tiêu chí đã khóa
6. KẾT LUẬN  đạt → đề xuất bot ảo cố định (đến bước người dùng duyệt)
             trượt → ghi vào bộ kiến thức phần C; sổ cái ghi "đã tiêu" một lượt
7. BÁO CÁO   người kể (agent 8) tóm tắt trong báo cáo thứ Bảy: giả thuyết mới, đang theo dõi, đã chấm
```

## 4. Khuôn một giả thuyết

```json
{
  "id": "H-2026-11-01-001",
  "khoa_luc_utc": "2026-11-01T02:00:00Z",
  "sha256": "...",
  "nguon_y_tuong": "nhật ký hội đồng 3 tuần: S07 thua sau phiên Á rất hẹp",
  "loai": "loc_bot | setup_moi | quan_ly_lenh | rui_ro",
  "thi_truong": "XAUUSD",
  "khung": "M30",
  "luat_su_kien": "mô tả chính xác, tính được bằng máy từ nến đã đóng",
  "doi_chung": "mô tả nhóm đối chứng (cùng điều kiện trừ yếu tố đang kiểm)",
  "ket_qua_do": "R lệnh (phí harsh) | P(THEO) ± 1 ATR | ...",
  "co_mau_toi_thieu": 60,
  "han_cuoi": "2027-11-01",
  "tieu_chi_dat": "chênh > 0, cận dưới CI (theo mức của sổ cái) > 0, cùng dấu ở các nửa thời gian",
  "du_lieu_kiem": "forward từ khoa_luc_utc | thị trường chưa dùng: ...",
  "kien_thuc_lien_quan": ["A7", "C18"]
}
```

Giả thuyết **không được sửa** sau khi khóa. Muốn đổi thì đăng ký giả thuyết mới, và sổ cái tính thêm một lượt.

## 5. Sổ cái và ngưỡng đạt

- File `research/lab/ledger.jsonl`: mỗi dòng một giả thuyết (id, mã băm, giờ khóa, trạng thái, kết quả).
- **Ngưỡng siết theo số đã thử (alpha-spending):** giả thuyết thứ k được cấp mức sai số α_k = 0,05 × 6 / (π² k²). Tổng mọi α_k không
  vượt 0,05 dù thử bao nhiêu giả thuyết. Ví dụ:
  - giả thuyết thứ 1: α ≈ 0,030;
  - thứ 10: ≈ 0,0003;
  - thứ 30: ≈ 0,00003.

  Hệ quả: những giả thuyết đầu dễ đạt hơn. Vì vậy phải ưu tiên giả thuyết có cơ sở mạnh nhất, không được thử bừa.
- Khoảng tin cậy luôn bằng **bootstrap theo khối tuần**. Với lệnh S07, dùng khối theo **đợt xu hướng** (bài học G155).

## 6. Hướng tìm được phép (và không được phép)

**Được ưu tiên** (thông tin mới hoặc dữ liệu forward):
- hành vi của **chính các bot** trên dữ liệu forward (lệnh thật + ảo): thắng / thua theo trạng thái thị trường;
- **bất thường** mà agent 3 ghi lại: spread, trượt giá, tick;
- **nội dung tin** khi có nguồn;
- tương tác giữa các bot: chạy cùng lúc, cùng chiều, chồng rủi ro;
- quản lý lệnh: kế hoạch có điều kiện của hội đồng so với để bot tự quản (đã chạy ảo, mục 4.4 thiết kế chung).

**Không được đề xuất lại** khi không có dữ liệu mới:
- mọi dòng phần C của bộ kiến thức (C1–C18);
- đoán hướng phá giả / đi tiếp từ bối cảnh giá (G156a2, G157);
- lịch dương và âm lịch (G147, G155);
- máy dò tổ hợp kỹ thuật trên dữ liệu giá cũ (G154).

## 7. Ngân sách AI

Phòng nghiên cứu chạy **một lần mỗi tuần**, cuối tuần. Mỗi lần khoảng 3–5 lượt gọi mô hình (đề xuất, viết khuôn, tóm tắt), tính vào
hạn mức 20 lượt / ngày của ngày đó. Phần lọc, theo dõi và chấm do script chạy, không tốn lượt.

## 8. Phần dựng sớm được

Hai phần nhẹ, không cần AI:
- **sổ cái + khóa giả thuyết**: script tạo id, mã băm, commit;
- **khung theo dõi sự kiện forward**: dùng lại cách SQZ / W1 ghi nhật ký.

Dựng sớm thì những ý tưởng người dùng nêu từ bây giờ (ví dụ "S07 vào ngay trước tin +1,04R", G156c) có thể được khóa ngay, và bắt đầu tính
dữ liệu forward từ hôm nay.

## 9. Kỳ vọng

- Phần lớn giả thuyết sẽ bị từ chối. Đó là dấu hiệu phòng nghiên cứu làm đúng việc.
- Mỗi giả thuyết cần nhiều tháng dữ liệu forward. Đây là cỗ máy **chậm và kỷ luật**, không phải máy in setup.
- Giá trị lớn nhất có thể đến từ những loại dữ liệu hệ thống chưa từng có (nội dung tin, hành vi broker, kết quả forward của chính các
  bot), không đến từ việc khai thác lại giá cũ.
