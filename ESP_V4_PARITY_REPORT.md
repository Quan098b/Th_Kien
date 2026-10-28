# ESP32-S3 deployment 4 parity report

Ngày kiểm thử: 2026-10-22. Thiết bị: ESP32-S3 N16R8, COM15, MAC `80:b5:4e:e9:4f:c4`.

## Kết luận

Deployment 4 trên ESP và Windows cho cùng nhãn **20/20** WAV Tat_Den và cùng vector xác suất INT8; sai khác lớn nhất do định dạng CSV sáu chữ số là `0.000000500` (trung bình `0.000000241`). ESP nhận đúng **18/20 (90%)**, đúng bằng laptop; deployment 3 trước đó nhận đúng **0/20 (0%)**. Vì vậy chênh lệch 0/20 so với 18/20 xuất phát từ deployment/model version, không phải đường PCM Serial hay DSP trên ESP.

Hai lỗi Tat_Den còn lại cũng giống hệt laptop: một mẫu hòa Bat_Den/Tat_Den ở 0.4921875 và một mẫu nghiêng Bat_Den 0.51171875 so với Tat_Den 0.40234375. TTS Tat_Den vẫn bị nhận Bat_Den; đây là hành vi của model deployment 4, không được che bằng ngưỡng hay logic thủ công.

## Xác minh artifact và cấu hình

- Project `VuDieuAnhSang`, project ID `1144745`, deployment `4`.
- Nhãn/tensor output: `Bat_Den`, `Tap_Am`, `Tat_Den`, `Unknown`.
- Input PCM16 mono 16 kHz, 24.000 mẫu; MFE output 5.960 phần tử; TFLite INT8 (`quantized=1`, `compiled=0`).
- SHA-256 model `.tflite`: `A9B5C89E841E9546A4048A0D11BA2C7EF1153C0168BEC5BCC55AF50A20F20E6D`.
- SHA-256 firmware deployment 4: `1FF24A415428F803791656BBB6A503AFFB70BA3C42FB686D7079DC5B53EC7259`.
- Bản sao flash deployment 3 (16 MiB): `988E0F24E9E2A2466B8BC3C67251ACAA9B8B50B537AEBC458B5C1136D8092B03`; lệnh khôi phục nằm trong `firmware_history/deployment3_restore_20261022/RESTORE.md`.
- Tất cả 20 lượt truyền có CRC32 trùng bộ kiểm thử deployment 3; firmware báo CRC hợp lệ trước suy luận.

## Confusion matrix — ESP deployment 4

| Thực tế \ Dự đoán | Bat_Den | Tap_Am | Tat_Den | Unknown |
|---|---:|---:|---:|---:|
| Bat_Den | 0 | 0 | 0 | 0 |
| Tap_Am | 0 | 0 | 0 | 0 |
| Tat_Den | 2 | 0 | 18 | 0 |
| Unknown | 0 | 0 | 0 | 0 |

Chỉ lớp Tat_Den có dữ liệu trong bộ 20 WAV này. Tat_Den → Bat_Den: **2/20 = 10%**; recall Tat_Den: **18/20 = 90%**. Không suy diễn precision/recall cho ba lớp không có mẫu thật trong tập này.

## So sánh từng WAV

