# Báo cáo kiểm thử `VuDieuAnhSang_inferencing` 1.0.3

Ngày kiểm thử: 2026-10-22. Phần cứng: ESP32-S3 N16R8, COM15, INMP441 (BCLK 4, WS 5, SD 6). Kết luận chính: đường truyền PCM trực tiếp đã được xác minh toàn vẹn; model nhận đúng `Bật đèn` nhưng nhận sai `Tắt đèn` thành `Bat_Den`. Model cũng phát lệnh trên im lặng và nhiễu, do đó chưa an toàn để điều khiển thiết bị.

## 1. Nguồn âm thanh và giấy phép

Không tìm được hai bản thu người thật riêng lẻ có giấy phép đủ rõ. Hai câu được tạo tổng hợp bằng Piper 1.8.0 với voice `vi_VN-vais1000-medium`:

- Kho voice Piper: <https://huggingface.co/rhasspy/piper-voices>
- Model card: <https://huggingface.co/rhasspy/piper-voices/blob/main/vi/vi_VN/vais1000/medium/MODEL_CARD>
- Voice dùng dữ liệu VAIS-1000, giấy phép CC BY 4.0, sample rate gốc 22.050 Hz.
- Runtime Piper hiện hành: <https://github.com/OHF-Voice/piper1-gpl> (GPL-3.0).

Đây là **giọng TTS tổng hợp**, không phải bản thu người thật. Model voice và model card được giữ trong `test_audio/piper_model/`.

## 2. Đặc điểm WAV

Tạo ở 22.050 Hz, giữ trọn phần tiếng nói với biên 120 ms, resample thật bằng polyphase (`scipy.signal.resample_poly`) về 16.000 Hz, rồi căn giữa và đệm digital silence đến đúng 24.000 mẫu. Không đổi metadata giả, không time-stretch, không cắt âm đầu/cuối.

| File | PCM | Mẫu / thời lượng | Vùng tiếng nói | RMS | Min / Max | Clipping | SHA-256 |
|---|---|---:|---:|---:|---:|---:|---|
| `bat_den.wav` | 16-bit mono, 16 kHz | 24.000 / 1,500 s | 6.131 mẫu (~0,383 s) | 3.674,82 | -32.688 / 24.727 | 0 | `60AD46CC550D88F6FF0C5F0206B9C83FE7B155BAB4A8D301F72F2BAFB7981434` |
| `tat_den.wav` | 16-bit mono, 16 kHz | 24.000 / 1,500 s | 6.874 mẫu (~0,430 s) | 4.310,38 | -32.468 / 26.701 | 0 | `B8FDA23D350A072C2F6CA59E2D3B76CDE36900E5F761A8B085096894B4641C23` |

Các WAV nguồn 22.050 Hz (`*_piper_raw.wav`) được giữ nguyên để truy vết.

## 3. Cấu hình model/DSP đã xác minh

- Project `VuDieuAnhSang`, project ID 1144745, deployment 3; thư viện 1.0.3.
- Cửa sổ 24.000 mẫu, 16 kHz, 1,5 s; bốn nhãn `Bat_Den`, `Tap_Am`, `Tat_Den`, `Unknown`.
- MFE implementation v4: frame 20 ms, stride 10 ms, 40 filter, FFT 256, noise floor -52 dB; đầu ra 5.960 phần tử.
- TFLite EON compiled, lượng tử hóa INT8; output scale 1/256 và zero point -128. Vì deployment chỉ chứa graph EON C++ đã compile, không có `.tflite` hoặc `.eim`, không thể thực hiện phép chạy độc lập FLOAT32/TFLite trên Windows. Không tuyên bố đã chạy phép thử độc lập đó.
- Firmware gọi nguyên trạng `run_classifier()` từ thư viện v2; DSP và trọng số không bị thay đổi.

## 4. Phép thử A — PCM trực tiếp trên ESP32-S3

Host kiểm tra WAV rồi gửi header `EIP1`, số mẫu, CRC32 và 48.000 byte PCM. ESP32 kiểm tra magic, đúng 24.000 mẫu, kích thước cố định và CRC trước khi gọi `run_classifier()`, hoàn toàn bỏ qua I2S trong phép thử này. USB CDC phải được paced theo packet 64 byte để không tràn RX ring; sau sửa, CRC host/device trùng tuyệt đối.

| Đầu vào | CRC32 | Bat_Den | Tat_Den | Tap_Am | Unknown | Top / margin | DSP / infer | Đánh giá |
|---|---|---:|---:|---:|---:|---|---|---|
| Bật đèn | `7ddf9018` | **0,984375** | 0 | 0 | 0,011719 | Bat_Den / 0,972656 | 191 / 12 ms | Đúng |
| Tắt đèn | `f7a313a4` | **0,984375** | 0 | 0 | 0,015625 | Bat_Den / 0,968750 | 191 / 12 ms | **Sai** |
| Im lặng | `0aa99847` | **0,496094** | 0,496094 | 0 | 0,007812 | Bat_Den / 0 | 190 / 12 ms | **False positive/tie** |
| Nhiễu trắng RMS 300 | `18d28b05` | **0,500000** | 0,500000 | 0 | 0 | Bat_Den / 0 | 194 / 12 ms | **False positive/tie** |

Log nguyên bản: `logs/serial_bat_den.log`, `logs/serial_tat_den.log`, `logs/serial_silence.log`, `logs/serial_noise_rms_300.log`.

## 5. Thu I2S và phép thử B

