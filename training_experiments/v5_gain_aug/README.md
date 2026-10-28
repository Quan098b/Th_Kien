# v5 gain-augmentation experiment (2026-10-23)

Local experiment only. Nothing here is deployed; deployment 4 is untouched.

## Question

Edge Impulse export (`C:\Users\khanh\Desktop\AIThKien\vudieuanhsang-export`) shows each label
recorded on a different device: Tat_Den only INMP441 (RMS ~200), Bat_Den/Tap_Am/Unknown
phone/computer (RMS ~1500-5000). `tools/gain_sensitivity_test.py` on deployment 4:
scaling the EI test split to RMS 200 turns all Bat_Den and Unknown into Tat_Den; scaling
Tat_Den to RMS 4500 turns 42/50 into Bat_Den. Does random gain augmentation fix this?

## Method

- Features: `laptop_model_test/sdk/build/mfe_bin.exe` (deployment 4 MFE, identical DSP).
- Same architecture as deployment 4 (Conv1D 8 -> 16, Dense 4), Adam 0.005, batch 32,
  early stopping on val loss. 3 seeds per variant.
- `plain`: EI training split as-is (2 all-zero Bat_Den clips removed).
- `aug`: + 5 copies per clip, RMS log-uniform 60-6000, Gaussian noise std 2-25, shift +/-100 ms.
- Validation: 15% by source recording. No speaker IDs, so not speaker-disjoint.
- `ext`: filter_evaluation WAVs with the existing voice gate result; 30 Tat_Den files that
  EI used for training were removed (90 files left).

Run: `prepare_features.py` then `train_eval.py`. Full numbers: `results.json`.

## Results (EI test split accuracy, ext FAR/FRR after voice gate, int8)

| model | orig | RMS 200 | RMS 4500 | ext FAR | ext FRR | non-command speech accepted |
|---|---|---|---|---|---|---|
| deployment 4 | - | - | - | 18/60 | 1/30 | 18/20 |
| plain s1/s2/s3 | 97.5-98% | 31-37% | 73% | 16-20/60 | 0-3/30 | 16-20/20 |
| aug s1 | 99.5% | 97% | 98% | 17/60 | 0/30 | 16/20 |
| aug s2 | 96.5% | 96% | 95.5% | 19/60 | 17/30 | 19/20 |
| aug s3 | 97.5% | 96.5% | 94.5% | 13/60 | 0/30 | 12/20 |

## Conclusions

- Confirmed: the deployment 4 data teaches a loudness shortcut; plain retraining reproduces it.
- Gain augmentation removes it (RMS 200 accuracy 31-37% -> 96-97%).
- It does NOT fix non-command speech: 12-19/20 still accepted, now split between Bat_Den and
  Tat_Den. Unknown training data is one phone recording, unlike INMP441/TTS speech.
- Seed variance is large (aug s2 FRR 17/30); the external set is small and single-voice TTS.
- Not a deployment candidate. Next: real INMP441 recordings for Bat_Den and Unknown from
  several speakers, then retrain with gain augmentation kept on.
