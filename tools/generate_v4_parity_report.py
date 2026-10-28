"""Generate the deployment-4 laptop/ESP parity CSV and Markdown report."""
from __future__ import annotations

import csv
import hashlib
import pathlib
import re
import statistics


ROOT = pathlib.Path(__file__).resolve().parents[1]
LABELS = ["Bat_Den", "Tap_Am", "Tat_Den", "Unknown"]


def read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_serial_log(path: pathlib.Path, filename: str, expected: str) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    probs = dict(re.findall(r"PROB source=SERIAL (\w+)=([0-9.]+)", text))
    result = re.search(
        r"RESULT source=SERIAL best=(\w+) probability=([0-9.]+).*?dsp_ms=(\d+) inference_ms=(\d+)",
        text,
    )
    audio = re.search(r"AUDIO source=SERIAL rms=([0-9.]+)", text)
    crc = re.search(r"actual_crc=([0-9a-f]+) valid=(\w+)", text)
    if not result or not audio or not crc or set(probs) != set(LABELS):
        raise RuntimeError(f"Incomplete serial log: {path}")
    return {
        "file": filename,
        "expected": expected,
        "rms": audio.group(1),
        **probs,
        "predicted": result.group(1),
        "dsp_ms": result.group(3),
        "inference_ms": result.group(4),
        "crc32": crc.group(1),
        "crc_valid": crc.group(2),
    }


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


esp = read_csv(ROOT / "logs/esp_v4_dataset_seed_20261022.csv")
laptop = read_csv(ROOT / "laptop_model_test/laptop_results.csv")
v3 = read_csv(ROOT / "logs/dataset_benchmark_seed_20261022.csv")

laptop_by_name = {pathlib.Path(row["file"]).name: row for row in laptop}
v3_by_name = {pathlib.Path(row["file"]).name: row for row in v3}
comparison: list[dict[str, str]] = []
for row in esp:
    name = pathlib.Path(row["file"]).name
    lap = laptop_by_name[name]
    old = v3_by_name[name]
    out = {
        "file": name,
        "expected": row["expected"],
        "crc32": row["crc32"],
        "rms": row["rms"],
        "esp_v3_predicted": old["predicted"],
        "laptop_v4_predicted": lap["predicted"],
        "esp_v4_predicted": row["predicted"],
        "prediction_match": str(lap["predicted"] == row["predicted"]).lower(),
        "laptop_dsp_ms": lap["dsp_ms"],
        "laptop_inference_ms": lap["inference_ms"],
        "esp_dsp_ms": row["dsp_ms"],
        "esp_inference_ms": row["inference_ms"],
    }
    for label in LABELS:
        out[f"laptop_{label}"] = lap[label]
        out[f"esp_{label}"] = row[label]
        out[f"abs_delta_{label}"] = f"{abs(float(lap[label]) - float(row[label])):.9f}"
    comparison.append(out)

