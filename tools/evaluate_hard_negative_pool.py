"""Run frozen deployment 4 against training-only hard-negative candidates."""
from __future__ import annotations
import csv, os, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXP = ROOT / "training_experiments/v5_hard_negatives"
manifest = list(csv.DictReader((EXP / "hard_negative_manifest.csv").open(encoding="utf-8-sig")))
paths = [ROOT / row["file"] for row in manifest]
exe = ROOT / "laptop_model_test/sdk/build/laptop_infer.exe"
mingw = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Microsoft/WinGet/Packages/BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe/mingw64/bin"
env = os.environ.copy(); env["PATH"] = str(mingw) + os.pathsep + env.get("PATH", "")
run = subprocess.run([str(exe), *map(str, paths)], cwd=exe.parent.parent, env=env,
                     text=True, encoding="utf-8", capture_output=True, check=True)
parsed = {}
for line in run.stdout.splitlines():
    if not line.startswith("FILE\t"): continue
    parts = line.split("\t")
    parsed[str(pathlib.Path(parts[1]).resolve())] = dict(p.split("=", 1) for p in parts[2:])
rows = []
for meta, path in zip(manifest, paths): rows.append({**meta, **parsed[str(path.resolve())]})
fields = list(rows[0])
with (EXP / "baseline_hard_negative_results.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
commands = sum(r["predicted"] in ("Bat_Den", "Tat_Den") for r in rows)
print(f"hard negatives classified as command: {commands}/{len(rows)} ({commands/len(rows):.1%})")
