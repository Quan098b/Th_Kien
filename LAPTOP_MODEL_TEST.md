# Laptop Model Test — VuDieuAnhSang deployment 4

Ngày chạy: 2026-10-22. Toàn bộ thay đổi nằm trong `laptop_model_test`; firmware ESP32-S3 và WAV gốc không bị sửa.

## Kết luận

C++ Library mới đã được biên dịch và chạy native trên Windows x86_64 bằng MinGW. Runner sử dụng nguyên Edge Impulse SDK, MFE và TFLite INT8 trong ZIP, không dùng MFCC tự viết hay model thay thế.

Trên 20 WAV `Tat_Den` giống hệt benchmark ESP trước đó, deployment 4 trên laptop nhận đúng 18/20 (90%), thay vì deployment 3 trên ESP nhận sai 20/20 thành `Bat_Den`. Hai file còn sai gồm một trường hợp hòa tuyệt đối. Tuy nhiên WAV TTS “Tắt đèn” vẫn bị deployment 4 nhận thành `Bat_Den`; lỗi tổng quát hóa theo giọng/miền dữ liệu chưa được giải quyết.

Không có 20 WAV `Bat_Den` đã thu trên máy: thư mục `dataset_inmp441/Bat_Den` tồn tại nhưng rỗng và tìm toàn bộ thư mục người dùng chỉ thấy WAV TTS. Vì vậy yêu cầu 20 mẫu lớp này chưa thể thực hiện và không có accuracy hai lớp cân bằng.

## 1. Xác minh ZIP/model

ZIP mới nhất trong Downloads:

- `C:\Users\khanh\Downloads\vudieuanhsang-cpp-mcu-v4-impulse-#1.zip`
- LastWriteTime: 2026-10-22 04:44:19
- SHA-256: `6026800E7403DC730218B95E9BE11879D0D522B3794248DE1BAF31C6E3CF1CA6`
- Project ID: `1144745`; project: `VuDieuAnhSang`; deployment: `4`
- Sensor audio, 16.000 Hz, 24.000 mẫu, 1,5 giây
- Nhãn/tensor order: `Bat_Den`, `Tap_Am`, `Tat_Den`, `Unknown`
- TFLite INT8, `EI_CLASSIFIER_QUANTIZATION_ENABLED=1`, `EI_CLASSIFIER_COMPILED=0`
- `.tflite` SHA-256: `A9B5C89E841E9546A4048A0D11BA2C7EF1153C0168BEC5BCC55AF50A20F20E6D`

Không có nhãn ON/OFF tiếng Anh và project name không phải `Longvio12-project-1`.

## 2. Build native Windows

Visual Studio/MSVC có trên máy nhưng library dùng GNU `INCBIN` để nhúng `.tflite`, nên đường MSVC không phù hợp trực tiếp. WSL2 cũng không thể khởi động vì virtualization đang tắt. Đã cài WinLibs MinGW-W64 16.2.0 trong phạm vi user và dùng Makefile từ official `edgeimpulse/example-standalone-inferencing` làm nền.

Lỗi link đầu tiên là Windows command line quá dài do hàng trăm object TFLM. Makefile trong bản sao được sửa dùng response file `build/objects.rsp`; build sau đó thành công.

- Executable: `laptop_model_test/sdk/build/laptop_infer.exe`
- SHA-256 executable: `D9A15AA685330D2B1824DC26505D98237093B9F9DE66DCCF1672516D82B5D1EE`
- Build lặp lại bằng `laptop_model_test/build.ps1`
- Runner kiểm tra RIFF/WAVE, PCM16, mono, 16 kHz và đúng 24.000 mẫu trước inference.

## 3. DSP và độ tương đương input

Deployment 4 và firmware deployment 3 có cùng cấu hình DSP:

- MFE implementation v4
- frame length 20 ms, stride 10 ms
- 40 filters, FFT 256, window size 101, noise floor -52 dB
- 5.960 đặc trưng đầu vào NN
- không có data-normalization block riêng
- PCM16 được cast trực tiếp thành float, giống callback firmware Serial
- output INT8: zero point -128, scale 1/256

