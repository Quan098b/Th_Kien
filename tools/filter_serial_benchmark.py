"""Run the fixed filter-evaluation test split through the ESP32 EIP1 path."""
from __future__ import annotations
import argparse, binascii, csv, pathlib, re, struct, time, wave
import serial

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROB_RE = re.compile(r"PROB source=SERIAL (\S+)=([0-9.]+)")
AUDIO_RE = re.compile(r"AUDIO source=SERIAL rms=([0-9.]+) pcm_min=(-?\d+) pcm_max=(-?\d+) clipped=(\d+)/")
FILTER_RE = re.compile(r"FILTER source=SERIAL pass=(yes|no) active_ratio=([0-9.]+) flatness=([0-9.]+) low_ratio=([0-9.]+) zcr=([0-9.]+)")
RESULT_RE = re.compile(r"RESULT source=SERIAL best=(\S+) probability=([0-9.]+) second=(\S+) margin=([0-9.]+) dsp_ms=(\d+) inference_ms=(\d+)")
DECISION_RE = re.compile(r"DECISION source=SERIAL final=(\S+) model=(\S+) reason=(\S+)")

def pcm(path: pathlib.Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        if w.getparams()[:4] != (1, 2, 16000, 24000): raise ValueError(path)
        return w.readframes(24000)

def wait_line(port: serial.Serial, prefix: str, deadline: float) -> str:
    while time.monotonic() < deadline:
        line = port.readline().decode("utf-8", "replace").strip()
        if line.startswith("TEST_ERROR"): raise RuntimeError(line)
        if line.startswith(prefix): return line
    raise TimeoutError(prefix)

def infer(port: serial.Serial, data: bytes) -> list[str]:
    crc = binascii.crc32(data) & 0xffffffff
    port.reset_input_buffer(); port.write(b"t")
    deadline = time.monotonic() + 45
    wait_line(port, "TEST_READY", deadline)
    port.write(struct.pack("<4sII", b"EIP1", 24000, crc)); port.flush()
    wait_line(port, "TEST_HEADER_READY", deadline)
    for offset in range(0, len(data), 64):
        port.write(data[offset:offset+64]); port.flush(); time.sleep(.006)
    lines = []
    while time.monotonic() < deadline:
        line = port.readline().decode("utf-8", "replace").strip()
        if line: lines.append(line)
        if line == "TEST_END": return lines
        if line.startswith("TEST_ERROR"): raise RuntimeError(line)
    raise TimeoutError("TEST_END")

ap = argparse.ArgumentParser()
ap.add_argument("--port", default="COM15")
ap.add_argument("--split", default="test", choices=("dev", "test", "all"))
ap.add_argument("--group")
ap.add_argument("--output", type=pathlib.Path, default=ROOT / "filter_evaluation/esp_filter_results.csv")
args = ap.parse_args()
source = list(csv.DictReader((ROOT / "filter_evaluation/filter_results.csv").open(encoding="utf-8")))
selected = source if args.split == "all" else [r for r in source if r["split"] == args.split]
if args.group: selected = [r for r in selected if r["group"] == args.group]
fields = ["file", "group", "expected", "split", "crc32", "rms", "active_ratio", "flatness", "low_ratio", "zcr",
          "Bat_Den", "Tap_Am", "Tat_Den", "Unknown", "predicted", "final", "margin", "dsp_ms", "inference_ms"]
args.output.parent.mkdir(parents=True, exist_ok=True)
with serial.Serial(args.port, 115200, timeout=1, write_timeout=5) as port, args.output.open("w", newline="", encoding="utf-8") as out:
    writer = csv.DictWriter(out, fieldnames=fields); writer.writeheader(); time.sleep(.4)
    for i, src in enumerate(selected, 1):
        path = pathlib.Path(src["file"]); data = pcm(path)
        row = {k: src[k] for k in ("file", "group", "expected", "split")}; row["crc32"] = f"{binascii.crc32(data)&0xffffffff:08x}"
        for line in infer(port, data):
            if m := PROB_RE.fullmatch(line): row[m.group(1)] = m.group(2)
            elif m := AUDIO_RE.match(line): row["rms"] = m.group(1)
            elif m := FILTER_RE.match(line):
                row.update(active_ratio=m.group(2), flatness=m.group(3), low_ratio=m.group(4), zcr=m.group(5))
            elif m := RESULT_RE.match(line):
                row.update(predicted=m.group(1), margin=m.group(4), dsp_ms=m.group(5), inference_ms=m.group(6))
            elif m := DECISION_RE.match(line): row["final"] = m.group(1)
        writer.writerow(row); out.flush()
        print(f"[{i}/{len(selected)}] {path.name} expected={row['expected']} model={row.get('predicted')} final={row.get('final')}", flush=True)
