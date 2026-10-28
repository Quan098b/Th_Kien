# ESP32S3_Voice_Test — handoff cho phiên chat mới

> Cập nhật: 2026-10-23 (Asia/Bangkok)
>
> Workspace: `C:\Users\khanh\Documents\PlatformIO\Projects\ESP32S3_Voice_Test`

## 1. Mục tiêu dự án

Nhận diện giọng nói tiếng Việt trực tiếp trên ESP32-S3 N16R8 bằng microphone INMP441 và Edge Impulse. Bốn output label của model là:

1. `Bat_Den`
2. `Tap_Am`
3. `Tat_Den`
4. `Unknown`

Firmware hiện tại (từ 2026-10-23) có web dashboard qua WiFi và LED ở GPIO7 (xem mục 4).

> **Đọc mục 13 trước tiên**: nguyên nhân gốc của false accept là dữ liệu huấn luyện Edge Impulse
> mỗi label thu bằng một thiết bị khác nhau → model phân loại theo âm lượng, không theo nội dung.

## 2. Phần cứng và kết nối

- Board: ESP32-S3 N16R8, PSRAM 8 MB, flash 16 MB.
- Serial/upload port: `COM15`, 115200 baud.
- MAC đã xác minh: `80:b5:4e:e9:4f:c4`.
- INMP441:
  - BCLK: GPIO4
  - WS/LRCLK: GPIO5
  - DATA: GPIO6
- I2S: 32-bit left channel; firmware chuyển sang PCM16 bằng dịch phải 16 bit, gain 1.

## 3. Model đang chạy

- Edge Impulse project: `VuDieuAnhSang`
- Project ID: `1144745`
- Deployment: `4`
- Runtime: TensorFlow Lite Micro INT8 (`quantized=1`, `compiled=0`)
- Input: PCM16 mono, 16 kHz, 24.000 mẫu (1,5 giây)
- MFE:
  - implementation version 4
  - frame length 0,02 s
  - frame stride 0,01 s
  - 40 filters
  - FFT 256
  - win_size 101
  - noise floor -52 dB
  - output 5.960 features
- SHA-256 `.tflite`:
  `A9B5C89E841E9546A4048A0D11BA2C7EF1153C0168BEC5BCC55AF50A20F20E6D`

Model nằm trong:

`lib/VuDieuAnhSang_inferencing`

Không thay trọng số, MFE hoặc thứ tự label nếu chưa tạo deployment mới và kiểm thử parity.

## 4. Firmware hiện tại

Source chính: `src/main.cpp`.

Firmware giữ nguyên model deployment 4, I2S và bộ lọc VAD/phổ đã kiểm thử. Thay đổi gần nhất chỉ đơn giản hóa Serial Monitor.

### Serial output mặc định

`DEBUG_VERBOSE` hiện bằng 0:

```cpp
#define DEBUG_VERBOSE 0
```

Mỗi cửa sổ suy luận chỉ in một dòng:

```text
BAT DEN | 96.8% | RMS:352 | ACCEPT
TAT DEN | 94.2% | RMS:280 | ACCEPT
NOISE   | 88.5% | RMS:125 | REJECT
SILENCE | RMS:18 | REJECT
```

Quy tắc hiển thị:

- Chỉ `Bat_Den` hoặc `Tat_Den` đồng thời pass toàn bộ voice gate mới là `ACCEPT`.
- `Tap_Am` hoặc `Unknown` luôn hiển thị `NOISE ... REJECT`.
- Voice gate fail vì RMS dưới ngưỡng năng lượng: `SILENCE ... REJECT`.
- Voice gate fail vì đặc trưng khác: `NOISE ... REJECT`.
- Đặt `DEBUG_VERBOSE` thành 1 để xem lại `AUDIO`, `FILTER`, `PROB`, `RESULT`, `DECISION` và memory diagnostics.

SHA-256 firmware compact hiện tại:

`319FA9CC51FDF955BF707E2FE1E715C0A9ADED6C10A86F67E1B370E9476A360E`

Build cuối đã thành công:

- RAM: 45.672 / 327.680 byte (13,9%)
- Flash: 555.752 / 6.553.600 byte (8,5%)
- Upload COM15 và verify flash thành công.

