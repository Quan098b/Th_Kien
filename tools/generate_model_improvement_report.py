"""Generate the hard-negative analysis and model-improvement report."""
from __future__ import annotations
import csv, datetime, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
HNA = ROOT / "hard_negative_analysis"
EXP = ROOT / "training_experiments/v5_hard_negatives"

def read(path, encoding="utf-8"):
    with path.open(encoding=encoding, newline="") as f: return list(csv.DictReader(f))

phrases = [
    "xin chào", "hôm nay trời đẹp", "mở cửa sổ", "đóng cửa lại", "bây giờ là mấy giờ",
    "cảm ơn bạn", "tôi đang học bài", "âm nhạc rất hay", "hãy đọc tin tức", "nhiệt độ bao nhiêu",
    "chúc ngủ ngon", "tôi muốn uống nước", "đi ra ngoài", "quạt đang chạy", "đèn ở phòng khách",
    "bật quạt", "tắt quạt", "mở nhạc", "dừng lại", "hãy nói chậm hơn",
]
esp = read(ROOT / "filter_evaluation/esp_filter_results.csv")
mfe = {pathlib.Path(r["file"]).name: r for r in read(HNA / "mfe_summary.csv")}
fa = []
for r in esp:
    if r["group"] != "non_command_speech" or r["final"] not in ("Bat_Den", "Tat_Den"): continue
    name = pathlib.Path(r["file"]).name
    idx = int(re.search(r"(\d+)", name).group(1))
    m = mfe[name]
    fa.append({
        "file": name, "content": phrases[idx], "rms": r["rms"],
        "Bat_Den": r["Bat_Den"], "Tap_Am": r["Tap_Am"], "Tat_Den": r["Tat_Den"], "Unknown": r["Unknown"],
        "predicted": r["predicted"],
        **{k: m[k] for k in ("mfe_mean","mfe_std","mfe_min","mfe_p05","mfe_p50","mfe_p95","mfe_max",
                              "band_00_09","band_10_19","band_20_29","band_30_39","time_first","time_middle","time_last")}
    })