Khác biệt quan trọng là **phiên bản trọng số/runtime model**: laptop dùng deployment 4 `.tflite`; firmware hiện tại dùng deployment 3 EON-compiled. Vì thế so sánh laptop–ESP bên dưới là so sánh deployment 4 với 3, không phải phép kiểm tra hai runtime của cùng một binary model.

## 4. Kết quả 20 WAV Tat_Den

Danh sách được giữ đúng seed `20261022` và manifest V2. Bảng đầy đủ gồm RMS/timing nằm trong `laptop_model_test/laptop_results.csv`.

| WAV | Bat_Den | Tap_Am | Tat_Den | Unknown | Dự đoán |
|---|---:|---:|---:|---:|---|
| Tat_Den_20261021_215439_245839.wav | 0.066406 | 0.003906 | 0.925781 | 0.003906 | Tat_Den |
| Tat_Den_20261021_215044_824656.wav | 0.066406 | 0 | 0.925781 | 0.003906 | Tat_Den |
| Tat_Den_20261021_215310_123139.wav | 0.433594 | 0.007812 | 0.550781 | 0.007812 | Tat_Den |
| Tat_Den_20261021_214924_424200.wav | 0.066406 | 0 | 0.921875 | 0.007812 | Tat_Den |
| Tat_Den_20261021_230628_317894.wav | **0.492188** | 0.003906 | **0.492188** | 0.007812 | **Bat_Den (tie)** |
| Tat_Den_20261021_214812_315519.wav | 0.054688 | 0 | 0.937500 | 0.007812 | Tat_Den |
| Tat_Den_20261021_214644_966730.wav | 0.156250 | 0.003906 | 0.828125 | 0.011719 | Tat_Den |
| Tat_Den_20261021_230708_630365.wav | 0.417969 | 0.003906 | 0.527344 | 0.050781 | Tat_Den |
| Tat_Den_20261021_230609_200512.wav | 0.308594 | 0.007812 | 0.625000 | 0.058594 | Tat_Den |
| Tat_Den_20261021_214904_602165.wav | 0.066406 | 0 | 0.921875 | 0.007812 | Tat_Den |
| Tat_Den_20261021_214838_809565.wav | 0.042969 | 0 | 0.953125 | 0 | Tat_Den |
| Tat_Den_20261021_214902_759356.wav | 0.066406 | 0 | 0.921875 | 0.007812 | Tat_Den |
| Tat_Den_20261021_214540_648363.wav | 0.156250 | 0.003906 | 0.820312 | 0.019531 | Tat_Den |
| Tat_Den_20261021_223144_213761.wav | 0.054688 | 0 | 0.937500 | 0.007812 | Tat_Den |
| Tat_Den_20261021_230611_327779.wav | 0.273438 | 0.003906 | 0.707031 | 0.015625 | Tat_Den |
| Tat_Den_20261021_215228_555390.wav | **0.511719** | 0.023438 | 0.402344 | 0.058594 | **Bat_Den** |
| Tat_Den_20261021_214750_727109.wav | 0.066406 | 0 | 0.925781 | 0.007812 | Tat_Den |
| Tat_Den_20261021_214650_342274.wav | 0.191406 | 0.003906 | 0.800781 | 0.007812 | Tat_Den |
| Tat_Den_20261021_214823_869835.wav | 0.054688 | 0 | 0.941406 | 0.003906 | Tat_Den |
| Tat_Den_20261021_214821_789034.wav | 0.066406 | 0 | 0.921875 | 0.007812 | Tat_Den |

Accuracy Tat_Den dataset: **18/20 = 90%**. Tỷ lệ `Tat_Den → Bat_Den`: **2/20 = 10%**. Native laptop timing khoảng 1 ms DSP và 0–1 ms inference; không so timing trực tiếp với MCU vì CPU và timer khác nhau.

### Confusion matrix — dữ liệu thu hiện có

Hàng là actual, cột là predicted.

| Actual \\ Predicted | Bat_Den | Tap_Am | Tat_Den | Unknown | Support |
|---|---:|---:|---:|---:|---:|
| Bat_Den | 0 | 0 | 0 | 0 | 0 |
| Tap_Am | 0 | 0 | 0 | 0 | 0 |
| Tat_Den | 2 | 0 | 18 | 0 | 20 |
| Unknown | 0 | 0 | 0 | 0 | 0 |

