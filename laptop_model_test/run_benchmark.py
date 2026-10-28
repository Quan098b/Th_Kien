"""Run deployment 4 on the exact ESP benchmark manifest plus the two TTS WAVs."""
from __future__ import annotations
import csv, json, os, pathlib, subprocess

root = pathlib.Path(__file__).resolve().parents[1]
manifest = root / "logs/dataset_benchmark_seed_20261022.csv"
exe = pathlib.Path(__file__).parent / "sdk/build/laptop_infer.exe"
rows_v3 = list(csv.DictReader(manifest.open(encoding="utf-8")))
cases = [(pathlib.Path(r["file"]), r["expected"], "dataset") for r in rows_v3]
cases += [(root / "test_audio/bat_den.wav", "Bat_Den", "tts"),
          (root / "test_audio/tat_den.wav", "Tat_Den", "tts")]
env = os.environ.copy()
mingw = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Microsoft/WinGet/Packages/BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe/mingw64/bin"
env["PATH"] = str(mingw) + os.pathsep + env.get("PATH", "")
run = subprocess.run([str(exe), *map(lambda c: str(c[0]), cases)], cwd=exe.parent.parent,
                     env=env, text=True, encoding="utf-8", capture_output=True, check=True)
(pathlib.Path(__file__).parent / "laptop_raw_output.txt").write_text(run.stdout, encoding="utf-8")
parsed = []
case_by_path = {str(p): (expected, source) for p, expected, source in cases}
for line in run.stdout.splitlines():
    if not line.startswith("FILE\t"): continue
    parts = line.split("\t"); path = parts[1]
    values = dict(field.split("=", 1) for field in parts[2:])
    expected, source = case_by_path[path]
    parsed.append({"file": path, "source": source, "expected": expected, **values})
fields = ["file", "source", "expected", "rms", "min", "max", "clipped", "Bat_Den", "Tap_Am", "Tat_Den", "Unknown", "predicted", "dsp_ms", "inference_ms"]
with (pathlib.Path(__file__).parent / "laptop_results.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(parsed)

labels = ["Bat_Den", "Tap_Am", "Tat_Den", "Unknown"]
dataset_rows = [r for r in parsed if r["source"] == "dataset"]
matrix = {a: {p: 0 for p in labels} for a in labels}
for r in dataset_rows: matrix[r["expected"]][r["predicted"]] += 1
summary = {
    "dataset_count": len(dataset_rows), "tts_count": len(parsed) - len(dataset_rows),
    "dataset_accuracy": sum(r["expected"] == r["predicted"] for r in dataset_rows) / len(dataset_rows),
    "confusion_matrix": matrix,
    "tat_den_to_bat_den": matrix["Tat_Den"]["Bat_Den"] / sum(matrix["Tat_Den"].values()),
}
(pathlib.Path(__file__).parent / "laptop_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
v4_by_file = {pathlib.Path(r["file"]).name: r for r in dataset_rows}
comparison = []
for old in rows_v3:
    new = v4_by_file[pathlib.Path(old["file"]).name]
    comparison.append({
        "file": pathlib.Path(old["file"]).name, "expected": old["expected"],
        "esp_deploy3_predicted": old["predicted"], "laptop_deploy4_predicted": new["predicted"],
        **{f"esp_v3_{label}": old[label] for label in labels},
        **{f"laptop_v4_{label}": new[label] for label in labels},
    })
with (pathlib.Path(__file__).parent / "esp_v3_vs_laptop_v4.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=comparison[0].keys()); writer.writeheader(); writer.writerows(comparison)
print(json.dumps(summary, indent=2))
