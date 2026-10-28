"""Fill deterministic PCM statistics and summarize a serial benchmark CSV."""
from __future__ import annotations
import array, csv, json, math, pathlib, sys, wave

source = pathlib.Path(sys.argv[1])
rows = list(csv.DictReader(source.open(encoding="utf-8")))
for row in rows:
    with wave.open(row["file"], "rb") as wav:
        pcm = wav.readframes(24000)
    samples = array.array("h"); samples.frombytes(pcm)
    row["rms"] = f"{math.sqrt(sum(x*x for x in samples)/len(samples)):.2f}"
    row["pcm_min"], row["pcm_max"] = str(min(samples)), str(max(samples))
    row["clipped"] = str(sum(x in (-32768, 32767) for x in samples))
with source.open("w", newline="", encoding="utf-8") as out:
    writer = csv.DictWriter(out, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)

labels = ["Bat_Den", "Tap_Am", "Tat_Den", "Unknown"]
matrix = {actual: {pred: 0 for pred in labels} for actual in labels}
for row in rows: matrix[row["expected"]][row["predicted"]] += 1
metrics = {}
for label in labels:
    tp = matrix[label][label]
    fp = sum(matrix[a][label] for a in labels if a != label)
    fn = sum(matrix[label][p] for p in labels if p != label)
    support = sum(matrix[label].values())
    precision = tp/(tp+fp) if tp+fp else None
    recall = tp/(tp+fn) if tp+fn else None
    f1 = 2*precision*recall/(precision+recall) if precision is not None and recall is not None and precision+recall else (0.0 if support else None)
    metrics[label] = {"support": support, "precision": precision, "recall": recall, "f1": f1}
summary = {
    "rows": len(rows), "confusion_matrix": matrix, "metrics": metrics,
    "tat_den_to_bat_den": matrix["Tat_Den"]["Bat_Den"] / sum(matrix["Tat_Den"].values()),
    "mean_dsp_ms": sum(int(r["dsp_ms"]) for r in rows)/len(rows),
    "mean_inference_ms": sum(int(r["inference_ms"]) for r in rows)/len(rows),
    "rms_min": min(float(r["rms"]) for r in rows), "rms_max": max(float(r["rms"]) for r in rows),
}
target = source.with_suffix(".summary.json")
target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
