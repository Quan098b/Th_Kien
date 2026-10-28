"""Run a reproducible WAV benchmark through the ESP32 EIP1 serial path."""
from __future__ import annotations
import argparse, binascii, csv, math, pathlib, random, re, struct, time, wave
import serial

LABELS = ("Bat_Den", "Tap_Am", "Tat_Den", "Unknown")
PROB_RE = re.compile(r"PROB source=SERIAL (\S+)=([0-9.]+)")
RESULT_RE = re.compile(r"RESULT source=SERIAL best=(\S+) probability=([0-9.]+) second=(\S+) margin=([0-9.]+) dsp_ms=(\d+) inference_ms=(\d+)")
AUDIO_RE = re.compile(r"AUDIO source=SERIAL rms=([0-9.]+) pcm_min=(-?\d+) pcm_max=(-?\d+) clipped=(\d+)/")

def read_wav(path: pathlib.Path) -> bytes:
    with wave.open(str(path), "rb") as wav:
        if wav.getparams()[:4] != (1, 2, 16000, 24000):
            raise ValueError(f"{path}: expected mono PCM16 16kHz 24000 samples; got {wav.getparams()}")
        return wav.readframes(24000)

def wait_line(port: serial.Serial, prefix: str, deadline: float) -> str:
    while time.monotonic() < deadline:
        line = port.readline().decode("utf-8", "replace").strip()
        if line.startswith("TEST_ERROR"):
            raise RuntimeError(line)
        if line.startswith(prefix):
            return line
    raise TimeoutError(f"No {prefix}")

def infer(port: serial.Serial, pcm: bytes, timeout: float) -> list[str]:
    crc = binascii.crc32(pcm) & 0xffffffff
    port.reset_input_buffer(); port.write(b"t")
    deadline = time.monotonic() + timeout
    wait_line(port, "TEST_READY", deadline)
    port.write(struct.pack("<4sII", b"EIP1", 24000, crc)); port.flush()
    wait_line(port, "TEST_HEADER_READY", deadline)
    for offset in range(0, len(pcm), 64):
        port.write(pcm[offset:offset + 64]); port.flush(); time.sleep(0.006)
    lines = []
    while time.monotonic() < deadline:
        line = port.readline().decode("utf-8", "replace").strip()
        if line: lines.append(line)
        if line == "TEST_END": return lines
        if line.startswith("TEST_ERROR"): raise RuntimeError(line)
    raise TimeoutError("No TEST_END")

parser = argparse.ArgumentParser()
parser.add_argument("dataset", type=pathlib.Path)
parser.add_argument("--port", default="COM15")
parser.add_argument("--seed", type=int, default=20261022)
parser.add_argument("--per-class", type=int, default=20)
parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("logs/dataset_benchmark.csv"))
args = parser.parse_args()

rng = random.Random(args.seed)
selected: list[tuple[str, pathlib.Path]] = []
for label in LABELS:
    folder = args.dataset / label
    files = sorted(folder.glob("*.wav")) if folder.is_dir() else []
    if files:
        selected.extend((label, path) for path in rng.sample(files, min(args.per_class, len(files))))
    print(f"DATASET class={label} available={len(files)} selected={min(args.per_class, len(files))}", flush=True)

args.output.parent.mkdir(parents=True, exist_ok=True)
fields = ["index", "file", "expected", *LABELS, "predicted", "margin", "rms", "pcm_min", "pcm_max", "clipped", "dsp_ms", "inference_ms", "crc32"]
with serial.Serial(args.port, 115200, timeout=1, write_timeout=5) as port, args.output.open("w", newline="", encoding="utf-8") as out:
    writer = csv.DictWriter(out, fieldnames=fields); writer.writeheader(); time.sleep(0.4)
    for index, (expected, path) in enumerate(selected, 1):
        pcm = read_wav(path); crc = binascii.crc32(pcm) & 0xffffffff
        lines = infer(port, pcm, 45.0)
        row = {"index": index, "file": str(path), "expected": expected, "crc32": f"{crc:08x}"}
        for line in lines:
            if match := PROB_RE.fullmatch(line): row[match.group(1)] = match.group(2)
            elif match := AUDIO_RE.match(line):
                row.update(rms=match.group(1), pcm_min=match.group(2), pcm_max=match.group(3), clipped=match.group(4))
            elif match := RESULT_RE.match(line):
                row.update(predicted=match.group(1), margin=match.group(4), dsp_ms=match.group(5), inference_ms=match.group(6))
        writer.writerow(row); out.flush()
        print(f"[{index}/{len(selected)}] {path.name}: expected={expected} predicted={row.get('predicted')} rms={row.get('rms')} margin={row.get('margin')}", flush=True)
