"""Generate deterministic, non-speech control windows for classifier checks."""
from pathlib import Path
import wave
import numpy as np

out = Path("test_audio")
out.mkdir(exist_ok=True)
rng = np.random.default_rng(20261022)
controls = {
    "silence.wav": np.zeros(24000, dtype=np.int16),
    "noise_rms_300.wav": np.clip(np.rint(rng.normal(0, 300, 24000)), -32768, 32767).astype("<i2"),
}
for name, samples in controls.items():
    with wave.open(str(out / name), "wb") as wav:
        wav.setparams((1, 2, 16000, 24000, "NONE", "not compressed"))
        wav.writeframes(samples.tobytes())
    print(f"{name}: samples={len(samples)} rms={np.sqrt(np.mean(samples.astype(float)**2)):.2f}")