| WAV | ESP v3 | Laptop v4 | ESP v4 | Bat Δ | Tap Δ | Tat Δ | Unknown Δ |
|---|---|---|---|---:|---:|---:|---:|
| Tat_Den_20261021_215439_245839.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000250 | 0.000000250 | 0.000000250 |
| Tat_Den_20261021_215044_824656.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000000 | 0.000000250 | 0.000000250 |
| Tat_Den_20261021_215310_123139.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000500 | 0.000000250 | 0.000000500 |
| Tat_Den_20261021_214924_424200.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000000 | 0.000000000 | 0.000000500 |
| Tat_Den_20261021_230628_317894.wav | Bat_Den | Bat_Den | Bat_Den | 0.000000500 | 0.000000250 | 0.000000500 | 0.000000500 |
| Tat_Den_20261021_214812_315519.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000500 | 0.000000000 | 0.000000000 | 0.000000500 |
| Tat_Den_20261021_214644_966730.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000000 | 0.000000250 | 0.000000000 | 0.000000250 |
| Tat_Den_20261021_230708_630365.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000250 | 0.000000250 | 0.000000250 |
| Tat_Den_20261021_230609_200512.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000500 | 0.000000000 | 0.000000250 |
| Tat_Den_20261021_214904_602165.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000000 | 0.000000000 | 0.000000500 |
| Tat_Den_20261021_214838_809565.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000000 | 0.000000000 | 0.000000000 |
| Tat_Den_20261021_214902_759356.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000000 | 0.000000000 | 0.000000500 |
| Tat_Den_20261021_214540_648363.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000000 | 0.000000250 | 0.000000500 | 0.000000250 |
| Tat_Den_20261021_223144_213761.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000500 | 0.000000000 | 0.000000000 | 0.000000500 |
| Tat_Den_20261021_230611_327779.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000500 | 0.000000250 | 0.000000250 | 0.000000000 |
| Tat_Den_20261021_215228_555390.wav | Bat_Den | Bat_Den | Bat_Den | 0.000000250 | 0.000000500 | 0.000000250 | 0.000000250 |
| Tat_Den_20261021_214750_727109.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000000 | 0.000000250 | 0.000000500 |
| Tat_Den_20261021_214650_342274.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000250 | 0.000000250 | 0.000000500 |
| Tat_Den_20261021_214823_869835.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000500 | 0.000000000 | 0.000000250 | 0.000000250 |
| Tat_Den_20261021_214821_789034.wav | Bat_Den | Tat_Den | Tat_Den | 0.000000250 | 0.000000000 | 0.000000000 | 0.000000500 |

Các CSV đầy đủ chứa xác suất của cả bốn lớp, RMS, CRC32 và thời gian DSP/inference: `logs/esp_v4_laptop_parity.csv` (20 WAV dataset) và `logs/esp_v4_special_cases_parity.csv` (TTS, im lặng, nhiễu).

## TTS, im lặng và nhiễu

| WAV | Kỳ vọng | Laptop v4 | ESP v4 | ESP probabilities (Bat / Tap / Tat / Unknown) | CRC |
|---|---|---|---|---|---|
| bat_den.wav | Bat_Den | Bat_Den | Bat_Den | 0.832031 / 0.000000 / 0.011719 / 0.156250 | yes |
| tat_den.wav | Tat_Den | Bat_Den | Bat_Den | 0.554688 / 0.000000 / 0.003906 / 0.437500 | yes |
| silence.wav | Unknown | Tat_Den | Tat_Den | 0.066406 / 0.000000 / 0.921875 / 0.011719 | yes |
| noise_rms_300.wav | Unknown | Unknown | Unknown | 0.027344 / 0.003906 / 0.066406 / 0.906250 | yes |

Im lặng bị nhận Tat_Den với 0.921875 ở cả hai runtime, trong khi nhiễu RMS≈300 được nhận Unknown với 0.90625. Điều này cho thấy model chưa có khả năng loại im lặng phù hợp dù runtime parity là chính xác.

## Timing và thay đổi kỹ thuật

ESP deployment 4: DSP 193–193 ms, inference 18–18 ms trên 20 WAV. Laptop thường DSP 1 ms và inference 0–1 ms; chênh lệch thời gian là phù hợp với phần cứng, không làm thay đổi output lượng tử.

Firmware logic, giao thức EIP1, dữ liệu và ngưỡng không bị thay đổi. Chỉ thay thư viện inference deployment 3 bằng export deployment 4 và điều chỉnh đường dẫn `INCBIN` để PlatformIO đóng gói đúng chính file `.tflite`; trọng số/model hash không thay đổi.

## Hướng tiếp theo

Không cần sửa DSP/firmware cho lỗi parity. Giai đoạn huấn luyện sau nên bổ sung im lặng vào Unknown, tăng dữ liệu Tat_Den đa giọng/âm lượng/môi trường, rà soát các mẫu Tat_Den gần Bat_Den và giữ một test split theo người nói/phiên thu độc lập. Chưa huấn luyện lại hoặc thay đổi trọng số trong lần kiểm thử này.
