"""Capture the exact inference window streamed by the ESP32-S3 as a WAV file."""
import argparse
import pathlib
import re
import time
import serial

parser = argparse.ArgumentParser()
parser.add_argument("output", type=pathlib.Path)
parser.add_argument("--port", default="COM15")
parser.add_argument("--baud", type=int, default=115200)
parser.add_argument("--timeout", type=float, default=10.0)
args = parser.parse_args()
with serial.Serial(args.port, args.baud, timeout=1) as port:
    time.sleep(0.3)
    port.reset_input_buffer()
    port.write(b"w\n")
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        match = re.fullmatch(rb"WAV_BEGIN (\d+)\r?\n", port.readline())
        if not match:
            continue
        expected = int(match.group(1))
        data = port.read(expected)
        if len(data) != expected:
            raise RuntimeError(f"Incomplete WAV: {len(data)}/{expected} bytes")
        if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            raise RuntimeError("Invalid WAV header")
        args.output.write_bytes(data)
        print(f"Saved {len(data)} bytes to {args.output.resolve()}")
        break
    else:
        raise TimeoutError("Device did not send a WAV window")
