# TEST REPORT V2 — dataset INMP441

Ngày chạy: 2026-10-22. Seed chọn mẫu: `20261022`. Thiết bị: ESP32-S3 N16R8 trên COM15. Model: `VuDieuAnhSang_inferencing` 1.0.3, deployment 3.

## Kết luận

20/20 WAV có nhãn `Tat_Den` được chọn cố định từ `dataset_inmp441` đều bị model trên ESP32-S3 dự đoán thành `Bat_Den`. Tỷ lệ `Tat_Den → Bat_Den` là **100%**, recall và F1 của `Tat_Den` bằng **0** trên tập con này. Kết quả tái hiện lỗi bằng audio thu từ INMP441, không chỉ bằng TTS.

Không tìm thấy lỗi firmware, thứ tự nhãn, DSP hoặc transport đủ để sửa. Vì vậy không thay trọng số, không đảo nhãn, không thêm logic ép kết quả và không upload một firmware “sửa” không có căn cứ.

## 1. Kiểm kê và giới hạn dataset

Nguồn: `C:\Users\khanh\Desktop\AIThKien\esp32_microphone_continuous\dataset_inmp441`.

| Lớp | WAV hiện có | Được chọn |
|---|---:|---:|
| Bat_Den | 0 | 0 |
| Tap_Am | không có thư mục | 0 |
| Tat_Den | 250 | 20 |
| Unknown | không có thư mục | 0 |

Tất cả 250 file `Tat_Den` dài 48.044 byte và có SHA-256 khác nhau. Không có manifest hoặc metadata train/validation/test, vì vậy không thể chứng minh đây là tập Test độc lập. Báo cáo không gọi mẫu này là test độc lập và không suy diễn metric bốn lớp từ dữ liệu không tồn tại.

Việc chọn dùng `random.Random(20261022).sample()` trên danh sách đường dẫn đã sort. Dataset gốc không bị sửa, di chuyển hay đổi tên.

## 2. Quy trình thực nghiệm

Mỗi WAV được xác nhận PCM16 mono, 16 kHz, đúng 24.000 mẫu. Host gửi header `EIP1`, sample count, CRC32 và 48.000 byte PCM. ESP kiểm tra header/count/CRC rồi dùng PCM trực tiếp làm input `run_classifier()`, bỏ qua I2S. USB CDC gửi theo packet 64 byte có pacing để không tràn RX ring.

CSV đầy đủ: `logs/dataset_benchmark_seed_20261022.csv`. Summary máy đọc được: `logs/dataset_benchmark_seed_20261022.summary.json`.

## 3. Kết quả từng WAV

Timing ghi theo `DSP/inference` (ms). Tất cả file có clipping bằng 0.

