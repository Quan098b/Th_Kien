# MODEL_IMPROVEMENT_REPORT

Ngày phân tích: 2026-10-22. Firmware filter và Edge Impulse deployment 4 được giữ nguyên; không build/upload firmware trong giai đoạn này.

## Kết luận

Chưa huấn luyện hoặc đề xuất triển khai model mới. Máy không có Edge Impulse CLI/config đăng nhập và Computer Use không có browser khả dụng; C++ deployment ZIP không chứa training data hay training job configuration. Dữ liệu local cũng chưa đủ: chỉ có 250 WAV Tat_Den, không có WAV thật cho Bat_Den, Tap_Am hoặc Unknown, và không có speaker/session ID đáng tin cậy.

Bằng chứng hard-negative rất mạnh: baseline nhận **26/30 (86.7%)** câu training-candidate mới thành Bat_Den/Tat_Den. Trong test độc lập trước đó, 9/10 non-command speech thành Bat_Den. Do đó ưu tiên đúng là bổ sung speech hard negatives vào Unknown và thu Bat_Den thật đa người nói, không tối ưu thêm VAD.

## Chín false acceptance độc lập

MFE được trích bằng chính `extract_mfe_features` của SDK deployment 4: implementation 4, 40 filter, FFT 256, 5.960 phần tử. Vector đầy đủ nằm tại `hard_negative_analysis/mfe_vectors.csv`.

| Nội dung | RMS | Bat | Tap | Tat | Unknown | MFE mean | MFE std | P95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| tôi muốn uống nước | 4556.4 | 0.617 | 0.000 | 0.000 | 0.383 | 0.1149 | 0.1668 | 0.4609 |
| đi ra ngoài | 5882.8 | 0.895 | 0.000 | 0.000 | 0.105 | 0.1594 | 0.2259 | 0.6016 |
| quạt đang chạy | 3935.6 | 0.914 | 0.000 | 0.000 | 0.086 | 0.1088 | 0.1867 | 0.5391 |
| đèn ở phòng khách | 5357.5 | 0.723 | 0.000 | 0.000 | 0.277 | 0.1696 | 0.2035 | 0.5664 |
| bật quạt | 2909.0 | 0.938 | 0.000 | 0.027 | 0.035 | 0.0686 | 0.1520 | 0.4648 |
| tắt quạt | 4294.7 | 0.844 | 0.000 | 0.031 | 0.125 | 0.0843 | 0.1776 | 0.5312 |
| mở nhạc | 3713.6 | 0.941 | 0.000 | 0.004 | 0.055 | 0.0926 | 0.1709 | 0.4883 |
| dừng lại | 4609.7 | 0.805 | 0.000 | 0.004 | 0.191 | 0.1037 | 0.1869 | 0.5195 |
| hãy nói chậm hơn | 5747.6 | 0.871 | 0.000 | 0.000 | 0.129 | 0.1895 | 0.2174 | 0.5977 |

Cả 9 đều pass VAD và đều bị nhận Bat_Den. Bat_Den nằm trong khoảng 0,617–0,941; Tap_Am luôn 0; Tat_Den 0–0,031. Điều này phù hợp với thiếu hard-negative speech trong vùng âm vị gần “bật/tắt”, không phải lỗi PCM/MFE.

## Audit dữ liệu hiện có

| Label | WAV local | Speaker ID | Session ID rõ ràng | Split theo speaker được? |
|---|---:|---:|---:|---|
| Bat_Den | 0 | 0 | 0 | no |
| Tat_Den | 250 | 0 | 0 | no |
| Tap_Am | 0 | 0 | 0 | no |
| Unknown | 0 | 0 | 0 | no |

Các filename Tat_Den chứa timestamp và cho thấy nhiều cụm thời gian, nhưng không chứng minh đó là người nói hay phiên thu độc lập. Không được dùng timestamp làm speaker ID giả. Thành phần training thực tế trên Edge Impulse chưa thể audit từ deployment ZIP.

## Challenge set mới

Đã tạo 30 training-only candidates từ Piper `vi_VN-vais1000-medium`, model card ghi một speaker, nguồn VAIS1000, giấy phép CC-BY-4.0. Các câu gồm Bật/Tắt nhạc, quạt, máy, máy lạnh, TV, điện thoại; phủ định; câu hỏi; và lời nói không phải lệnh.

