"""Send an exact PCM16 WAV window to the ESP32-S3 EIP1 test protocol."""
from __future__ import annotations
import argparse, binascii, pathlib, re, struct, time, wave
import serial

parser = argparse.ArgumentParser()
parser.add_argument("wav", type=pathlib.Path)
parser.add_argument("--port", default="COM15")
parser.add_argument("--timeout", type=float, default=15.0)
parser.add_argument("--log", type=pathlib.Path)
args = parser.parse_args()
lines: list[str] = []

def emit(line: str) -> None:
    print(line)
    lines.append(line)
with wave.open(str(args.wav), "rb") as wav:
    if wav.getparams()[:4] != (1, 2, 16000, 24000):
        raise ValueError(f"Expected mono PCM16 16kHz 24000 samples, got {wav.getparams()}")
    pcm = wav.readframes(24000)
crc = binascii.crc32(pcm) & 0xffffffff
with serial.Serial(args.port, 115200, timeout=1, write_timeout=5) as port:
    time.sleep(0.3); port.reset_input_buffer(); port.write(b"t")
    deadline = time.monotonic() + args.timeout
    ready = False
    while time.monotonic() < deadline:
        line = port.readline().decode("utf-8", "replace").strip()
        if line.startswith("TEST_READY protocol=EIP1"):
            ready = True; break
    if not ready: raise TimeoutError("No TEST_READY from device")
    port.write(struct.pack("<4sII", b"EIP1", 24000, crc)); port.flush()
    while time.monotonic() < deadline:
        line = port.readline().decode("utf-8", "replace").strip()
        if line == "TEST_HEADER_READY": break
        if line.startswith("TEST_ERROR"): raise RuntimeError(line)
    else: raise TimeoutError("No TEST_HEADER_READY from device")
    # Native USB CDC has a small RX ring on this target; pace endpoint-sized packets.
    for offset in range(0, len(pcm), 64):
        port.write(pcm[offset:offset + 64])
        port.flush()
        time.sleep(0.006)
    emit(f"HOST file={args.wav} samples=24000 bytes={len(pcm)} crc={crc:08x}")
    while time.monotonic() < deadline:
        line = port.readline().decode("utf-8", "replace").strip()
        if line: emit(line)
        if line == "TEST_END": break
        if line.startswith("TEST_ERROR"): raise RuntimeError(line)
    else: raise TimeoutError("No TEST_END from device")

if args.log:
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text("\n".join(lines) + "\n", encoding="utf-8")