### Web dashboard (2026-10-23) — firmware đang nạp

- WiFi STA + `WebServer` chạy task riêng trên core 0; inference giữ nguyên trên core 1.
- Model, I2S, voice gate, dòng Serial và lệnh `t`/`w` không đổi. Thêm một dòng
  `WEB | http://<ip> | http://voice.local` in một lần sau khi có WiFi (từ `loop()`, không chen vào WAV/EIP1).
- `/` = trang `include/web_page.h`; `/api/state` = JSON kết quả mới nhất, xác suất, gate, lịch sử 20 cửa sổ.
- LED GPIO7 (active high, qua điện trở 220–330 Ω xuống GND): BAT DEN ACCEPT → sáng,
  TAT DEN ACCEPT → tắt, còn lại giữ nguyên. Web hiển thị trạng thái LED thật.
  Firmware này: SHA-256 `9A01902B1DC2CB7CFFADA0F1B815716DA1884849EAD36D4D5A1246838383F394`,
  backup `firmware_history/deployment4_web_led7_20261023`.
- WiFi credentials: `include/wifi_secrets.h` (không chia sẻ file này).
- `platformio.ini` cần `lib_deps` + include path `Network/src` cho Arduino core 3.x.
- Build: RAM 77.404 B (23,6%), Flash 1.269.055 B (19,4%). Lần chạy đầu IP `192.168.1.13`.
- SHA-256 firmware: `DBF72DF14895EEC7ECDC18823492B206D2A65426B6CE07A725E0DAFCE667328D`
- Backup: `firmware_history/deployment4_web_20261023` (không chứa `wifi_secrets.h`).

## 5. Voice gate hiện tại — không tự ý đổi ngưỡng

Gate pass khi đồng thời:

- RMS ≥ 20
- active frame ratio ≥ 0,02
- spectral flatness ≤ 0,15
- low-frequency energy ratio ≤ 0,80
- zero-crossing rate ≥ 0,01

Gate dùng RMS + energy VAD + FFT 256 + spectral flatness + low-band ratio + ZCR. Confidence và score gap không tham gia gate.

Kết quả test độc lập 60 WAV:

- FAR trước gate: 60% (18/30 negative phát thành lệnh)
- FAR sau gate: 30% (9/30)
- FRR trước: 3,33% (1/30)
- FRR sau: 3,33% (1/30)
- Gate không loại nhầm mẫu lệnh nào trong test này.
- Toàn bộ silence/noise/wind/hum trong test không còn phát thành lệnh.
- 9 false accepts còn lại đều là non-command speech bị model gán `Bat_Den`; VAD không thể phân biệt nội dung câu nói.

Báo cáo: `FILTER_EVALUATION.md`.

## 6. Parity Windows và ESP32

Deployment 4 đã được kiểm thử trên cùng 20 WAV Tat_Den:

- Laptop và ESP khớp nhãn 20/20.
- Sai khác xác suất tối đa 0,0000005 (do định dạng CSV).
- Tat_Den đúng 18/20 trên cả laptop và ESP.
- Tat_Den → Bat_Den: 2/20 = 10%.
- Deployment 3 cũ chỉ đúng 0/20.
- TTS Tat_Den vẫn thành Bat_Den trên cả hai runtime.
- Silence từng bị model nhận Tat_Den 0,921875 nhưng hiện bị voice gate reject.

Kết luận đã chứng minh: PCM Serial, MFE, label order và TFLite INT8 trên ESP tương đương laptop. Lỗi còn lại thuộc model/data, không phải firmware DSP.

Báo cáo và CSV:

- `ESP_V4_PARITY_REPORT.md`
- `logs/esp_v4_laptop_parity.csv`
- `logs/esp_v4_special_cases_parity.csv`
- `LAPTOP_MODEL_TEST.md`

## 7. Phân tích hard negatives và giới hạn model

Chín non-command speech test-only bị false accept gồm:

- tôi muốn uống nước
- đi ra ngoài
- quạt đang chạy
- đèn ở phòng khách
- bật quạt
- tắt quạt
- mở nhạc
- dừng lại
- hãy nói chậm hơn