| # | WAV | RMS | Bat_Den | Tap_Am | Tat_Den | Unknown | Dự đoán | Margin | Timing |
|---:|---|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | Tat_Den_20261021_215439_245839.wav | 147.75 | 0.757812 | 0 | 0.230469 | 0.011719 | Bat_Den | 0.527344 | 194/12 |
| 2 | Tat_Den_20261021_215044_824656.wav | 178.41 | 0.699219 | 0 | 0.269531 | 0.031250 | Bat_Den | 0.429688 | 194/11 |
| 3 | Tat_Den_20261021_215310_123139.wav | 739.32 | 0.820312 | 0 | 0.023438 | 0.156250 | Bat_Den | 0.664062 | 194/12 |
| 4 | Tat_Den_20261021_214924_424200.wav | 87.95 | 0.554688 | 0 | 0.437500 | 0.007812 | Bat_Den | 0.117188 | 194/11 |
| 5 | Tat_Den_20261021_230628_317894.wav | 937.39 | 0.914062 | 0 | 0.050781 | 0.031250 | Bat_Den | 0.863281 | 194/11 |
| 6 | Tat_Den_20261021_214812_315519.wav | 109.61 | 0.492188 | 0 | 0.492188 | 0.015625 | Bat_Den | 0 | 194/11 |
| 7 | Tat_Den_20261021_214644_966730.wav | 362.96 | 0.828125 | 0 | 0.125000 | 0.046875 | Bat_Den | 0.703125 | 194/12 |
| 8 | Tat_Den_20261021_230708_630365.wav | 580.48 | 0.554688 | 0 | 0.007812 | 0.437500 | Bat_Den | 0.117188 | 194/12 |
| 9 | Tat_Den_20261021_230609_200512.wav | 690.58 | 0.699219 | 0 | 0.031250 | 0.269531 | Bat_Den | 0.429688 | 194/12 |
| 10 | Tat_Den_20261021_214904_602165.wav | 96.05 | 0.554688 | 0 | 0.437500 | 0.007812 | Bat_Den | 0.117188 | 194/11 |
| 11 | Tat_Den_20261021_214838_809565.wav | 178.73 | 0.601562 | 0 | 0.371094 | 0.027344 | Bat_Den | 0.230469 | 194/11 |
| 12 | Tat_Den_20261021_214902_759356.wav | 75.88 | 0.554688 | 0 | 0.437500 | 0.007812 | Bat_Den | 0.117188 | 194/11 |
| 13 | Tat_Den_20261021_214540_648363.wav | 461.62 | 0.664062 | 0 | 0.257812 | 0.078125 | Bat_Den | 0.406250 | 194/11 |
| 14 | Tat_Den_20261021_223144_213761.wav | 121.27 | 0.550781 | 0 | 0.433594 | 0.011719 | Bat_Den | 0.117188 | 194/12 |
| 15 | Tat_Den_20261021_230611_327779.wav | 517.67 | 0.894531 | 0 | 0.066406 | 0.039062 | Bat_Den | 0.828125 | 194/11 |
| 16 | Tat_Den_20261021_215228_555390.wav | 773.99 | 0.671875 | 0 | 0 | 0.328125 | Bat_Den | 0.343750 | 194/12 |
| 17 | Tat_Den_20261021_214750_727109.wav | 106.87 | 0.550781 | 0 | 0.433594 | 0.011719 | Bat_Den | 0.117188 | 194/11 |
| 18 | Tat_Den_20261021_214650_342274.wav | 312.41 | 0.816406 | 0 | 0.152344 | 0.027344 | Bat_Den | 0.664062 | 194/11 |
| 19 | Tat_Den_20261021_214823_869835.wav | 134.80 | 0.593750 | 0 | 0.371094 | 0.035156 | Bat_Den | 0.222656 | 194/12 |
| 20 | Tat_Den_20261021_214821_789034.wav | 82.67 | 0.554688 | 0 | 0.437500 | 0.007812 | Bat_Den | 0.117188 | 194/11 |

DSP trung bình 194,0 ms; inference trung bình 11,4 ms. RMS trải từ 75,88 đến 937,39 nhưng toàn bộ đều sai, nên gain đơn thuần không giải thích kết quả.

## 4. Confusion matrix

Hàng là nhãn thật, cột là dự đoán.

| Actual \\ Predicted | Bat_Den | Tap_Am | Tat_Den | Unknown | Support |
|---|---:|---:|---:|---:|---:|
| Bat_Den | 0 | 0 | 0 | 0 | 0 |
| Tap_Am | 0 | 0 | 0 | 0 | 0 |
| Tat_Den | **20** | 0 | 0 | 0 | 20 |
| Unknown | 0 | 0 | 0 | 0 | 0 |

Đây là ma trận quan sát một lớp, không phải confusion matrix bốn lớp hoàn chỉnh.

| Lớp | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Bat_Den | 0,0000 (20 false positive) | N/A | N/A | 0 |
| Tap_Am | N/A | N/A | N/A | 0 |
| Tat_Den | N/A (không có dự đoán Tat_Den) | **0,0000** | **0,0000** | 20 |
| Unknown | N/A | N/A | N/A | 0 |

Accuracy trên 20 file: 0%. Tỷ lệ `Tat_Den → Bat_Den`: **20/20 = 100%**. Không tính macro/micro score bốn lớp vì ba lớp không có support.

## 5. Đối chiếu model, DSP và input

