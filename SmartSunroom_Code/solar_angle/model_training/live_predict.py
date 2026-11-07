# -*- coding: utf-8 -*-
"""
Live test: serial Mega -> mean of 20 raw readings -> normalize with normalization_meta
-> flatten to train.py 8-D order -> single predict with artifacts/model.joblib.

Note: collection CSV/serial use interleaved E1 E2 S1 S2...; training flattens all *_1 then *_2,
map normalized 8-D into that order before predict (same as dataset.load_xy_from_normalized_dir).

Usage:
  cd solar_angle/model_training
  python live_predict.py COM7

Deps: pyserial, numpy, joblib, scikit-learn (same as training)
"""
from __future__ import print_function

import argparse
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import joblib
import numpy as np

# --- Paths: data_collection config + serial_reader ---
_ROOT = os.path.dirname(os.path.abspath(__file__))
_COLLECTOR = os.path.abspath(os.path.join(_ROOT, "..", "data_collection"))
if _COLLECTOR not in sys.path:
    sys.path.insert(0, _COLLECTOR)

import config  # noqa: E402
from serial_reader import open_serial, read_channels  # noqa: E402

ARTIFACTS_DIR = os.path.join(_ROOT, "artifacts")
NORM_META_PATH = os.path.join(_COLLECTOR, "data_normalized", "normalization_meta.json")

SAMPLE_COUNT = 20
SAMPLE_INTERVAL_SEC = 0.5


def raw_adc_to_ordered8(raw8_int):
    """Mega A0..A7 order -> CSV-like 8 columns: *_1,*_2 per ROWS_ORDER."""
    raw8 = [float(x) for x in raw8_int]
    out = []
    for direction in config.ROWS_ORDER:
        ai, bi = config.PIN_GROUPS[direction]
        out.append(raw8[ai])
        out.append(raw8[bi])
    return np.array(out, dtype=np.float64)


def normalize_with_meta(vec8, meta):
    """Same as normalize_dataset.py: (x-ref)/max(ref,1); vec8 ordered like meta['sensor_columns']."""
    names = meta["sensor_columns"]
    ref_mean = meta["reference_mean_per_channel"]
    normed = []
    for name in names:
        r = float(ref_mean[name])
        x = float(vec8[len(normed)])
        denom = r if r >= 1.0 else 1.0
        normed.append((x - r) / denom)
    return np.array(normed, dtype=np.float64)


def normalized_serial8_to_model_flat(normed_serial8):
    """
    Interleaved serial/CSV order (_1,_2 per dir) -> train.py X.reshape(N,-1) order:
    [east_1,south_1,west_1,north_1, east_2,south_2,west_2,north_2]
    """
    row0 = ["{}_1".format(d) for d in config.ROWS_ORDER]
    row1 = ["{}_2".format(d) for d in config.ROWS_ORDER]
    serial_names = []
    for d in config.ROWS_ORDER:
        serial_names.append("{}_1".format(d))
        serial_names.append("{}_2".format(d))
    m = dict(zip(serial_names, normed_serial8))
    return np.array([m[c] for c in row0 + row1], dtype=np.float64)


def load_model_bundle():
    clf = joblib.load(os.path.join(ARTIFACTS_DIR, "model.joblib"))
    with open(os.path.join(ARTIFACTS_DIR, "classes.json"), encoding="utf-8") as f:
        cm = json.load(f)
    id_to = {c["class_id"]: (c["ns_deg"], c["ew_deg"]) for c in cm["classes"]}
    return clf, id_to


def run_live_test(port, log_print):
    if not os.path.isfile(NORM_META_PATH):
        raise FileNotFoundError("missing normalization meta: " + NORM_META_PATH)
    with open(NORM_META_PATH, encoding="utf-8") as f:
        meta = json.load(f)

    if not os.path.isfile(os.path.join(ARTIFACTS_DIR, "model.joblib")):
        raise FileNotFoundError("run train.py first to create artifacts/model.joblib")

    clf, id_to = load_model_bundle()
    ser = open_serial(port, config.SERIAL_BAUD)
    acc = np.zeros(8, dtype=np.float64)

    try:
        for i in range(SAMPLE_COUNT):
            raw = read_channels(ser)
            vec = raw_adc_to_ordered8(raw)
            acc += vec
            log_print(
                "[{:02d}/{}] sampled (accumulating raw 8 channels)".format(i + 1, SAMPLE_COUNT)
            )
            if i + 1 < SAMPLE_COUNT:
                time.sleep(SAMPLE_INTERVAL_SEC)
    finally:
        ser.close()

    mean_raw = acc / float(SAMPLE_COUNT)
    normed = normalize_with_meta(mean_raw, meta)
    X = normalized_serial8_to_model_flat(normed).reshape(1, -1)
    best_cid = int(clf.predict(X)[0])
    bns, bew = id_to[best_cid]
    log_print("")
    log_print("======== summary ({}-sample mean -> normalize -> predict) ========".format(SAMPLE_COUNT))
    log_print("mean raw 8 channels (serial order): {}".format(np.array2string(mean_raw, precision=2)))
    log_print("normalized (model input order): {}".format(np.array2string(X.ravel(), precision=4)))
    log_print("predicted class: {}".format(best_cid))
    log_print("angles: ns_deg={} , ew_deg={}".format(bns, bew))
    log_print("========================================")


class App(object):
    def __init__(self, default_port):
        self.root = tk.Tk()
        self.root.title("Mega live predict (20-sample mean + normalize)")
        self.root.geometry("560x400")

        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Port:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value=default_port or "")
        self.entry = ttk.Entry(top, textvariable=self.port_var, width=14)
        self.entry.pack(side=tk.LEFT, padx=6)
        self.btn = ttk.Button(top, text="Start test", command=self.on_start)
        self.btn.pack(side=tk.LEFT)

        self.log = scrolledtext.ScrolledText(self.root, height=18, state=tk.DISABLED, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._busy = False

    def log_line(self, s):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, s + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def on_start(self):
        if self._busy:
            messagebox.showinfo("Notice", "Test in progress...")
            return
        port = self.port_var.get().strip()
        if not port:
            messagebox.showerror("Error", "Enter a serial port, e.g. COM7")
            return

        def worker():
            self._busy = True
            self.btn.configure(state=tk.DISABLED)
            try:
                self.root.after(0, lambda: self.log_line("Using port: " + port))
                run_live_test(port, lambda m: self.root.after(0, self.log_line, m))
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Done", "Finished 20-sample mean, normalize, and one prediction. See log."
                    ),
                )
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self._busy = False
                self.root.after(0, lambda: self.btn.configure(state=tk.NORMAL))

        threading.Thread(target=worker, daemon=True).start()

    def run(self):
        self.root.mainloop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", default="", help="serial port e.g. COM7; can also change in the window")
    args = ap.parse_args()
    App(default_port=args.port).run()


if __name__ == "__main__":
    main()