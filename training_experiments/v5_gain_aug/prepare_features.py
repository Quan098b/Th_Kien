"""Build MFE feature sets for the v5 gain-augmentation experiment.

Features come from laptop_model_test/sdk/build/mfe_bin.exe, i.e. the exact
deployment 4 MFE block, so a model trained here sees the same inputs as on ESP.

Sets written to work/features/<name>.f32 + <name>.csv:
  train_plain   EI training split, original level (all-zero clips removed)
  train_aug     EI training split, original + N random gain/noise/shift copies
  test_orig     EI testing split, original level
  test_rms200   EI testing split scaled to RMS 200 (INMP441 level)
  test_rms200n  as above + Gaussian noise std 12 (ESP noise floor)
  test_rms4500  EI testing split scaled to RMS 4500 (phone level)
  ext           filter_evaluation WAVs (not in EI training), with gate_pass
"""
import argparse, csv, re, subprocess, wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
MFE_BIN = PROJECT / "laptop_model_test/sdk/build/mfe_bin.exe"
N = 24000


def read(path):
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)


def write(path, v):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(np.clip(np.round(v), -32768, 32767).astype(np.int16).tobytes())


def to_rms(v, target):
    r = np.sqrt(np.mean(v ** 2))
    return v * (target / r) if r > 0 else v


def augment(v, rng):
    shift = int(rng.integers(-1600, 1601))
    v = np.roll(v, shift)
    if shift > 0: v[:shift] = 0
    elif shift < 0: v[shift:] = 0
    v = to_rms(v, float(np.exp(rng.uniform(np.log(60), np.log(6000)))))
    return v + rng.normal(0, float(np.exp(rng.uniform(np.log(2), np.log(25)))), N)


def extract(name, rows, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    lst = out_dir / f"{name}.txt"
    lst.write_text("\n".join(str(r["wav"]) for r in rows) + "\n", encoding="utf-8")
    res = subprocess.run([str(MFE_BIN), str(lst), str(out_dir / f"{name}.f32")],
                         capture_output=True, text=True)
    if res.returncode:
        raise SystemExit(res.stderr)
    with (out_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"{name:14s} {res.stdout.strip()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export-wav", type=Path,
                    default=Path(r"C:\Users\khanh\Desktop\AIThKien\vudieuanhsang-export-wav"))
    ap.add_argument("--copies", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20261023)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    work, feats = HERE / "work", HERE / "work/features"

    manifest = list(csv.DictReader((a.export_wav / "manifest.csv").open(encoding="utf-8")))
    infer = a.export_wav / "infer"
    train = [m for m in manifest if m["split"] == "training" and m["all_zero"] == "0"]
    test = [m for m in manifest if m["split"] == "testing"]
    print(f"train={len(train)} (dropped {sum(m['all_zero'] == '1' for m in manifest)} all-zero) test={len(test)}")

    plain, aug = [], []
    for m in train:
        src = infer / "training" / m["label"] / f"{m['name']}.wav"
        base = {"label": m["label"], "device": m["device_name"], "source": m["name"]}
        plain.append({**base, "wav": src, "copy": 0})
        aug.append({**base, "wav": src, "copy": 0})
        v = read(src)
        for k in range(1, a.copies + 1):
            dst = work / "aug_wav" / m["label"] / f"{m['name']}_a{k}.wav"
            write(dst, augment(v.copy(), rng)); aug.append({**base, "wav": dst, "copy": k})
    extract("train_plain", plain, feats)
    extract("train_aug", aug, feats)

    noise_rng = np.random.default_rng(a.seed + 1)
    for name, fn in [("test_orig", None),
                     ("test_rms200", lambda v: to_rms(v, 200)),
                     ("test_rms200n", lambda v: to_rms(v, 200) + noise_rng.normal(0, 12, N)),
                     ("test_rms4500", lambda v: to_rms(v, 4500))]:
        rows = []
        for m in test:
            src = infer / "testing" / m["label"] / f"{m['name']}.wav"
            wav = src
            if fn:
                wav = work / name / m["label"] / f"{m['name']}.wav"; write(wav, fn(read(src)))
            rows.append({"label": m["label"], "device": m["device_name"], "source": m["name"], "wav": wav})
        extract(name, rows, feats)

    # External set: filter_evaluation WAVs; drop Tat_Den files that EI used for training.
    ei_train_tat = {re.search(r"(Tat_Den_\d{8}_\d{6}_\d+)", m["name"]).group(1)
                    for m in train if m["label"] == "Tat_Den"}
    ext, leaked = [], 0
    for r in csv.DictReader((PROJECT / "filter_evaluation/filter_results.csv").open(encoding="utf-8")):
        stem = Path(r["file"]).stem
        if stem in ei_train_tat:
            leaked += 1; continue
        ext.append({"label": r["expected"], "device": r["group"], "source": stem,
                    "wav": Path(r["file"]), "gate_pass": r["gate_pass"],
                    "dep4_pred": r["predicted"], "split": r["split"]})
    print(f"ext: kept {len(ext)}, dropped {leaked} Tat_Den files present in EI training")
    extract("ext", ext, feats)


if __name__ == "__main__":
    main()
