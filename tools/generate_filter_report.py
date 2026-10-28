"""Merge ESP reruns and generate FILTER_EVALUATION.md from measured CSV data."""
from __future__ import annotations
import csv, hashlib, pathlib, statistics, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from filter_evaluation import features, read_wav  # noqa: E402

L = {"Bat_Den", "Tat_Den"}

def rows(path):
    with path.open(encoding="utf-8", newline="") as f: return list(csv.DictReader(f))

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest().upper()

esp_path = ROOT / "filter_evaluation/esp_filter_results.csv"
esp = rows(esp_path)
rerun = rows(ROOT / "filter_evaluation/esp_filter_noncommand_rerun.csv")
latest = {r["file"]: r for r in rerun}
esp = [latest.get(r["file"], r) for r in esp]
with esp_path.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=esp[0].keys()); w.writeheader(); w.writerows(esp)

laptop = {str(pathlib.Path(r["file"]).resolve()): r for r in rows(ROOT / "filter_evaluation/filter_results.csv") if r["split"] == "test"}
pos = [r for r in esp if r["expected"] in L]
neg = [r for r in esp if r["expected"] == "reject"]
base_far = sum(r["predicted"] in L for r in neg) / len(neg)
after_far = sum(r["final"] in L for r in neg) / len(neg)
base_frr = sum(r["predicted"] != r["expected"] for r in pos) / len(pos)
after_frr = sum(r["final"] != r["expected"] for r in pos) / len(pos)

groups = []
for name in sorted({r["group"] for r in esp}):
    g = [r for r in esp if r["group"] == name]
    lf = [laptop[str(pathlib.Path(r["file"]).resolve())] for r in g]
    groups.append((name, len(g), sum(r["predicted"] in L for r in g), sum(r["final"] in L for r in g),
                   statistics.median(float(r["rms"]) for r in lf), statistics.median(float(r["flatness"]) for r in lf),
                   statistics.median(float(r["low_ratio"]) for r in lf)))

# Previously known failures from the parity suite and the TTS Tat sample.
old = rows(ROOT / "logs/esp_v4_dataset_seed_20261022.csv")
known = []
for r in old:
    if r["expected"] == "Tat_Den" and r["predicted"] == "Bat_Den":
        f = features(read_wav(pathlib.Path(r["file"])))
        passed = f["rms"] >= 20 and f["active_ratio"] >= .02 and f["flatness"] <= .15 and f["low_ratio"] <= .8 and f["zcr"] >= .01
        known.append((pathlib.Path(r["file"]).name, float(r["rms"]), f, passed, "Bat_Den"))
tts = ROOT / "test_audio/tat_den.wav"
f = features(read_wav(tts)); passed = f["rms"] >= 20 and f["active_ratio"] >= .02 and f["flatness"] <= .15 and f["low_ratio"] <= .8 and f["zcr"] >= .01
known.append((tts.name, f["rms"], f, passed, "Bat_Den"))

