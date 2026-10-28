# FILTER_EVALUATION

Ngày đánh giá: 2026-10-22. Model giữ nguyên Edge Impulse deployment 4; không đổi trọng số, confidence, score gap hoặc thứ tự nhãn.

## Kết luận

Trên split test độc lập 60 WAV, bộ lọc energy-VAD/phổ giảm **FAR từ 60.0% xuống 30.0%** và giữ **FRR 3.33% → 3.33%**. Không có mẫu lệnh nào bị chính gate loại nhầm. Kết quả này được chạy lại trực tiếp trên ESP32-S3 qua COM15/CRC32, không chỉ mô phỏng laptop.

Bộ lọc loại toàn bộ command false-accept do silence, white/colored noise, wind và hum trong test. Nó không loại được lời nói thật có nội dung ngoài lệnh: 9/10 câu non-command vẫn bị model gán Bat_Den. Vì vậy đây là cải thiện có giới hạn; cần huấn luyện lại Unknown bằng non-command speech thật để giải quyết phần còn lại.

## Bộ dữ liệu và phân vùng

- Seed `20261022`; dev 60 WAV và test 60 WAV, không dùng test để chọn ngưỡng.
- Mỗi split: 20 Tat_Den thật chưa dùng trong parity, 10 Bat_Den TTS augmentation, 20 noise/silence/wind/hum và 10 câu tiếng Việt ngoài lệnh.
- Không có WAV Bat_Den, Tap_Am hoặc Unknown thu thật trong dataset hiện có. Vì vậy kết luận cho Bat_Den dựa trên TTS augmentation và kết luận negative dựa trên controls/TTS; cần xác nhận thêm bằng bản ghi thực địa.
- WAV gốc không bị sửa; fixtures mới nằm trong `filter_evaluation/audio`.

## Bộ lọc đã chọn trên dev

Gate chỉ pass khi đồng thời: RMS ≥ 20; tỷ lệ frame có tiếng ≥ 2%; spectral flatness ≤ 0,15; tỷ lệ năng lượng 80–250 Hz ≤ 0,80; zero-crossing rate ≥ 0,01. Phổ được tính bằng các FFT 256 điểm chồng lấn. Confidence và score gap không tham gia gate.

## Kết quả ESP trên split test

| Nhóm | N | Model phát lệnh trước lọc | Phát lệnh sau lọc | RMS median | Flatness median | Low-band median |
|---|---:|---:|---:|---:|---:|---:|
| Bat_Den_tts_augmented | 10 | 10 | 10 | 3683.9 | 0.0279 | 0.1656 |
| Tat_Den_real | 20 | 20 | 20 | 192.9 | 0.0198 | 0.2052 |
| background_colored | 5 | 4 | 0 | 1800.0 | 0.0919 | 0.6288 |
| background_white | 5 | 0 | 0 | 1800.0 | 0.9967 | 0.0158 |
| hum | 5 | 1 | 0 | 1800.0 | 0.1168 | 0.8914 |
| non_command_speech | 10 | 9 | 9 | 4583.1 | 0.0335 | 0.1582 |
| wind | 5 | 4 | 0 | 1799.8 | 0.0000 | 0.8545 |

| Chỉ số | Trước | Sau |
|---|---:|---:|
| FAR (negative bị phát thành Bat/Tat) | 60.00% (18/30) | 30.00% (9/30) |
| FRR (lệnh không ra đúng nhãn) | 3.33% (1/30) | 3.33% (1/30) |

## Các trường hợp sai còn lại

- Test Tat_Den: `Tat_Den_20261021_230712_137669.wav` vẫn thành Bat_Den; gate pass. Đây là lỗi phân lớp, không phải absence-of-speech.
- Non-command speech: 9/10 thành Bat_Den; gate phải cho qua vì đó là tiếng nói thật. Dùng VAD để chặn chúng sẽ đồng thời tăng FRR cho câu lệnh.
- TTS Tat_Den và hai lỗi Tat_Den của bộ parity cũ đều có đặc trưng tiếng nói và pass gate:

| WAV | RMS | Active | Flatness | Low ratio | ZCR | Gate | Model |
|---|---:|---:|---:|---:|---:|---|---|
| Tat_Den_20261021_230628_317894.wav | 937.4 | 0.510 | 0.0084 | 0.3074 | 0.0462 | PASS | Bat_Den |
| Tat_Den_20261021_215228_555390.wav | 774.0 | 0.664 | 0.0051 | 0.2978 | 0.0584 | PASS | Bat_Den |
| tat_den.wav | 4310.4 | 0.302 | 0.0656 | 0.2010 | 0.0248 | PASS | Bat_Den |

## Unknown và Tap_Am

Trong 30 negative test, model nguyên bản phát lệnh 18 lần. Tap_Am không thắng ở bất kỳ mẫu test nào; Unknown chỉ xử lý được một phần noise và 1/10 non-command speech. Với dữ liệu hiện có, hai nhãn này chưa bao phủ tốt silence và speech ngoài lệnh. Tên `Tap_Am` cũng không có mẫu WAV tương ứng để xác minh semantic; cần kiểm tra lại định nghĩa/labelling trong Edge Impulse trước khi retrain.

## Firmware và khả năng khôi phục

- Build thành công: RAM 13,9%, flash 8,5%. Firmware filter SHA-256 `8311A92BE59B9F37A10EDD6E7C6DB216479C755BD9985BB146A9FF97B8BFCA35`.
- Upload COM15 và verify flash thành công trên MAC `80:b5:4e:e9:4f:c4`.
- Backup nguyên flash deployment 4 trước thay đổi: 16 MiB, SHA-256 `73E8D0982934D1A7EEB2B24A807BF08D26D060A33705E3867B8A3BDB87F72FD9`; hướng dẫn tại `firmware_history/deployment4_restore_20261022/RESTORE.md`.
- Firmware vẫn chạy inference và in cả model result lẫn final decision; không điều khiển LED/relay.

## Khuyến nghị tiếp theo

Thu ít nhất 50–100 mẫu mỗi nhóm Bat_Den, Tat_Den, silence/noise và non-command speech từ nhiều người/phiên/phòng; đưa silence và speech ngoài lệnh vào Unknown; làm rõ hoặc đổi nhãn Tap_Am; chia test theo người nói/phiên thu. Sau đó huấn luyện một bản sao deployment mới và giữ nguyên bộ test này làm holdout.