| Câu | Bat | Tat | Unknown | Dự đoán |
|---|---:|---:|---:|---|
| Bật nhạc | 0.871 | 0.023 | 0.102 | Bat_Den |
| Tắt nhạc | 0.750 | 0.020 | 0.227 | Bat_Den |
| Bật quạt | 0.934 | 0.043 | 0.020 | Bat_Den |
| Tắt quạt | 0.828 | 0.047 | 0.125 | Bat_Den |
| Bật máy | 0.914 | 0.020 | 0.066 | Bat_Den |
| Tắt máy | 0.668 | 0.004 | 0.328 | Bat_Den |
| Bật máy lạnh | 0.723 | 0.000 | 0.277 | Bat_Den |
| Tắt máy lạnh | 0.617 | 0.000 | 0.383 | Bat_Den |
| Bật ti vi | 0.492 | 0.016 | 0.492 | Bat_Den |
| Tắt ti vi | 0.277 | 0.000 | 0.719 | Unknown |
| Bật điện thoại | 0.867 | 0.000 | 0.129 | Bat_Den |
| Tắt điện thoại | 0.559 | 0.000 | 0.441 | Bat_Den |
| Bật đèn phòng khách | 0.723 | 0.000 | 0.277 | Bat_Den |
| Tắt đèn phòng khách | 0.066 | 0.000 | 0.934 | Unknown |
| Đèn đang bật | 0.840 | 0.000 | 0.160 | Bat_Den |
| Đèn đang tắt | 0.379 | 0.008 | 0.613 | Unknown |
| Đừng bật đèn | 0.805 | 0.000 | 0.191 | Bat_Den |
| Không được tắt đèn | 0.617 | 0.000 | 0.383 | Bat_Den |
| Bạn có bật đèn không | 0.559 | 0.000 | 0.441 | Bat_Den |
| Bạn có tắt đèn không | 0.500 | 0.000 | 0.500 | Bat_Den |
| Tôi muốn uống nước | 0.617 | 0.000 | 0.383 | Bat_Den |
| Đi ra ngoài | 0.945 | 0.000 | 0.055 | Bat_Den |
| Quạt đang chạy | 0.930 | 0.000 | 0.066 | Bat_Den |
| Đèn ở phòng khách | 0.766 | 0.000 | 0.234 | Bat_Den |
| Mở cửa sổ | 0.559 | 0.000 | 0.441 | Bat_Den |
| Đóng cửa lại | 0.277 | 0.000 | 0.723 | Unknown |
| Mở nhạc | 0.941 | 0.004 | 0.055 | Bat_Den |
| Dừng lại | 0.895 | 0.004 | 0.105 | Bat_Den |
| Hãy nói chậm hơn | 0.809 | 0.000 | 0.191 | Bat_Den |
| Bây giờ là mấy giờ | 0.840 | 0.000 | 0.160 | Bat_Den |

Kết quả: **26/30 (86.7%)** false acceptance. Các file này mang split `training_candidate`, speaker `piper_vi_VN_vais1000`, session `synthetic_hardneg_001`; chúng không được đưa vào test hiện tại.

## Thiết kế dữ liệu v5 đề xuất

1. Thu tối thiểu 5 người nói, ít nhất 2 phiên/người, tách ngày/phòng hoặc thiết bị khi có thể.
2. Mỗi speaker/session: Bat_Den và Tat_Den thật; Unknown gồm câu gần âm vị, câu phủ định/câu hỏi, lệnh thiết bị khác, hội thoại tự nhiên, silence/noise. Không biến Tap_Am thành kho chứa tùy ý; trước tiên xác minh semantic của nhãn này.
3. Gán `speaker_id`, `session_id`, nội dung, nguồn, giấy phép và hash WAV trong manifest. Không suy speaker từ filename.
4. Chia theo speaker trước khi cắt/augment: training khoảng 60%, validation 20%, test 20%; toàn bộ session của một speaker chỉ thuộc một split.
5. 9 false acceptance và filter test hiện tại tiếp tục là test-only. Không dùng chúng để train rồi báo kết quả trên chính chúng.

## So sánh cấu hình

| Thành phần | Deployment 4 baseline | Phương án v5 |
|---|---|---|
| DSP | MFE impl.4, 40 filters, FFT256 | Giữ nguyên để cô lập tác động dữ liệu |
| Nhãn | Bat_Den, Tap_Am, Tat_Den, Unknown | Giữ thứ tự; làm rõ Tap_Am |
| Unknown | Không audit được; thực nghiệm cho thấy thiếu speech ngoài lệnh | Bổ sung hard negatives đa speaker/session |
| Bat_Den local | 0 WAV thật | Thu cân bằng với Tat_Den |
| Split | Không xác minh được | Speaker/session-disjoint |
| Quyết định triển khai | Baseline đang chạy | Chỉ khi test độc lập giảm FAR và FRR không tăng đáng kể |

## Trạng thái huấn luyện

Không có model v5 được huấn luyện: chưa đủ đa người nói, chưa có training dataset gốc để tạo bản sao tương đương, và không có phiên Edge Impulse/CLI khả dụng. Vì vậy không có metric sau huấn luyện và không có thay đổi deployment. Validation accuracy sẽ không được dùng thay cho FAR/FRR trên test speaker-disjoint.

## Artifacts

- Baseline đóng băng: `training_experiments/v5_hard_negatives/BASELINE.json`.
- Manifest training candidates: `training_experiments/v5_hard_negatives/hard_negative_manifest.csv`.
- Baseline challenge results: `training_experiments/v5_hard_negatives/baseline_hard_negative_results.csv`.
- Phân tích 9 false accepts: `hard_negative_analysis/false_acceptance_analysis.csv`.
- MFE vectors đầy đủ: `hard_negative_analysis/mfe_vectors.csv`.
- Inventory dữ liệu local: `hard_negative_analysis/local_dataset_inventory.csv`.
