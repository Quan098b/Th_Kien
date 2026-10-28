"""Create and evaluate a deterministic, independent audio rejection test set."""
from __future__ import annotations

import csv
import json
import math
import os
import pathlib
import random
import subprocess
import wave

import numpy as np
from scipy.signal import butter, lfilter, resample_poly

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "filter_evaluation"
AUDIO = OUT / "audio"
RATE, N = 16_000, 24_000
SEED = 20261022
LABELS = ["Bat_Den", "Tap_Am", "Tat_Den", "Unknown"]


def read_wav(path: pathlib.Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != RATE:
            raise ValueError(f"Expected PCM16 mono 16 kHz: {path}")
        x = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").copy()
    if len(x) != N:
        raise ValueError(f"Expected {N} samples: {path} has {len(x)}")
    return x


def write_wav(path: pathlib.Path, x: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    y = np.clip(np.rint(x), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE); wav.writeframes(y.tobytes())


def features(x16: np.ndarray) -> dict[str, float]:
    raw = x16.astype(np.float64)
    x = raw.copy()
    x -= x.mean()
    rms = math.sqrt(float(np.mean(x * x)))
    frames = np.lib.stride_tricks.sliding_window_view(x, 320)[::160]
    frms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    # Adaptive floor makes this a simple energy VAD, not a model-score threshold.
    floor = float(np.sort(frms)[int(0.10 * (len(frms) - 1))])
    active = frms > max(35.0, floor * 3.0)
    active_ratio = float(active.mean())
    # Average short-time spectrum; this maps directly to a 256-point FFT on ESP.
    spectral_frames = np.lib.stride_tricks.sliding_window_view(x, 256)[::160]
    spec = np.mean(np.abs(np.fft.rfft(spectral_frames * np.hanning(256), axis=1)) ** 2, axis=0) + 1e-12
    freq = np.fft.rfftfreq(256, 1 / RATE)
    band = (freq >= 80) & (freq <= 7600)
    flatness = float(np.exp(np.mean(np.log(spec[band]))) / np.mean(spec[band]))
    total = float(spec[band].sum())
    speech_ratio = float(spec[(freq >= 250) & (freq <= 4000)].sum() / total)
    low_ratio = float(spec[(freq >= 80) & (freq < 250)].sum() / total)
    zcr = float(np.mean(np.signbit(raw[1:]) != np.signbit(raw[:-1])))
    return {"rms": rms, "active_ratio": active_ratio, "flatness": flatness,
            "speech_ratio": speech_ratio, "low_ratio": low_ratio, "zcr": zcr}


def format_speech(raw: pathlib.Path) -> np.ndarray:
    with wave.open(str(raw), "rb") as wav:
        rate = wav.getframerate()
        x = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64)
    peak = np.max(np.abs(x))
    active = np.flatnonzero(np.abs(x) >= max(64, peak * 0.01))
    margin = round(0.12 * rate)
    x = x[max(0, active[0]-margin):min(len(x), active[-1]+margin+1)]
    x = resample_poly(x, RATE, rate)
    if len(x) > N:
        x = x[:N]
    out = np.zeros(N)
    left = (N - len(x)) // 2
    out[left:left+len(x)] = x
    return out


def generate() -> list[dict[str, str]]:
    AUDIO.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    rows: list[dict[str, str]] = []
    def add(path: pathlib.Path, group: str, expected: str, split: str) -> None:
        rows.append({"file": str(path.resolve()), "group": group, "expected": expected, "split": split})

    # Held-out real Tat_Den recordings: exclude the 20 files used for parity and split 20/20.
    dataset = pathlib.Path(r"C:\Users\khanh\Desktop\AIThKien\esp32_microphone_continuous\dataset_inmp441\Tat_Den")
    used = {pathlib.Path(r["file"]).name for r in csv.DictReader((ROOT / "logs/esp_v4_dataset_seed_20261022.csv").open(encoding="utf-8"))}
    candidates = sorted(p for p in dataset.glob("*.wav") if p.name not in used)
    random.Random(SEED).shuffle(candidates)
    for i, path in enumerate(candidates[:40]):
        add(path, "Tat_Den_real", "Tat_Den", "dev" if i < 20 else "test")

    # Bat_Den is only available as a TTS fixture. Create gain/time-shift variants, kept explicit in the report.
    bat = read_wav(ROOT / "test_audio/bat_den.wav").astype(np.float64)
    for i in range(20):
        gain = 0.35 + 0.045 * i
        shifted = np.roll(bat * gain, (i - 10) * 80)
        path = AUDIO / f"bat_tts_variant_{i:02d}.wav"; write_wav(path, shifted)
        add(path, "Bat_Den_tts_augmented", "Bat_Den", "dev" if i < 10 else "test")

    # Silence / electronic floor, white noise, low-frequency wind and tonal household hum.
    b, a = butter(3, 180 / (RATE / 2), btype="low")
    for i in range(40):
        kind = i % 4
        target = [0, 20, 60, 150, 300, 600, 1000, 1800, 3000, 5000][i // 4]
        raw = rng.normal(size=N)
        if kind == 0: x = raw
        elif kind == 1: x = lfilter(b, a, raw)  # wind
        elif kind == 2: x = np.sin(2*np.pi*(50 + 10*(i % 3))*np.arange(N)/RATE) + 0.1*raw
        else: x = np.cumsum(raw); x -= x.mean()
        cur = np.sqrt(np.mean(x*x))
        x = np.zeros(N) if target == 0 else x * target / cur
        path = AUDIO / f"negative_noise_{i:02d}.wav"; write_wav(path, x)
        group = ["background_white", "wind", "hum", "background_colored"][kind]
        add(path, group, "reject", "dev" if i < 20 else "test")

    # Vietnamese non-command speech generated by the same fixed Piper voice.
    from piper import PiperVoice
    model = ROOT / "test_audio/piper_model/vi_VN-vais1000-medium.onnx"
    voice = PiperVoice.load(model)
    phrases = [
        "xin chào", "hôm nay trời đẹp", "mở cửa sổ", "đóng cửa lại", "bây giờ là mấy giờ",
        "cảm ơn bạn", "tôi đang học bài", "âm nhạc rất hay", "hãy đọc tin tức", "nhiệt độ bao nhiêu",
        "chúc ngủ ngon", "tôi muốn uống nước", "đi ra ngoài", "quạt đang chạy", "đèn ở phòng khách",
        "bật quạt", "tắt quạt", "mở nhạc", "dừng lại", "hãy nói chậm hơn",
    ]
    raw_dir = AUDIO / "raw"
    raw_dir.mkdir(exist_ok=True)
    for i, phrase in enumerate(phrases):
        raw = raw_dir / f"noncommand_{i:02d}.wav"
        path = AUDIO / f"noncommand_{i:02d}.wav"
        # Piper sampling is not bit-deterministic, so preserve a generated fixture once created.
        if not path.exists():
            with wave.open(str(raw), "wb") as wav: voice.synthesize_wav(phrase, wav)
            write_wav(path, format_speech(raw))
        add(path, "non_command_speech", "reject", "dev" if i < 10 else "test")
    return rows


def infer(rows: list[dict[str, str]]) -> None:
    exe = ROOT / "laptop_model_test/sdk/build/laptop_infer.exe"
    mingw = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Microsoft/WinGet/Packages/BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe/mingw64/bin"
    env = os.environ.copy(); env["PATH"] = str(mingw) + os.pathsep + env.get("PATH", "")
    run = subprocess.run([str(exe), *(r["file"] for r in rows)], cwd=exe.parent.parent,
                         env=env, text=True, encoding="utf-8", capture_output=True, check=True)
    parsed = {}
    for line in run.stdout.splitlines():
        if not line.startswith("FILE\t"): continue
        parts = line.split("\t")
        parsed[str(pathlib.Path(parts[1]).resolve())] = dict(p.split("=", 1) for p in parts[2:])
    for row in rows:
        row.update(parsed[str(pathlib.Path(row["file"]).resolve())])
        row.update({k: f"{v:.9f}" for k, v in features(read_wav(pathlib.Path(row["file"]))).items()})


def gate(row: dict[str, str], t: tuple[float, float, float, float, float]) -> bool:
    rms, active, flat, low, zcr_min = t
    return (float(row["rms"]) >= rms and float(row["active_ratio"]) >= active
            and float(row["flatness"]) <= flat and float(row["low_ratio"]) <= low
            and float(row["zcr"]) >= zcr_min)


def metrics(rows: list[dict[str, str]], threshold: tuple[float, float, float, float, float] | None) -> dict[str, float]:
    pos = [r for r in rows if r["expected"] in ("Bat_Den", "Tat_Den")]
    neg = [r for r in rows if r["expected"] == "reject"]
    accepted = lambda r: (threshold is None or gate(r, threshold)) and r["predicted"] in ("Bat_Den", "Tat_Den")
    correct = lambda r: (threshold is None or gate(r, threshold)) and r["predicted"] == r["expected"]
    return {
        "positives": len(pos), "negatives": len(neg),
        "far": sum(accepted(r) for r in neg) / len(neg),
        "frr": sum(not correct(r) for r in pos) / len(pos),
        "gate_reject_positive": sum(threshold is not None and not gate(r, threshold) for r in pos) / len(pos),
    }


def main() -> None:
    rows = generate(); infer(rows)
    dev = [r for r in rows if r["split"] == "dev"]
    test = [r for r in rows if r["split"] == "test"]
    candidates = []
    for rms in (20, 35, 50, 70, 90, 120):
        for active in (0.02, 0.04, 0.06, 0.08, 0.10):
            for flat in (0.15, 0.25, 0.4, 0.6, 0.9):
                for low in (0.4, 0.6, 0.8, 0.95):
                    for zcr_min in (0.0, 0.005, 0.01, 0.015):
                        t = (rms, active, flat, low, zcr_min); m = metrics(dev, t)
                        # First avoid adding gate-induced false rejects, then minimize total error.
                        candidates.append((m["gate_reject_positive"], m["far"] + m["frr"], m["far"], t))
    _, _, _, chosen = min(candidates)
    for row in rows:
        row["gate_pass"] = str(gate(row, chosen)).lower()
        row["final"] = row["predicted"] if gate(row, chosen) else "REJECT"
    fields = list(rows[0])
    with (OUT / "filter_results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    summary = {"seed": SEED, "threshold": {"rms": chosen[0], "active_ratio": chosen[1], "flatness_max": chosen[2], "low_ratio_max": chosen[3], "zcr_min": chosen[4]},
               "dev_baseline": metrics(dev, None), "dev_filtered": metrics(dev, chosen),
               "test_baseline": metrics(test, None), "test_filtered": metrics(test, chosen)}
    (OUT / "filter_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__": main()