Đây chưa phải confusion matrix bốn lớp hợp lệ vì ba lớp không có support.

## 5. Hai WAV TTS

| WAV / expected | Bat_Den | Tap_Am | Tat_Den | Unknown | Dự đoán | Đúng? |
|---|---:|---:|---:|---:|---|---|
| `bat_den.wav` / Bat_Den | 0.832031 | 0 | 0.011719 | 0.156250 | Bat_Den | Có |
| `tat_den.wav` / Tat_Den | 0.554688 | 0 | 0.003906 | 0.437500 | Bat_Den | Không |

TTS accuracy: 1/2 = 50%. Kết quả gộp 20 dataset + 2 TTS là 19/22 = 86,36%, nhưng số này mất cân bằng mạnh và không nên dùng làm accuracy tổng quát.

## 6. So sánh đúng cùng WAV với ESP32-S3

CSV ghép từng file: `laptop_model_test/esp_v3_vs_laptop_v4.csv`.

| Kết quả trên cùng 20 Tat_Den | ESP deployment 3 | Laptop deployment 4 |
|---|---:|---:|
| Dự đoán Tat_Den | 0 | 18 |
| Dự đoán Bat_Den | 20 | 2 |
| Accuracy | 0% | 90% |

18/20 file đổi từ `Bat_Den` trên v3 sang `Tat_Den` trên v4; hai file vẫn là `Bat_Den`. PCM của phép ESP đã được CRC32 xác minh, còn laptop đọc nguyên byte PCM từ cùng đường dẫn. MFE parameters và label order giống nhau. Chênh lệch chủ yếu được quy cho deployment/trọng số v4, không phải Windows DSP.

Không nạp v4 lên ESP để kiểm tra bit-level runtime parity vì yêu cầu hiện tại cấm sửa firmware đang chạy. Muốn kết luận TFLM laptop và ESP hoàn toàn tương đương cần build một firmware tạm dùng đúng deployment 4 rồi khôi phục bản hiện tại, hoặc cho phép thay firmware.

## 7. Đánh giá và bước tiếp theo

Deployment 4 cải thiện rất lớn trên các mẫu INMP441 `Tat_Den` hiện có, nhưng chưa chứng minh model tổng quát hóa tốt:

- Không có 20 WAV thu `Bat_Den`, `Tap_Am`, `Unknown` để đo precision/recall/F1 bốn lớp.
- Một file Tat_Den hòa 0,492188/0,492188; cách chọn phần tử đầu khiến nó thành `Bat_Den`.
- Một file Tat_Den sai rõ hơn (Bat 0,511719 so với Tat 0,402344).
- TTS Tat_Den vẫn sai và có Unknown cao 0,4375, cho thấy domain/speaker mismatch.

Đề xuất trước huấn luyện lại: bổ sung test set độc lập theo người/phiên ghi cho cả bốn lớp; kiểm tra hai file sai trong MFE feature explorer; thêm nhiều người nói và mức gain; đưa silence, nền, lời ngoài lệnh vào Unknown; split theo recording session thay vì random clip. Không thay threshold hoặc đảo nhãn để che hai lỗi này.

## 8. Artifacts

- `laptop_model_test/sdk/`: bản giải nén C++ Library v4 và runner
- `laptop_model_test/sdk/source/main.cpp`: WAV validator + Edge Impulse inference
- `laptop_model_test/build.ps1`: build lặp lại
- `laptop_model_test/run_benchmark.py`: benchmark đúng manifest
- `laptop_model_test/laptop_results.csv`: xác suất/timing/RMS từng WAV
- `laptop_model_test/laptop_raw_output.txt`: output nguyên bản
- `laptop_model_test/laptop_summary.json`: summary
- `laptop_model_test/esp_v3_vs_laptop_v4.csv`: so sánh từng WAV với ESP v3

Nguồn cấu trúc build tham chiếu: <https://github.com/edgeimpulse/example-standalone-inferencing>.