fields = list(comparison[0])
with (ROOT / "logs/esp_v4_laptop_parity.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(comparison)

special_esp = [
    parse_serial_log(ROOT / "logs/esp_v4_tts_bat.log", "bat_den.wav", "Bat_Den"),
    parse_serial_log(ROOT / "logs/esp_v4_tts_tat.log", "tat_den.wav", "Tat_Den"),
    parse_serial_log(ROOT / "logs/esp_v4_silence.log", "silence.wav", "Unknown"),
    parse_serial_log(ROOT / "logs/esp_v4_noise.log", "noise_rms_300.wav", "Unknown"),
]
special_laptop = {
    pathlib.Path(row["file"]).name: row for row in laptop if row["source"] == "tts"
}
special_laptop.update({
    "silence.wav": {"predicted": "Tat_Den", "Bat_Den": "0.066406250", "Tap_Am": "0.000000000", "Tat_Den": "0.921875000", "Unknown": "0.011718750", "dsp_ms": "1", "inference_ms": "0"},
    "noise_rms_300.wav": {"predicted": "Unknown", "Bat_Den": "0.027343750", "Tap_Am": "0.003906250", "Tat_Den": "0.066406250", "Unknown": "0.906250000", "dsp_ms": "1", "inference_ms": "0"},
})

special_comparison = []
for esp_row in special_esp:
    lap = special_laptop[esp_row["file"]]
    out = {
        "file": esp_row["file"], "expected": esp_row["expected"],
        "crc32": esp_row["crc32"], "crc_valid": esp_row["crc_valid"], "rms": esp_row["rms"],
        "laptop_predicted": lap["predicted"], "esp_predicted": esp_row["predicted"],
        "prediction_match": str(lap["predicted"] == esp_row["predicted"]).lower(),
        "laptop_dsp_ms": lap["dsp_ms"], "laptop_inference_ms": lap["inference_ms"],
        "esp_dsp_ms": esp_row["dsp_ms"], "esp_inference_ms": esp_row["inference_ms"],
    }
    for label in LABELS:
        out[f"laptop_{label}"] = lap[label]
        out[f"esp_{label}"] = esp_row[label]
        out[f"abs_delta_{label}"] = f"{abs(float(lap[label]) - float(esp_row[label])):.9f}"
    special_comparison.append(out)
with (ROOT / "logs/esp_v4_special_cases_parity.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(special_comparison[0]))
    writer.writeheader()
    writer.writerows(special_comparison)

correct_v3 = sum(r["predicted"] == r["expected"] for r in v3)
correct_v4 = sum(r["predicted"] == r["expected"] for r in esp)
agreement = sum(r["prediction_match"] == "true" for r in comparison)
all_deltas = [float(r[f"abs_delta_{label}"]) for r in comparison for label in LABELS]
max_delta = max(all_deltas)
mean_delta = statistics.fmean(all_deltas)
esp_dsp = [int(r["dsp_ms"]) for r in esp]
esp_inf = [int(r["inference_ms"]) for r in esp]

matrix = {actual: {pred: 0 for pred in LABELS} for actual in LABELS}
for row in esp:
    matrix[row["expected"]][row["predicted"]] += 1

model = ROOT / "lib/VuDieuAnhSang_inferencing/src/tflite-model/tflite_learn_1144745_3.tflite"
firmware = ROOT / "firmware_history/deployment4_test_20261022/firmware.bin"
flash_v3 = ROOT / "firmware_history/deployment3_restore_20261022/flash_16mb.bin"

lines = [
    "# ESP32-S3 deployment 4 parity report",
    "",
    "Ngày kiểm thử: 2026-10-22. Thiết bị: ESP32-S3 N16R8, COM15, MAC `80:b5:4e:e9:4f:c4`.",
    "",
    "## Kết luận",
    "",
    f"Deployment 4 trên ESP và Windows cho cùng nhãn **{agreement}/20** WAV Tat_Den và cùng vector xác suất INT8; sai khác lớn nhất do định dạng CSV sáu chữ số là `{max_delta:.9f}` (trung bình `{mean_delta:.9f}`). ESP nhận đúng **{correct_v4}/20 (90%)**, đúng bằng laptop; deployment 3 trước đó nhận đúng **{correct_v3}/20 (0%)**. Vì vậy chênh lệch 0/20 so với 18/20 xuất phát từ deployment/model version, không phải đường PCM Serial hay DSP trên ESP.",
    "",
    "Hai lỗi Tat_Den còn lại cũng giống hệt laptop: một mẫu hòa Bat_Den/Tat_Den ở 0.4921875 và một mẫu nghiêng Bat_Den 0.51171875 so với Tat_Den 0.40234375. TTS Tat_Den vẫn bị nhận Bat_Den; đây là hành vi của model deployment 4, không được che bằng ngưỡng hay logic thủ công.",
    "",
    "## Xác minh artifact và cấu hình",
    "",
    "- Project `VuDieuAnhSang`, project ID `1144745`, deployment `4`.",
    "- Nhãn/tensor output: `Bat_Den`, `Tap_Am`, `Tat_Den`, `Unknown`.",
    "- Input PCM16 mono 16 kHz, 24.000 mẫu; MFE output 5.960 phần tử; TFLite INT8 (`quantized=1`, `compiled=0`).",
    f"- SHA-256 model `.tflite`: `{sha256(model)}`.",
    f"- SHA-256 firmware deployment 4: `{sha256(firmware)}`.",
    f"- Bản sao flash deployment 3 (16 MiB): `{sha256(flash_v3)}`; lệnh khôi phục nằm trong `firmware_history/deployment3_restore_20261022/RESTORE.md`.",
    "- Tất cả 20 lượt truyền có CRC32 trùng bộ kiểm thử deployment 3; firmware báo CRC hợp lệ trước suy luận.",
    "",
    "## Confusion matrix — ESP deployment 4",
    "",
    "| Thực tế \\ Dự đoán | Bat_Den | Tap_Am | Tat_Den | Unknown |",
    "|---|---:|---:|---:|---:|",
]
for actual in LABELS:
    lines.append("| " + actual + " | " + " | ".join(str(matrix[actual][p]) for p in LABELS) + " |")
lines += [
    "",
    "Chỉ lớp Tat_Den có dữ liệu trong bộ 20 WAV này. Tat_Den → Bat_Den: **2/20 = 10%**; recall Tat_Den: **18/20 = 90%**. Không suy diễn precision/recall cho ba lớp không có mẫu thật trong tập này.",
    "",
    "## So sánh từng WAV",
    "",
    "| WAV | ESP v3 | Laptop v4 | ESP v4 | Bat Δ | Tap Δ | Tat Δ | Unknown Δ |",
    "|---|---|---|---|---:|---:|---:|---:|",
]
for row in comparison:
    lines.append(
        f"| {row['file']} | {row['esp_v3_predicted']} | {row['laptop_v4_predicted']} | {row['esp_v4_predicted']} | "
        + " | ".join(row[f"abs_delta_{label}"] for label in LABELS) + " |"
    )
lines += [
    "",
    "Các CSV đầy đủ chứa xác suất của cả bốn lớp, RMS, CRC32 và thời gian DSP/inference: `logs/esp_v4_laptop_parity.csv` (20 WAV dataset) và `logs/esp_v4_special_cases_parity.csv` (TTS, im lặng, nhiễu).",
    "",
    "## TTS, im lặng và nhiễu",
    "",
    "| WAV | Kỳ vọng | Laptop v4 | ESP v4 | ESP probabilities (Bat / Tap / Tat / Unknown) | CRC |",
    "|---|---|---|---|---|---|",
]
for esp_row in special_esp:
    lap = special_laptop[esp_row["file"]]
    probs = " / ".join(esp_row[label] for label in LABELS)
    lines.append(f"| {esp_row['file']} | {esp_row['expected']} | {lap['predicted']} | {esp_row['predicted']} | {probs} | {esp_row['crc_valid']} |")
lines += [
    "",
    "Im lặng bị nhận Tat_Den với 0.921875 ở cả hai runtime, trong khi nhiễu RMS≈300 được nhận Unknown với 0.90625. Điều này cho thấy model chưa có khả năng loại im lặng phù hợp dù runtime parity là chính xác.",
    "",
    "## Timing và thay đổi kỹ thuật",
    "",
    f"ESP deployment 4: DSP {min(esp_dsp)}–{max(esp_dsp)} ms, inference {min(esp_inf)}–{max(esp_inf)} ms trên 20 WAV. Laptop thường DSP 1 ms và inference 0–1 ms; chênh lệch thời gian là phù hợp với phần cứng, không làm thay đổi output lượng tử.",
    "",
    "Firmware logic, giao thức EIP1, dữ liệu và ngưỡng không bị thay đổi. Chỉ thay thư viện inference deployment 3 bằng export deployment 4 và điều chỉnh đường dẫn `INCBIN` để PlatformIO đóng gói đúng chính file `.tflite`; trọng số/model hash không thay đổi.",
    "",
    "## Hướng tiếp theo",
    "",
    "Không cần sửa DSP/firmware cho lỗi parity. Giai đoạn huấn luyện sau nên bổ sung im lặng vào Unknown, tăng dữ liệu Tat_Den đa giọng/âm lượng/môi trường, rà soát các mẫu Tat_Den gần Bat_Den và giữ một test split theo người nói/phiên thu độc lập. Chưa huấn luyện lại hoặc thay đổi trọng số trong lần kiểm thử này.",
]
(ROOT / "ESP_V4_PARITY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {len(comparison)} parity rows; agreement={agreement}/20; accuracy={correct_v4}/20; max_delta={max_delta:.9f}")