Cả 9 bị nhận `Bat_Den`; xác suất Bat_Den 0,617–0,941. `Tap_Am` luôn 0 và Tat_Den gần 0.

Đã tạo challenge set training-candidate mới gồm 30 câu như `Bật nhạc`, `Tắt quạt`, `Bật máy`, `Tắt máy`, câu phủ định, câu hỏi và hội thoại. Baseline deployment 4 false accept 26/30 = 86,7%.

Nguồn TTS: Piper `vi_VN-vais1000-medium`, một speaker, VAIS1000, CC-BY-4.0. Đây chỉ là training candidate, không đủ chứng minh đa người nói hay đủ điều kiện retrain/deploy.

Báo cáo: `MODEL_IMPROVEMENT_REPORT.md`.

Artifacts:

- `hard_negative_analysis/false_acceptance_analysis.csv`
- `hard_negative_analysis/mfe_summary.csv`
- `hard_negative_analysis/mfe_vectors.csv`
- `hard_negative_analysis/local_dataset_inventory.csv`
- `training_experiments/v5_hard_negatives/BASELINE.json`
- `training_experiments/v5_hard_negatives/hard_negative_manifest.csv`
- `training_experiments/v5_hard_negatives/baseline_hard_negative_results.csv`

## 8. Dữ liệu local hiện có

Dataset:

`C:\Users\khanh\Desktop\AIThKien\esp32_microphone_continuous\dataset_inmp441`

Inventory đã xác minh:

- `Tat_Den`: 250 WAV thật
- `Bat_Den`: 0 WAV thật
- `Tap_Am`: không có thư mục/mẫu local dùng được
- `Unknown`: không có thư mục/mẫu local dùng được
- Không có speaker ID hoặc session ID đáng tin cậy.

Không được suy speaker ID từ timestamp trong filename. Chưa đủ dữ liệu để chia speaker-disjoint hoặc huấn luyện model mới đáng tin cậy.

Không dùng các file test/parity/9 false accepts làm training rồi đánh giá lại trên chính chúng.

## 9. Serial test protocol và WAV export

Firmware vẫn giữ:

- Lệnh `t`: nhận protocol EIP1, 24.000 PCM16 samples và CRC32, rồi inference.
- Lệnh `w`: xuất một WAV 48.044 byte.

WAV export sau thay đổi Serial đã được kiểm tra:

- RIFF/WAV hợp lệ
- mono
- PCM16
- 16 kHz
- 24.000 frames
- không có debug chen vào payload nhị phân

Tools:

- `tools/serial_inference.py`
- `tools/benchmark_serial.py`
- `tools/filter_serial_benchmark.py`
- `tools/capture_wav.py`

## 10. Backup và khôi phục

Không xóa các thư mục dưới `firmware_history`.

- Full flash deployment 3:
  `firmware_history/deployment3_restore_20261022`
- Full flash deployment 4 trước filter:
  `firmware_history/deployment4_restore_20261022`
- Firmware deployment 4 có filter trước khi đổi Serial output:
  `firmware_history/deployment4_filter_verbose_restore_20261022`
- Firmware compact Serial hiện tại:
  `firmware_history/deployment4_compact_serial_20261022`

Source trước thay đổi Serial và binary SHA-256
`8311A92BE59B9F37A10EDD6E7C6DB216479C755BD9985BB146A9FF97B8BFCA35`
nằm trong `deployment4_filter_verbose_restore_20261022`.

## 11. Lệnh build/upload/monitor

