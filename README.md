# Th_Kien — nhận diện giọng nói tiếng Việt trên ESP32-S3

ESP32-S3 N16R8 + micro INMP441 + model Edge Impulse (deployment 4) nhận lệnh
`Bat_Den` / `Tat_Den`, kèm voice gate, web dashboard qua WiFi và LED ở GPIO7.

**Bắt đầu từ [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md)** — trạng thái hiện tại, ràng buộc,
kết quả đo và việc nên làm tiếp. Mục 13 giải thích nguyên nhân gốc của lỗi nhận nhầm.

## Cấu trúc

| Đường dẫn | Nội dung |
|---|---|
| `src/main.cpp` | Firmware: I2S, voice gate, inference, Serial, WiFi/web, LED |
| `include/web_page.h` | Giao diện web (`/`), dữ liệu ở `/api/state` |
| `include/wifi_secrets.example.h` | Mẫu; copy thành `wifi_secrets.h` |
| `lib/VuDieuAnhSang_inferencing` | Thư viện Edge Impulse deployment 4 (không sửa) |
| `tools/` | Script Serial test, benchmark, export dataset, kiểm tra độ nhạy âm lượng |
| `laptop_model_test/` | Runner chạy model trên Windows (cần SDK từ ZIP deployment, không kèm) |
| `training_experiments/` | Thử nghiệm hard negatives và augment âm lượng |
| `*.md`, `logs/`, `filter_evaluation/`, `hard_negative_analysis/` | Báo cáo và kết quả đo |

## Build và nạp

```powershell
copy include\wifi_secrets.example.h include\wifi_secrets.h   # rồi sửa SSID/mật khẩu
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run --target upload --upload-port COM15
```
