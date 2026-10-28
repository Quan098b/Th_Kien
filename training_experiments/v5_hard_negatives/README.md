# VuDieuAnhSang v5 hard-negative experiment

This directory is isolated from deployment 4. Nothing here is deployed to the ESP32.

## Leakage rules

- `filter_evaluation/audio/noncommand_10.wav` through `noncommand_19.wav` remain test-only.
- The two parity failures, TTS command fixtures, and the 60-file filter test remain test-only.
- Files in `data/training_candidate` are newly synthesized utterances and may be used for training only after a speaker-disjoint validation/test set exists.
- Split by `speaker_id` first, then `session_id`; never randomly split windows from the same recording session.

## Current limitation

The local source dataset contains 250 real `Tat_Den` files and no local real `Bat_Den`, `Tap_Am`, or `Unknown` files. The candidate pool uses one licensed Piper speaker (CC-BY-4.0), so it is not sufficient for training or deployment by itself. Add recordings from multiple consenting speakers and independent sessions before training.

Recommended minimum collection per label: at least 5 speakers, 2 sessions per speaker, and 20 utterances per speaker/session. Reserve entire speakers for validation and test (for example 60/20/20 by speaker, adjusted to keep every class represented).