Trong PowerShell tại project root:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run --target upload --upload-port COM15
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" device monitor --port COM15 --baud 115200
```

Nếu upload báo COM15 busy, kiểm tra và đóng riêng PlatformIO serial monitor đang giữ cổng trước khi upload. Không kill tiến trình không liên quan.

## 12. Việc nên làm tiếp

Ưu tiên dữ liệu/model, không tiếp tục tối ưu VAD khi chưa có bằng chứng:

1. Thu Bat_Den và Tat_Den thật từ ít nhất 5 người, ≥2 phiên/người.
2. Thu Unknown gồm speech ngoài lệnh, câu gần âm vị, phủ định, câu hỏi và lệnh thiết bị khác.
3. Xác minh ý nghĩa và dữ liệu thật của `Tap_Am`.
4. Gắn `speaker_id` và `session_id`; chia train/validation/test theo speaker trước augment.
5. Tạo bản sao Edge Impulse project/deployment; không ghi đè deployment 4.
6. Giữ nguyên MFE ban đầu để đo riêng tác động dữ liệu hard negatives.
7. Chỉ triển khai model mới nếu test speaker-disjoint giảm FAR mà FRR không tăng đáng kể, sau đó kiểm tra lại parity laptop/ESP.

Đã có thử nghiệm huấn luyện local (mục 13) nhưng không có model v5 đủ điều kiện triển khai. Không được mô tả challenge-set accuracy hoặc validation accuracy như bằng chứng triển khai.

## 13. Dữ liệu Edge Impulse gốc và thử nghiệm huấn luyện (2026-10-23)

Dataset export của project 1144745 (không có trong repo, nằm local):
`C:\Users\khanh\Desktop\AIThKien\vudieuanhsang-export` (JSON) và
`...\vudieuanhsang-export-wav` (WAV, tạo bằng `tools/export_ei_json_to_wav.py`).

| Label | Train | Test | Thiết bị thu | RMS trung vị |
|---|---|---|---|---|
| Bat_Den | 265 | 54 | 2 điện thoại + 1 máy tính | ~1.500–5.300 |
| Tap_Am | 253 | 39 | chỉ 1 điện thoại (`phone_mfn070e8`) | ~4.200 |
| Tat_Den | 200 | 50 | chỉ INMP441 (= 250 file local) | ~200 |
| Unknown | 261 | 57 | chỉ cùng điện thoại đó | ~4.700 |

- 2 mẫu Bat_Den training toàn số 0 (`Bat_Den.75bei17l`, `Bat_Den.75bf6c9g`) — nên xóa.
- ~40 mẫu Bat_Den từ máy tính dài 2,0 s (model dùng 1,5 s).
- Không trùng audio giữa train/test.

**Chứng minh shortcut âm lượng** (`tools/gain_sensitivity_test.py`, deployment 4 trên laptop, 200 mẫu test):
gốc đúng ~96%; scale về RMS 200 → toàn bộ Bat_Den và Unknown thành Tat_Den;
scale Tat_Den lên RMS 4.500 → 42/50 thành Bat_Den.

**Thử nghiệm huấn luyện** `training_experiments/v5_gain_aug/` (README + `results.json`):
cùng kiến trúc/MFE deployment 4 (MFE lấy từ `laptop_model_test/sdk/source/mfe_bin.cpp`).
- Train lại dữ liệu gốc: tái tạo đúng lỗi (accuracy ở RMS 200 chỉ 31–37%).
- Augment gain ngẫu nhiên RMS 60–6000 + noise: accuracy ở RMS 200 lên 96–97% → hết shortcut âm lượng.
- Nhưng non-command speech vẫn bị nhận thành lệnh 12–19/20 (deployment 4: 18/20); dao động lớn giữa seed.
- Kết luận: không triển khai. Cần thu Bat_Den và Unknown **bằng chính ESP + INMP441**, nhiều người,
  rồi retrain (nên trên Edge Impulse, deployment mới) và giữ augment gain.

GPU (RTX 3050 6 GB) không phải điểm nghẽn: model rất nhỏ, train CPU vài phút.
TensorFlow trên Windows native không dùng GPU; venv `training_experiments/.venv-train` (TF 2.19, không có trong repo).

## 14. Repo GitHub

`https://github.com/Quan098b/Th_Kien` (public) chỉ chứa source, tools, báo cáo và kết quả nhỏ.
Không có: `include/wifi_secrets.h` (copy từ `include/wifi_secrets.example.h`), dataset/WAV,
`firmware_history` (binary backup), `.venv*`, `laptop_model_test/sdk` (SDK copy, chỉ giữ source runner + Makefile),
`training_experiments/*/work|models|data`, `hard_negative_analysis/mfe_vectors.csv`.
`platformio.ini` có đường dẫn cứng `C:/Users/khanh/.platformio/...` cho thư viện Network.

