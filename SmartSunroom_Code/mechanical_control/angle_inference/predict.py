"""Predict N-S / E-W solar angles from the photoresistor board.

Uses the sibling solar_angle package: serial read -> normalize -> joblib classifier.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass

import serial

from mechanical_control.config import (
    ANGLE_COLLECTOR,
    ANGLE_MODEL_TRAIN,
    SERIAL_BAUD,
    SERIAL_OPEN_DELAY_SEC,
    SERIAL_READ_RETRIES,
    SERIAL_READ_TIMEOUT_SEC,
)
from mechanical_control.models import SunAngles


@dataclass(frozen=True)
class AnglePredictResult:
    sun: SunAngles
    raw_model_ns: float | None = None
    raw_model_ew: float | None = None
    note: str = ""


def _ensure_collector_on_path() -> None:
    collector = str(ANGLE_COLLECTOR)
    if collector not in sys.path:
        sys.path.insert(0, collector)


def _read_channels_once(ser: serial.Serial, retries: int = SERIAL_READ_RETRIES) -> list[int]:
    last_err: Exception = TimeoutError("serial read timeout; no data received")
    for _ in range(retries):
        try:
            ser.reset_input_buffer()
            ser.write(b"R\r\n")
            ser.flush()
            line = ser.readline()
            if not line:
                time.sleep(0.08)
                continue
            text = line.decode("ascii", errors="replace").strip()
            parts = text.split(",")
            if len(parts) != 8:
                last_err = ValueError(f"expected 8 values, got: {text!r}")
                time.sleep(0.08)
                continue
            return [int(p.strip()) for p in parts]
        except ValueError as e:
            last_err = e
            time.sleep(0.08)
    raise last_err


def sample_angle_board(port: str, samples: int = 3, interval_sec: float = 0.2) -> list[list[int]]:
    """Read several raw ADC rows from the angle board (command R)."""
    ser = serial.Serial(port, SERIAL_BAUD, timeout=SERIAL_READ_TIMEOUT_SEC)
    try:
        time.sleep(SERIAL_OPEN_DELAY_SEC)
        ser.reset_input_buffer()
        rows: list[list[int]] = []
        for i in range(samples):
            rows.append(_read_channels_once(ser))
            if i + 1 < samples:
                time.sleep(interval_sec)
        return rows
    finally:
        ser.close()


def _predict_with_model(port: str, sample_count: int = 20) -> SunAngles:
    """Full inference chain: multi-sample -> normalize -> joblib classify."""
    _ensure_collector_on_path()
    import config as ap_config  # type: ignore  # solar_angle/data_collection/config.py
    import joblib
    import numpy as np
    from serial_reader import open_serial, read_channels  # type: ignore

    meta_path = ANGLE_COLLECTOR / "data_normalized" / "normalization_meta.json"
    model_path = ANGLE_MODEL_TRAIN / "artifacts" / "model.joblib"
    classes_path = ANGLE_MODEL_TRAIN / "artifacts" / "classes.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"missing normalization meta: {meta_path}")
    if not model_path.is_file():
        raise FileNotFoundError(f"missing model: {model_path}")
    if not classes_path.is_file():
        raise FileNotFoundError(f"missing classes: {classes_path}")

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    with open(classes_path, encoding="utf-8") as f:
        cm = json.load(f)
    id_to = {c["class_id"]: (c["ns_deg"], c["ew_deg"]) for c in cm["classes"]}
    clf = joblib.load(model_path)

    def raw_to_ordered8(raw8: list[int]) -> np.ndarray:
        out = []
        for direction in ap_config.ROWS_ORDER:
            ai, bi = ap_config.PIN_GROUPS[direction]
            out.append(float(raw8[ai]))
            out.append(float(raw8[bi]))
        return np.array(out, dtype=np.float64)

    def normalize(vec8: np.ndarray) -> np.ndarray:
        names = meta["sensor_columns"]
        ref_mean = meta["reference_mean_per_channel"]
        normed = []
        for name in names:
            r = float(ref_mean[name])
            x = float(vec8[len(normed)])
            denom = r if r >= 1.0 else 1.0
            normed.append((x - r) / denom)
        return np.array(normed, dtype=np.float64)

    def to_model_flat(normed_serial8: np.ndarray) -> np.ndarray:
        row0 = [f"{d}_1" for d in ap_config.ROWS_ORDER]
        row1 = [f"{d}_2" for d in ap_config.ROWS_ORDER]
        serial_names = []
        for d in ap_config.ROWS_ORDER:
            serial_names.append(f"{d}_1")
            serial_names.append(f"{d}_2")
        m = dict(zip(serial_names, normed_serial8))
        return np.array([m[c] for c in row0 + row1], dtype=np.float64)

    ser = open_serial(port, ap_config.SERIAL_BAUD)
    acc = np.zeros(8, dtype=np.float64)
    try:
        for i in range(sample_count):
            raw = read_channels(ser)
            acc += raw_to_ordered8(raw)
            if i + 1 < sample_count:
                time.sleep(0.5)
    finally:
        ser.close()

    mean_raw = acc / float(sample_count)
    X = to_model_flat(normalize(mean_raw)).reshape(1, -1)
    best_cid = int(clf.predict(X)[0])
    ns, ew = id_to[best_cid]
    return SunAngles(ns_angle=float(ns), ew_zero=float(ew))


def predict_sun_angles(port: str, *, sample_count: int = 20, log=None) -> AnglePredictResult:
    """Predict solar angles from hardware + trained model. Port is required."""

    def _log(msg: str) -> None:
        if log:
            log(msg)

    if not port:
        raise ValueError("angle sensor port is required")

    _log(f"Running solar-angle model on {port}...")
    sun = _predict_with_model(port, sample_count=sample_count)
    return AnglePredictResult(
        sun=sun,
        raw_model_ns=sun.ns_angle,
        raw_model_ew=sun.ew_zero,
        note="Solar angles predicted by trained model.",
    )
