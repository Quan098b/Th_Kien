"""Convert an Edge Impulse data export (JSON samples) to WAV.

Writes two trees under OUT_DIR:
  listen/<split>/<label>/<name>.wav   original length, for listening
  infer/<split>/<label>/<name>.wav    exactly 24000 samples (loudest 1.5 s window)
and a manifest.csv describing every file.
"""
import argparse, array, csv, json, math, wave
from pathlib import Path

WINDOW = 24000
SR = 16000


def write_wav(path, samples):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(array.array("h", samples).tobytes())


def loudest_window(v):
    if len(v) <= WINDOW:
        return v + [0] * (WINDOW - len(v)), 0
    step = SR // 100
    energy = [sum(x * x for x in v[i:i + step]) for i in range(0, len(v), step)]
    span = WINDOW // step
    best = max(range(len(energy) - span + 1), key=lambda k: sum(energy[k:k + span]))
    start = best * step
    return v[start:start + WINDOW], start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    a = ap.parse_args()
    index = json.loads((a.export_dir / "info.labels").read_text(encoding="utf-8"))
    rows = []
    for item in index["files"]:
        payload = json.loads((a.export_dir / item["path"]).read_text(encoding="utf-8"))["payload"]
        v = payload["values"]
        if v and isinstance(v[0], list):
            v = [x[0] for x in v]
        v = [max(-32768, min(32767, int(x))) for x in v]
        if round(1000.0 / payload["interval_ms"]) != SR:
            raise SystemExit(f"unexpected sample rate in {item['path']}")
        split, label = item["category"], item["label"]["label"]
        stem = item["name"].replace("/", "_")
        write_wav(a.out_dir / "listen" / split / label / f"{stem}.wav", v)
        win, start = loudest_window(v)
        write_wav(a.out_dir / "infer" / split / label / f"{stem}.wav", win)
        rms = math.sqrt(sum(x * x for x in win) / WINDOW)
        rows.append({"split": split, "label": label, "name": stem,
                     "device_name": payload.get("device_name", ""),
                     "orig_samples": len(v), "window_start": start,
                     "window_rms": round(rms, 1), "all_zero": int(not any(v))})
    with (a.out_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"wrote {len(rows)} samples to {a.out_dir}")


if __name__ == "__main__":
    main()