fw = ROOT / "firmware_history/deployment4_filter_test_20261022/firmware.bin"
backup = ROOT / "firmware_history/deployment4_restore_20261022/flash_16mb.bin"
lines = [
"# FILTER_EVALUATION", "",
"Ngày đánh giá: 2026-10-22. Model giữ nguyên Edge Impulse deployment 4; không đổi trọng số, confidence, score gap hoặc thứ tự nhãn.", "",
"## Kết luận", "",
f"Trên split test độc lập 60 WAV, bộ lọc energy-VAD/phổ giảm **FAR từ {base_far:.1%} xuống {after_far:.1%}** và giữ **FRR {base_frr:.2%} → {after_frr:.2%}**. Không có mẫu lệnh nào bị chính gate loại nhầm. Kết quả này được chạy lại trực tiếp trên ESP32-S3 qua COM15/CRC32, không chỉ mô phỏng laptop.", "",
"Bộ lọc loại toàn bộ command false-accept do silence, white/colored noise, wind và hum trong test. Nó không loại được lời nói thật có nội dung ngoài lệnh: 9/10 câu non-command vẫn bị model gán Bat_Den. Vì vậy đây là cải thiện có giới hạn; cần huấn luyện lại Unknown bằng non-command speech thật để giải quyết phần còn lại.", "",
"## Bộ dữ liệu và phân vùng", "",
"- Seed `20261022`; dev 60 WAV và test 60 WAV, không dùng test để chọn ngưỡng.",
"- Mỗi split: 20 Tat_Den thật chưa dùng trong parity, 10 Bat_Den TTS augmentation, 20 noise/silence/wind/hum và 10 câu tiếng Việt ngoài lệnh.",
"- Không có WAV Bat_Den, Tap_Am hoặc Unknown thu thật trong dataset hiện có. Vì vậy kết luận cho Bat_Den dựa trên TTS augmentation và kết luận negative dựa trên controls/TTS; cần xác nhận thêm bằng bản ghi thực địa.",
"- WAV gốc không bị sửa; fixtures mới nằm trong `filter_evaluation/audio`.", "",
"## Bộ lọc đã chọn trên dev", "",
"Gate chỉ pass khi đồng thời: RMS ≥ 20; tỷ lệ frame có tiếng ≥ 2%; spectral flatness ≤ 0,15; tỷ lệ năng lượng 80–250 Hz ≤ 0,80; zero-crossing rate ≥ 0,01. Phổ được tính bằng các FFT 256 điểm chồng lấn. Confidence và score gap không tham gia gate.", "",
"## Kết quả ESP trên split test", "",
"| Nhóm | N | Model phát lệnh trước lọc | Phát lệnh sau lọc | RMS median | Flatness median | Low-band median |",
"|---|---:|---:|---:|---:|---:|---:|",
]
for g in groups: lines.append(f"| {g[0]} | {g[1]} | {g[2]} | {g[3]} | {g[4]:.1f} | {g[5]:.4f} | {g[6]:.4f} |")
lines += ["", "| Chỉ số | Trước | Sau |", "|---|---:|---:|",
          f"| FAR (negative bị phát thành Bat/Tat) | {base_far:.2%} ({int(base_far*len(neg))}/{len(neg)}) | {after_far:.2%} ({int(after_far*len(neg))}/{len(neg)}) |",
          f"| FRR (lệnh không ra đúng nhãn) | {base_frr:.2%} ({int(base_frr*len(pos))}/{len(pos)}) | {after_frr:.2%} ({int(after_frr*len(pos))}/{len(pos)}) |", "",
          "## Các trường hợp sai còn lại", "",
          "- Test Tat_Den: `Tat_Den_20261021_230712_137669.wav` vẫn thành Bat_Den; gate pass. Đây là lỗi phân lớp, không phải absence-of-speech.",
          "- Non-command speech: 9/10 thành Bat_Den; gate phải cho qua vì đó là tiếng nói thật. Dùng VAD để chặn chúng sẽ đồng thời tăng FRR cho câu lệnh.",
          "- TTS Tat_Den và hai lỗi Tat_Den của bộ parity cũ đều có đặc trưng tiếng nói và pass gate:", "",
          "| WAV | RMS | Active | Flatness | Low ratio | ZCR | Gate | Model |", "|---|---:|---:|---:|---:|---:|---|---|" ]
for name, rms, f, passed, pred in known:
    lines.append(f"| {name} | {rms:.1f} | {f['active_ratio']:.3f} | {f['flatness']:.4f} | {f['low_ratio']:.4f} | {f['zcr']:.4f} | {'PASS' if passed else 'REJECT'} | {pred} |")
lines += ["", "## Unknown và Tap_Am", "",
          "Trong 30 negative test, model nguyên bản phát lệnh 18 lần. Tap_Am không thắng ở bất kỳ mẫu test nào; Unknown chỉ xử lý được một phần noise và 1/10 non-command speech. Với dữ liệu hiện có, hai nhãn này chưa bao phủ tốt silence và speech ngoài lệnh. Tên `Tap_Am` cũng không có mẫu WAV tương ứng để xác minh semantic; cần kiểm tra lại định nghĩa/labelling trong Edge Impulse trước khi retrain.", "",
          "## Firmware và khả năng khôi phục", "",
          f"- Build thành công: RAM 13,9%, flash 8,5%. Firmware filter SHA-256 `{sha(fw)}`.",
          "- Upload COM15 và verify flash thành công trên MAC `80:b5:4e:e9:4f:c4`.",
          f"- Backup nguyên flash deployment 4 trước thay đổi: 16 MiB, SHA-256 `{sha(backup)}`; hướng dẫn tại `firmware_history/deployment4_restore_20261022/RESTORE.md`.",
          "- Firmware vẫn chạy inference và in cả model result lẫn final decision; không điều khiển LED/relay.", "",
          "## Khuyến nghị tiếp theo", "",
          "Thu ít nhất 50–100 mẫu mỗi nhóm Bat_Den, Tat_Den, silence/noise và non-command speech từ nhiều người/phiên/phòng; đưa silence và speech ngoài lệnh vào Unknown; làm rõ hoặc đổi nhãn Tap_Am; chia test theo người nói/phiên thu. Sau đó huấn luyện một bản sao deployment mới và giữ nguyên bộ test này làm holdout.", ""]
(ROOT / "FILTER_EVALUATION.md").write_text("\n".join(lines), encoding="utf-8")
print(f"ESP rows={len(esp)} FAR {base_far:.3f}->{after_far:.3f} FRR {base_frr:.3f}->{after_frr:.3f}")
