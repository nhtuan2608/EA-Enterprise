# G42: rủi ro mỗi lệnh cho vòng thi (06/10/2026)

Hoàn tất phần "input rủi ro cho vòng thi" còn thiếu của G32.

## Quyết định của người dùng

Mặc định **1,5%/lệnh** cho vòng thi; trần cứng **1,5%**.

## Input

| Input | Mặc định | Ý nghĩa |
|---|---|---|
| `InpAccountPhase` | `PHASE_EVALUATION` | `EVALUATION` dùng `InpEvalRiskPercent`; `FUNDED` quay về mức tự suy ra từ policy (0,5% với 2-Step, 0,3% với 1-Step) |
| `InpEvalRiskPercent` | 1,5 | rủi ro mỗi lệnh (% vốn gốc); 0 = tự suy ra; trên 1,5 bị cắt về 1,5 |

Khi được cấp vốn, đặt `InpAccountPhase=PHASE_FUNDED`: nghiên cứu G32 cho thấy từ 1% trở lên năm tệ nhất sát sàn −10%.

## Các hạn mức đi theo

Cùng tỷ lệ với bộ tự suy ra (mở 4×, ngày 4×, tuần 8× rủi ro một lệnh) quanh mức yêu cầu `p`, với hai chặn:

- ngày nội bộ ≤ 80% lỗ ngày của policy; tuần ≤ 80% lỗ tổng; một lệnh ≤ nửa hạn mức ngày nội bộ;
- đệm an toàn = `p`, phơi nhiễm một đồng tiền = 2,5 × `p`.

| Policy | Rủi ro/lệnh | Mở | Ngày | Tuần |
|---|---|---|---|---|
| 2-Step @1,5% | 1,5% | 4% | 4% | 8% |
| 1-Step @1,5% | 1,2% (bị cắt bởi ngày 2,4%) | 2,4% | 2,4% | 4,8% |
| 2-Step không override | 0,5% | 2% | 2% | 4% |

Headroom FTMO (sàn ngày/tổng + đệm), News Guard, phân xử setup và Trade Manager vẫn áp dụng như cũ; override chỉ đổi con số nền.

## Phiên live

Phiên đã ký chỉ có thể hạ rủi ro (`EEA_ControlledLiveApplySessionCap`). Phiên hiện tại ký 0,3%/lệnh nên rủi ro thật vẫn bị giữ 0,3% cho tới khi người dùng ký lại phiên (khi đó trần phiên mới là 1,5% hoặc 1,2%). Giới hạn của kho phiên (≤ 2%/lệnh, ≤ 5%/ngày) được tôn trọng.

## Kiểm chứng

`Tests/eval_risk_g42_tests.py` (bản đối chiếu Python của công thức: không override giữ nguyên bộ cũ, override bằng giá trị suy ra không đổi gì, 2-Step 1,5%, 1-Step bị cắt, mọi yêu cầu từ 0,1% đến 100% vẫn trong trần, CUSTOM với lỗ ngày nhỏ; kiểm nguồn MQL và giá trị mặc định); compile 0/0; toàn bộ test đạt.

## Lưu ý vận hành

Mặc định mới nâng rủi ro tiềm năng gấp 3 so với 0,5% khi nạp lại EA và ký lại phiên. Khuyến nghị G32 vẫn là chỉ nâng sau 2–4 tuần shadow S06B khớp nghiên cứu; có thể đặt `InpEvalRiskPercent=0` hoặc `PHASE_FUNDED` để giữ mức cũ.