Log firmware trước khi thêm test serial cho thấy nền INMP441 có RMS khoảng 29–37, không clipping, nhưng luôn xuất `Bat_Den=0,496094`, `Tat_Den=0,496094`, `Unknown=0,007812` và code cũ chọn `Bat_Den` khi hòa. Điều này độc lập xác nhận model không có cơ chế từ chối nền hữu hiệu.

Không chạy phép thử B vì trong phiên tự động này không thể xác minh vị trí/âm lượng loa vật lý và không thể xác nhận bằng nghe hoặc ASR rằng chính cửa sổ INMP441 thu được chứa đúng câu đã phát. Vì vậy không có kết quả loa→không khí→INMP441 nào được tuyên bố.

## 6. Lỗi đã xác nhận và phân tích

1. **Model nhầm hai lệnh:** cùng DSP và cùng INT8 graph nhận `Tắt đèn` thành `Bat_Den` với margin 0,968750. CRC trùng và PCM thống kê đúng nên không thể quy lỗi cho serial, byte order hoặc I2S.
2. **Nền bị coi là lệnh:** cả zero PCM, nhiễu RMS 300 và nền mic thực đều tạo tie gần 0,5 giữa hai lệnh; `Unknown` gần 0. Đây là lỗi nghiêm trọng về dữ liệu/model và chính sách quyết định.
3. **Cửa sổ không cắt câu:** cả hai câu chỉ chiếm 0,383–0,430 s và được căn giữa trong cửa sổ 1,5 s; không mất âm đầu/cuối.
4. **Biên độ:** hai mẫu TTS lớn hơn nhiều nền mic nhưng không clipping. `Tắt đèn` có RMS lớn hơn `Bật đèn`, song cả hai vẫn đổ vào cùng nhãn nên gain không giải thích lỗi truyền; domain mismatch TTS so với dữ liệu huấn luyện vẫn là một hạn chế thực nghiệm.
5. **MFE tương thích:** firmware sử dụng chính extractor và tham số MFE đi kèm deployment, nên không thấy dấu hiệu cấu hình DSP lệch. Chưa có baseline Edge Impulse Studio/native `.eim` để so sánh bit-for-bit ngoài ESP32.
6. **FLOAT32/INT8:** chỉ INT8 compiled có trong gói, nên chưa thể định lượng chênh lệch. Bước xác suất 1/256 trong kết quả đúng với output INT8.

Nguyên nhân khả dĩ nhất là tập huấn luyện/nhãn chưa đủ tách biệt và thiếu mẫu nền/unknown đại diện; có thể thêm domain mismatch giữa giọng TTS và giọng huấn luyện. Không sửa nhãn và không ép xác suất trong firmware.

## 7. Thay đổi code

- Thêm chế độ lệnh `t` trong `src/main.cpp`: nhận EIP1, validate header/count/CRC, chạy trực tiếp PCM qua classifier, in đủ bốn xác suất, RMS, min/max, clipping, top-2 margin và timing.
- Giữ đường thu I2S cũ; thêm trường `source=I2S|SERIAL` để phân biệt nguồn.
- Thêm `tools/serial_inference.py`, `tools/generate_test_audio.py`, `tools/generate_controls.py`.
- Không điều khiển LED/relay; không sửa thư viện Edge Impulse gốc, project Arduino cũ, `a.py`, ZIP hay WAV gốc.
- Firmware trước thay đổi được lưu ở `firmware_history/firmware_before_eip1.bin`.

## 8. Build, upload và so sánh trước/sau

PlatformIO build thành công với espressif32 8.0.0 / Arduino-ESP32 3.3.12. RAM tĩnh 41.168/327.680 byte (12,6%); flash 482.296/6.553.600 byte (7,4%). Upload COM15 thành công; esptool xác nhận ESP32-S3 rev 0.2, flash 16 MB cấu hình và embedded PSRAM 8 MB, MAC `80:b5:4e:e9:4f:c4`.

Trước sửa, chỉ có kết quả nền qua I2S và không thể tách lỗi model khỏi capture. Sau sửa, hai WAV được đưa bit-exact vào cùng model: `Bật đèn` đúng, `Tắt đèn` sai. Sửa transport USB CDC từ gửi khối nhanh (timeout, chỉ nhận 30.584/48.000 byte) sang handshake header và packet 64 byte có pacing; phép chạy hợp lệ sau sửa nhận đủ 48.000/48.000 byte với CRC trùng.

## 9. Hạn chế và hướng cải thiện

- Hai câu TTS chỉ là hai mẫu của một giọng; không đủ để đánh giá độ chính xác tổng quát.
- Cần thu nhiều người nói, khoảng cách, âm lượng và môi trường thực trên chính INMP441; cân bằng `Bat_Den`/`Tat_Den`; thêm silence, gió, tiếng phòng và lời nói ngoài lệnh vào `Unknown`.
- Kiểm tra nhãn sai/trùng file và chia train/validation theo người nói, tránh cùng người lọt sang cả hai tập.
- So sánh confusion matrix MFE, nhất là phần âm đầu “bật”/“tắt”; dùng augmentation gain/noise/time shift hợp lý.
- Xuất deployment FLOAT32 hoặc `.eim`/`.tflite` tương ứng để A/B với INT8. Chỉ tạo model phiên bản mới sau khi có dữ liệu và quyền truy cập Edge Impulse phù hợp.
- Trước khi điều khiển thiết bị thật, bắt buộc thêm policy từ chối: ngưỡng xác suất và margin, debounce nhiều cửa sổ, cùng lớp `Unknown` được huấn luyện đúng. Policy không thể chữa việc `Tắt đèn` hiện bị model dự đoán `Bat_Den` với độ tin cậy cao.