- Project ID 1144745, tên `VuDieuAnhSang`, deployment 3, labels theo đúng thứ tự: `Bat_Den`, `Tap_Am`, `Tat_Den`, `Unknown`.
- Input 16 kHz × 24.000 mẫu = 1,5 s; PCM được chuyển sang float trực tiếp bằng callback SDK, không đổi gain trong đường Serial.
- MFE implementation v4: frame 20 ms, stride 10 ms, 40 filters, FFT 256, window size 101, noise floor -52 dB, output 5.960 đặc trưng.
- Graph EON compiled INT8, output zero point -128 và scale 0,00390625. Bước xác suất quan sát được đúng 1/256.
- SHA-256 của `model_metadata.h`, `model_variables.h` và `tflite_learn_1144745_3_compiled.cpp` trong thư viện đang build trùng tuyệt đối với bản nguồn đã giải nén từ `v2.zip`.
- CRC từng WAV khớp giữa host và ESP; file #1 được chạy kiểm tra lại riêng cho cùng xác suất và thống kê (`rms=147,75`, min=-1225, max=1073).

Không có dấu hiệu label indexing, deployment mismatch, resampling, byte order, clipping hoặc MFE config mismatch trong firmware.

## 6. So sánh runtime Edge Impulse

Không thể chạy phép đối chiếu Edge Impulse Studio/native trong phiên này:

- `v2.zip` chỉ chứa Arduino C++ Library với EON compiled graph, không chứa `.eim` hoặc `.tflite` độc lập.
- Không tìm thấy `model.eim` trong project/dataset.
- WSL2 không khởi động được vì virtualization của máy đang tắt; native `.eim` là executable Linux.
- Không có phiên đăng nhập/quyền project Edge Impulse được cung cấp để tải deployment 3 từ Studio.

Do đó báo cáo **không tuyên bố** đã so sánh Studio. Việc hash-match ba thành phần model chỉ chứng minh firmware dùng đúng artifact v2, không thay thế phép chạy runtime thứ hai.

## 7. Trước/sau và quyết định sửa

| Giai đoạn | Dữ liệu | Kết quả Tat_Den |
|---|---|---|
| Báo cáo V1 | 1 WAV TTS | Bat_Den 0,984375 — sai |
| Báo cáo V2 | 20 WAV gốc INMP441, seed cố định | 20/20 thành Bat_Den — sai |

V2 mở rộng bằng chứng và loại trừ giả thuyết “chỉ TTS khác miền”. Không có thay đổi firmware/DSP sau benchmark vì chưa tìm thấy lỗi code. Vì vậy không có build/upload “sau sửa” để so sánh và không tuyên bố đã sửa lỗi.

Tool mới: `tools/benchmark_serial.py` và `tools/summarize_benchmark.py`. Các script này không sửa dataset. ZIP gốc, thư viện gốc và firmware backup được giữ nguyên.

## 8. Chẩn đoán và đề xuất huấn luyện lại

Bằng chứng hiện tại phù hợp nhất với lỗi model/dataset: lớp `Tat_Den` không được học đúng hoặc deployment 3 được huấn luyện từ phân vùng/nhãn khác với thư mục hiện có. Cần kiểm tra trong bản sao Edge Impulse project:

1. Đối chiếu sample ID/hash và label thực sự đã upload; kiểm tra nhãn bị đảo, file trùng và leakage giữa train/test.
2. Tạo test split bất biến theo phiên/người nói, tối thiểu 20 file mỗi lớp, không random-split các đoạn gần nhau từ cùng phiên ghi.
3. Bổ sung và cân bằng đủ `Bat_Den`, `Tat_Den`, `Tap_Am`, `Unknown`; `Unknown` phải có silence, nền phòng, gió và lời ngoài lệnh.
4. Kiểm tra MFE feature explorer/confusion matrix, đặc biệt các frame chứa phụ âm đầu “b” và “t”; cân chỉnh vị trí câu trong cửa sổ 1,5 s.
5. Augmentation gain/noise/time-shift trong miền INMP441, nhưng không dùng augmentation thay cho dữ liệu thật.
6. Huấn luyện bản sao với cả FLOAT32 và INT8, xuất `.eim`; chạy chính CSV manifest này trên Studio/native và ESP trước khi thay deployment đang dùng.

Chưa thể thực hiện huấn luyện lại vì thiếu ba lớp dữ liệu, split độc lập và quyền truy cập project Edge Impulse. Không được triển khai model hiện tại để điều khiển relay/LED.
