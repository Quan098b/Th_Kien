"""Build a licensed, training-only Vietnamese hard-negative candidate pool."""
from __future__ import annotations
import csv, pathlib, wave
from piper import PiperVoice
from generate_test_audio import format_window

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXP = ROOT / "training_experiments/v5_hard_negatives"
OUT = EXP / "data/training_candidate/piper_vais1000/session_hardneg_001"
MODEL = ROOT / "test_audio/piper_model/vi_VN-vais1000-medium.onnx"
PHRASES = [
    "Bật nhạc", "Tắt nhạc", "Bật quạt", "Tắt quạt", "Bật máy", "Tắt máy",
    "Bật máy lạnh", "Tắt máy lạnh", "Bật ti vi", "Tắt ti vi", "Bật điện thoại", "Tắt điện thoại",
    "Bật đèn phòng khách", "Tắt đèn phòng khách", "Đèn đang bật", "Đèn đang tắt",
    "Đừng bật đèn", "Không được tắt đèn", "Bạn có bật đèn không", "Bạn có tắt đèn không",
    "Tôi muốn uống nước", "Đi ra ngoài", "Quạt đang chạy", "Đèn ở phòng khách",
    "Mở cửa sổ", "Đóng cửa lại", "Mở nhạc", "Dừng lại", "Hãy nói chậm hơn", "Bây giờ là mấy giờ",
]

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    voice = PiperVoice.load(MODEL)
    records = []
    for i, text in enumerate(PHRASES):
        final = OUT / f"unknown_hardneg_{i:03d}.wav"
        raw = OUT / f"unknown_hardneg_{i:03d}.raw.wav"
        if not final.exists():
            with wave.open(str(raw), "wb") as wav: voice.synthesize_wav(text, wav)
            format_window(raw, final)
        records.append({
            "file": str(final.relative_to(ROOT)), "label": "Unknown", "content": text,
            "speaker_id": "piper_vi_VN_vais1000", "session_id": "synthetic_hardneg_001",
            "split": "training_candidate", "source": "Piper vi_VN-vais1000-medium",
            "license": "CC-BY-4.0", "derived_from_prior_test_audio": "false"
        })
    fields = list(records[0])
    with (EXP / "hard_negative_manifest.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(records)
    print(f"created/preserved {len(records)} training-only candidates in {OUT}")

if __name__ == "__main__": main()
