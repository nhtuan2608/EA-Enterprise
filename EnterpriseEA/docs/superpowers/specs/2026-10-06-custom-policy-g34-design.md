# G34: policy CUSTOM (06/10/2026)

Mục tiêu: dùng EA cho tài khoản không theo luật FTMO (cá nhân hoặc quỹ khác) mà không sửa code: lỗ ngày, lỗ tổng, kiểu sàn và mốc tính ngày do người vận hành đặt, được ký trong policy và phiên live.

## Quyết định của người dùng (06/10)

| Điểm | Chọn |
|---|---|
| Mốc tính lỗ ngày | **Equity lúc reset ngày** (Prague 00:00) |
| Sàn tổng | **FIXED hoặc TRAILING**, mặc định FIXED |

## Thiết kế

Một bộ luật chung `EEA_PolicyRules` (`Risk/PolicyRules.mqh`): `daily_percent`, `overall_percent` (% vốn gốc), `trailing`, `daily_from_equity`. FTMO 1-Step (3/10, trượt, balance), FTMO 2-Step và Balance-based (5/10, cố định, balance) là preset của nó; `CUSTOM` lấy số từ input. Mọi nơi tính sàn (`FtmoHeadroom`, `RiskLimitsProfile`) gọi cùng `EEA_PolicyRulesResolve`, nên không còn số 3/5/10 cứng.

| Input | Mặc định | Ý nghĩa |
|---|---|---|
| `InpCustomDailyLossPercent` | 5 | lỗ ngày tối đa |
| `InpCustomOverallLossPercent` | 10 | lỗ tổng tối đa |
| `InpCustomTrailingFloor` | false | sàn tổng trượt theo đỉnh balance |
| `InpCustomDailyFromEquity` | true | sàn ngày tính từ equity lúc reset |

Hợp lệ khi `0 < daily ≤ overall ≤ 100`; sai thì policy không giải được và EA từ chối lệnh mới (fail closed). Chọn CUSTOM bằng nút **Custom** ở panel (cùng luồng Apply/xác nhận như các policy khác).

**Equity lúc reset.** Lịch sử deal chỉ dựng lại được balance, không dựng lại được equity. Sổ rủi ro lấy mẫu equity (`last_reset_equity`) khi EA thấy reset trong vòng 600 s; nếu không có mẫu (EA tắt lúc reset, hoặc sổ cũ chưa có trường) thì dùng balance lúc reset, không bao giờ dùng 0. Mốc này dùng cho: sàn ngày trong headroom, hạn mức lỗ ngày nội bộ, và kiểm tra lỗ ngày của phiên live.

**Ký.** Phiên live mang `risk_policy_id`. Preset giữ id cũ (phiên cũ vẫn hợp lệ); CUSTOM ký thành `CUSTOM:d=…;o=…;t=…;e=…`, đổi bất kỳ số nào thì phiên mất hiệu lực (`LIVE_SESSION_POLICY_CHANGED`) và phải ký lại.

## Không đổi

Hành vi FTMO 1-Step/2-Step không đổi (test oracle cũ và đối chiếu CUSTOM tương đương FTMO 1-Step). Giờ reset vẫn Prague 00:00; reset theo múi giờ khác chưa hỗ trợ. Rủi ro mỗi lệnh vẫn suy từ luật (nội bộ ≤ 0,4 × lỗ ngày, tối đa 2%).

## Kiểm chứng

`Tests/custom_policy_g34_tests.py` (oracle: sàn cố định/trượt × balance/equity, thiếu equity fail closed, số sai fail closed, CUSTOM tương đương FTMO 1-Step; nguồn MQL: một nơi giải luật, mọi lối ký dùng `EEA_PolicySignedId`, mọi kiểm tra lỗ ngày dùng `EEA_LedgerDailyReference`); compile MetaEditor 0/0; toàn bộ 62 file test đạt.

## Chờ triển khai

Cần nạp lại EA (người dùng quyết định) và, nếu chuyển sang CUSTOM, ký lại phiên live. Ngày đầu sau khi nạp, sổ cũ chưa có mẫu equity nên CUSTOM dùng balance cho tới reset kế tiếp.
