"""Train control (plain) vs gain-augmented models on deployment 4 MFE features.

Validation is split by source recording (augmented copies stay with their
source). There are no speaker IDs, so validation is NOT speaker-disjoint.
"""
import argparse, csv, json
from collections import Counter
from pathlib import Path

import numpy as np
import tensorflow as tf

HERE = Path(__file__).resolve().parent
FEATS = HERE / "work/features"
LABELS = ["Bat_Den", "Tap_Am", "Tat_Den", "Unknown"]
COMMANDS = {"Bat_Den", "Tat_Den"}
COLS = 5960


def load(name):
    x = np.fromfile(FEATS / f"{name}.f32", dtype=np.float32).reshape(-1, COLS)
    meta = list(csv.DictReader((FEATS / f"{name}.csv").open(encoding="utf-8")))
    assert len(meta) == len(x), name
    return x, meta


def build_model():
    # Edge Impulse default keyword-spotting 1D CNN for 40-filter MFE.
    return tf.keras.Sequential([
        tf.keras.layers.Input((COLS,)),
        tf.keras.layers.Reshape((COLS // 40, 40)),
        tf.keras.layers.Conv1D(8, 3, padding="same", activation="relu"),
        tf.keras.layers.MaxPooling1D(2, padding="same"),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.Conv1D(16, 3, padding="same", activation="relu"),
        tf.keras.layers.MaxPooling1D(2, padding="same"),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(len(LABELS), activation="softmax"),
    ])


def train(x, meta, val_sources, seed, epochs):
    tf.keras.utils.set_random_seed(seed)
    y = np.array([LABELS.index(m["label"]) for m in meta])
    is_val = np.array([m["source"] in val_sources for m in meta])
    val_orig = is_val & np.array([m.get("copy", "0") == "0" for m in meta])
    model = build_model()
    model.compile(optimizer=tf.keras.optimizers.Adam(0.005),
                  loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    cb = tf.keras.callbacks.EarlyStopping("val_loss", patience=15, restore_best_weights=True)
    h = model.fit(x[~is_val], y[~is_val], validation_data=(x[val_orig], y[val_orig]),
                  epochs=epochs, batch_size=32, callbacks=[cb], verbose=0)
    return model, float(max(h.history["val_accuracy"])), len(h.history["loss"])


def to_int8(model, rep):
    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = lambda: ([r[None, :]] for r in rep)
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    return conv.convert()


def predict_int8(tfl, x):
    it = tf.lite.Interpreter(model_content=tfl); it.allocate_tensors()
    i, o = it.get_input_details()[0], it.get_output_details()[0]
    (si, zi), (so, zo) = i["quantization"], o["quantization"]
    out = []
    for row in x:
        it.set_tensor(i["index"], np.clip(np.round(row / si + zi), -128, 127).astype(np.int8)[None, :])
        it.invoke()
        out.append((it.get_tensor(o["index"])[0].astype(np.float32) - zo) * so)
    return np.array(out)


def accuracy(pred, meta):
    return float(np.mean([LABELS[p] == m["label"] for p, m in zip(pred, meta)]))


def gate_metrics(pred_labels, meta, split=None):
    rows = [(p, m) for p, m in zip(pred_labels, meta) if split is None or m["split"] == split]
    neg = [(p, m) for p, m in rows if m["label"] == "reject"]
    pos = [(p, m) for p, m in rows if m["label"] in COMMANDS]
    fa = sum(m["gate_pass"] == "true" and p in COMMANDS for p, m in neg)
    fr = sum(not (m["gate_pass"] == "true" and p == m["label"]) for p, m in pos)
    speech = [(p, m) for p, m in neg if m["device"] == "non_command_speech"]
    fa_speech = sum(m["gate_pass"] == "true" and p in COMMANDS for p, m in speech)
    return {"FAR": f"{fa}/{len(neg)}", "FRR": f"{fr}/{len(pos)}",
            "FA_noncommand_speech": f"{fa_speech}/{len(speech)}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--epochs", type=int, default=100)
    a = ap.parse_args()

    sets = {n: load(n) for n in ["train_plain", "train_aug", "test_orig", "test_rms200",
                                 "test_rms200n", "test_rms4500", "ext"]}
    ext_x, ext_meta = sets["ext"]

    # Fixed 15% validation split by source recording, stratified by label.
    rng = np.random.default_rng(20261023)
    val_sources = set()
    for lab in LABELS:
        srcs = sorted({m["source"] for m in sets["train_plain"][1] if m["label"] == lab})
        val_sources |= set(rng.choice(srcs, size=round(0.15 * len(srcs)), replace=False))

    results = {"deployment4_ext": {"all": gate_metrics([m["dep4_pred"] for m in ext_meta], ext_meta),
                                   "test": gate_metrics([m["dep4_pred"] for m in ext_meta], ext_meta, "test")}}
    out_dir = HERE / "models"; out_dir.mkdir(exist_ok=True)
    for variant in ["plain", "aug"]:
        x, meta = sets[f"train_{variant}"]
        for seed in [int(s) for s in a.seeds.split(",")]:
            model, val_acc, ep = train(x, meta, val_sources, seed, a.epochs)
            r = {"val_acc": round(val_acc, 4), "epochs": ep}
            for n in ["test_orig", "test_rms200", "test_rms200n", "test_rms4500"]:
                tx, tm = sets[n]
                r[n] = round(accuracy(model.predict(tx, verbose=0).argmax(1), tm), 4)
            ext_pred = [LABELS[p] for p in model.predict(ext_x, verbose=0).argmax(1)]
            r["ext_float_all"] = gate_metrics(ext_pred, ext_meta)
            r["ext_float_test"] = gate_metrics(ext_pred, ext_meta, "test")
            tfl = to_int8(model, x[rng.choice(len(x), 300, replace=False)])
            (out_dir / f"{variant}_seed{seed}.tflite").write_bytes(tfl)
            q_ext = [LABELS[p] for p in predict_int8(tfl, ext_x).argmax(1)]
            r["ext_int8_all"] = gate_metrics(q_ext, ext_meta)
            q_t = predict_int8(tfl, sets["test_rms200n"][0]).argmax(1)
            r["test_rms200n_int8"] = round(accuracy(q_t, sets["test_rms200n"][1]), 4)
            cm = Counter((m["label"], LABELS[p]) for p, m in zip(q_t, sets["test_rms200n"][1]))
            r["test_rms200n_int8_confusion"] = {f"{t}->{p}": c for (t, p), c in sorted(cm.items())}
            ext_detail = Counter((m["device"], p) for p, m in zip(q_ext, ext_meta))
            r["ext_int8_by_group"] = {f"{g}->{p}": c for (g, p), c in sorted(ext_detail.items())}
            results[f"{variant}_seed{seed}"] = r
            print(f"\n## {variant} seed={seed}\n{json.dumps(r, ensure_ascii=False, indent=1)}", flush=True)

    (HERE / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n## deployment 4 reference\n" + json.dumps(results["deployment4_ext"], indent=1))


if __name__ == "__main__":
    main()