with (HNA / "false_acceptance_analysis.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(fa[0])); w.writeheader(); w.writerows(fa)

dataset = pathlib.Path(r"C:\Users\khanh\Desktop\AIThKien\esp32_microphone_continuous\dataset_inmp441")
inventory = []
for label in ("Bat_Den", "Tat_Den", "Tap_Am", "Unknown"):
    files = sorted((dataset / label).glob("*.wav")) if (dataset / label).exists() else []
    inventory.append({"label": label, "local_wav_count": len(files), "speaker_ids_known": 0,
                      "session_ids_explicit": 0, "usable_for_speaker_disjoint_split": "no"})
with (HNA / "local_dataset_inventory.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(inventory[0])); w.writeheader(); w.writerows(inventory)

challenge = read(EXP / "baseline_hard_negative_results.csv", "utf-8-sig")
command_count = sum(r["predicted"] in ("Bat_Den", "Tat_Den") for r in challenge)
lines = [
"# MODEL_IMPROVEMENT_REPORT", "",
"Ngày phân tích: 2026-10-22. Firmware filter và Edge Impulse deployment 4 được giữ nguyên; không build/upload firmware trong giai đoạn này.", "",
"## Kết luận", "",
"Chưa huấn luyện hoặc đề xuất triển khai model mới. Máy không có Edge Impulse CLI/config đăng nhập và Computer Use không có browser khả dụng; C++ deployment ZIP không chứa training data hay training job configuration. Dữ liệu local cũng chưa đủ: chỉ có 250 WAV Tat_Den, không có WAV thật cho Bat_Den, Tap_Am hoặc Unknown, và không có speaker/session ID đáng tin cậy.", "",
f"Bằng chứng hard-negative rất mạnh: baseline nhận **{command_count}/30 ({command_count/len(challenge):.1%})** câu training-candidate mới thành Bat_Den/Tat_Den. Trong test độc lập trước đó, 9/10 non-command speech thành Bat_Den. Do đó ưu tiên đúng là bổ sung speech hard negatives vào Unknown và thu Bat_Den thật đa người nói, không tối ưu thêm VAD.", "",
"## Chín false acceptance độc lập", "",
"MFE được trích bằng chính `extract_mfe_features` của SDK deployment 4: implementation 4, 40 filter, FFT 256, 5.960 phần tử. Vector đầy đủ nằm tại `hard_negative_analysis/mfe_vectors.csv`.", "",
"| Nội dung | RMS | Bat | Tap | Tat | Unknown | MFE mean | MFE std | P95 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
]
for r in fa:
    lines.append(f"| {r['content']} | {float(r['rms']):.1f} | {float(r['Bat_Den']):.3f} | {float(r['Tap_Am']):.3f} | {float(r['Tat_Den']):.3f} | {float(r['Unknown']):.3f} | {float(r['mfe_mean']):.4f} | {float(r['mfe_std']):.4f} | {float(r['mfe_p95']):.4f} |")
lines += ["", "Cả 9 đều pass VAD và đều bị nhận Bat_Den. Bat_Den nằm trong khoảng 0,617–0,941; Tap_Am luôn 0; Tat_Den 0–0,031. Điều này phù hợp với thiếu hard-negative speech trong vùng âm vị gần “bật/tắt”, không phải lỗi PCM/MFE.", "",
"## Audit dữ liệu hiện có", "",
"| Label | WAV local | Speaker ID | Session ID rõ ràng | Split theo speaker được? |", "|---|---:|---:|---:|---|",
]
for r in inventory: lines.append(f"| {r['label']} | {r['local_wav_count']} | {r['speaker_ids_known']} | {r['session_ids_explicit']} | {r['usable_for_speaker_disjoint_split']} |")
lines += ["", "Các filename Tat_Den chứa timestamp và cho thấy nhiều cụm thời gian, nhưng không chứng minh đó là người nói hay phiên thu độc lập. Không được dùng timestamp làm speaker ID giả. Thành phần training thực tế trên Edge Impulse chưa thể audit từ deployment ZIP.", "",
"## Challenge set mới", "",
"Đã tạo 30 training-only candidates từ Piper `vi_VN-vais1000-medium`, model card ghi một speaker, nguồn VAIS1000, giấy phép CC-BY-4.0. Các câu gồm Bật/Tắt nhạc, quạt, máy, máy lạnh, TV, điện thoại; phủ định; câu hỏi; và lời nói không phải lệnh.", "",
"| Câu | Bat | Tat | Unknown | Dự đoán |", "|---|---:|---:|---:|---|",
]
for r in challenge:
    lines.append(f"| {r['content']} | {float(r['Bat_Den']):.3f} | {float(r['Tat_Den']):.3f} | {float(r['Unknown']):.3f} | {r['predicted']} |")
lines += ["", f"Kết quả: **{command_count}/30 ({command_count/len(challenge):.1%})** false acceptance. Các file này mang split `training_candidate`, speaker `piper_vi_VN_vais1000`, session `synthetic_hardneg_001`; chúng không được đưa vào test hiện tại.", "",
"## Thiết kế dữ liệu v5 đề xuất", "",
"1. Thu tối thiểu 5 người nói, ít nhất 2 phiên/người, tách ngày/phòng hoặc thiết bị khi có thể.",
"2. Mỗi speaker/session: Bat_Den và Tat_Den thật; Unknown gồm câu gần âm vị, câu phủ định/câu hỏi, lệnh thiết bị khác, hội thoại tự nhiên, silence/noise. Không biến Tap_Am thành kho chứa tùy ý; trước tiên xác minh semantic của nhãn này.",
"3. Gán `speaker_id`, `session_id`, nội dung, nguồn, giấy phép và hash WAV trong manifest. Không suy speaker từ filename.",
"4. Chia theo speaker trước khi cắt/augment: training khoảng 60%, validation 20%, test 20%; toàn bộ session của một speaker chỉ thuộc một split.",
"5. 9 false acceptance và filter test hiện tại tiếp tục là test-only. Không dùng chúng để train rồi báo kết quả trên chính chúng.", "",
"## So sánh cấu hình", "",
"| Thành phần | Deployment 4 baseline | Phương án v5 |", "|---|---|---|",
"| DSP | MFE impl.4, 40 filters, FFT256 | Giữ nguyên để cô lập tác động dữ liệu |",
"| Nhãn | Bat_Den, Tap_Am, Tat_Den, Unknown | Giữ thứ tự; làm rõ Tap_Am |",
"| Unknown | Không audit được; thực nghiệm cho thấy thiếu speech ngoài lệnh | Bổ sung hard negatives đa speaker/session |",
"| Bat_Den local | 0 WAV thật | Thu cân bằng với Tat_Den |",
"| Split | Không xác minh được | Speaker/session-disjoint |",
"| Quyết định triển khai | Baseline đang chạy | Chỉ khi test độc lập giảm FAR và FRR không tăng đáng kể |", "",
"## Trạng thái huấn luyện", "",
"Không có model v5 được huấn luyện: chưa đủ đa người nói, chưa có training dataset gốc để tạo bản sao tương đương, và không có phiên Edge Impulse/CLI khả dụng. Vì vậy không có metric sau huấn luyện và không có thay đổi deployment. Validation accuracy sẽ không được dùng thay cho FAR/FRR trên test speaker-disjoint.", "",
"## Artifacts", "",
"- Baseline đóng băng: `training_experiments/v5_hard_negatives/BASELINE.json`.",
"- Manifest training candidates: `training_experiments/v5_hard_negatives/hard_negative_manifest.csv`.",
"- Baseline challenge results: `training_experiments/v5_hard_negatives/baseline_hard_negative_results.csv`.",
"- Phân tích 9 false accepts: `hard_negative_analysis/false_acceptance_analysis.csv`.",
"- MFE vectors đầy đủ: `hard_negative_analysis/mfe_vectors.csv`.",
"- Inventory dữ liệu local: `hard_negative_analysis/local_dataset_inventory.csv`.", ""]
(ROOT / "MODEL_IMPROVEMENT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print(f"wrote report; false_accepts={len(fa)} challenge_command={command_count}/{len(challenge)}")
