"""Generate licensed Vietnamese Piper TTS fixtures and format them for the EI model."""
from __future__ import annotations

import math
import pathlib
import wave

import numpy as np
from piper import PiperVoice
from scipy.signal import resample_poly

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "test_audio"
MODEL = OUT / "piper_model" / "vi_VN-vais1000-medium.onnx"
TARGET_RATE = 16_000
TARGET_SAMPLES = 24_000


def read_pcm16(path: pathlib.Path) -> tuple[int, np.ndarray]:
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError(f"Unexpected Piper format: {path}")
        rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").copy()
    return rate, samples


def format_window(source: pathlib.Path, destination: pathlib.Path) -> None:
    source_rate, pcm = read_pcm16(source)
    peak = int(np.max(np.abs(pcm.astype(np.int32))))
    threshold = max(64, int(peak * 0.01))
    active = np.flatnonzero(np.abs(pcm.astype(np.int32)) >= threshold)
    if not len(active):
        raise ValueError(f"No speech detected in {source}")
    margin = round(0.12 * source_rate)
    start = max(0, int(active[0]) - margin)
    stop = min(len(pcm), int(active[-1]) + margin + 1)
    pcm = pcm[start:stop]
    pcm = resample_poly(pcm.astype(np.float64), TARGET_RATE, source_rate)
    if len(pcm) > TARGET_SAMPLES:
        raise ValueError(
            f"Speech is {len(pcm) / TARGET_RATE:.3f}s after safe trimming; refusing to crop it"
        )
    # Preserve synthesized gain unless the resampling filter overshoots PCM16.
    resampled_peak = float(np.max(np.abs(pcm)))
    if resampled_peak > 32760.0:
        pcm *= 32760.0 / resampled_peak
    pcm = np.clip(np.rint(pcm), -32768, 32767).astype("<i2")
    left = (TARGET_SAMPLES - len(pcm)) // 2
    window = np.zeros(TARGET_SAMPLES, dtype="<i2")
    window[left:left + len(pcm)] = pcm
    with wave.open(str(destination), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(TARGET_RATE)
        wav.writeframes(window.tobytes())
    mean = float(np.mean(window))
    rms = math.sqrt(float(np.mean((window.astype(np.float64) - mean) ** 2)))
    print(
        f"{destination.name}: source_rate={source_rate}, speech_samples={len(pcm)}, "
        f"padding=({left},{TARGET_SAMPLES-len(pcm)-left}), min={window.min()}, "
        f"max={window.max()}, rms={rms:.2f}"
    )


def main() -> None:
    OUT.mkdir(exist_ok=True)
    voice = PiperVoice.load(MODEL)
    for stem, text in (("bat_den", "Bật đèn"), ("tat_den", "Tắt đèn")):
        raw = OUT / f"{stem}_piper_raw.wav"
        with wave.open(str(raw), "wb") as wav:
            voice.synthesize_wav(text, wav)
        format_window(raw, OUT / f"{stem}.wav")


if __name__ == "__main__":
    main()
