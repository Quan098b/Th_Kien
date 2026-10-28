"""Check whether deployment 4 predictions depend on input loudness.

Runs laptop_infer.exe on each WAV at its original level and rescaled to
fixed RMS targets, then prints a confusion summary per condition.
"""
import argparse, array, csv, math, subprocess, wave
from collections import Counter, defaultdict
from pathlib import Path

LABELS = ["Bat_Den", "Tap_Am", "Tat_Den", "Unknown"]


def read(path):
    with wave.open(str(path), "rb") as w:
        return list(array.array("h", w.readframes(w.getnframes())))


def write(path, v):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(array.array("h", v).tobytes())


def scaled(v, target):
    rms = math.sqrt(sum(x * x for x in v) / len(v))
    g = target / rms if rms else 0.0
    return [max(-32768, min(32767, round(x * g))) for x in v]


def infer(exe, paths):
    out = {}
    for i in range(0, len(paths), 40):
        res = subprocess.run([str(exe)] + [str(p) for p in paths[i:i + 40]],
                             capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            if not line.startswith("FILE\t"):
                continue
            parts = line.split("\t")
            kv = dict(p.split("=", 1) for p in parts[2:] if "=" in p)
            out[Path(parts[1]).resolve()] = kv
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infer_dir", type=Path, help="infer/<split> folder with <label>/*.wav")
    ap.add_argument("work_dir", type=Path)
    ap.add_argument("out_csv", type=Path)
    ap.add_argument("--exe", type=Path, default=Path("laptop_model_test/sdk/build/laptop_infer.exe"))
    ap.add_argument("--targets", default="200,4500")
    a = ap.parse_args()

    src = sorted(a.infer_dir.glob("*/*.wav"))
    conds = {"orig": {p: p for p in src}}
    for t in [int(x) for x in a.targets.split(",")]:
        m = {}
        for p in src:
            v = read(p)
            if not any(v):
                continue
            q = a.work_dir / f"rms{t}" / p.parent.name / p.name
            write(q, scaled(v, t)); m[p] = q
        conds[f"rms{t}"] = m

    rows = []
    for cond, mapping in conds.items():
        res = infer(a.exe, list(mapping.values()))
        for p, q in mapping.items():
            kv = res[q.resolve()]
            rows.append({"condition": cond, "true": p.parent.name, "file": p.name,
                         "rms": kv["rms"], "predicted": kv["predicted"],
                         **{l: kv[l] for l in LABELS}})

    with a.out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    for cond in conds:
        print(f"\n== {cond} ==  (rows=true, cols=predicted)")
        cm = defaultdict(Counter)
        for r in rows:
            if r["condition"] == cond:
                cm[r["true"]][r["predicted"]] += 1
        print(f"{'':10s}" + "".join(f"{l:>9s}" for l in LABELS) + "   acc")
        for t in LABELS:
            n = sum(cm[t].values())
            print(f"{t:10s}" + "".join(f"{cm[t][l]:9d}" for l in LABELS)
                  + f"  {cm[t][t] / n:5.1%}" if n else "")


if __name__ == "__main__":
    main()
