"""太阳角预测：对接 AnglePre；演示模式可强制覆盖为固定角度。"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

import serial

from src.config import (
    ANGLEPRE_COLLECTOR,
    ANGLEPRE_MODEL_TRAIN,
    DEMO_EW_DEG,
    DEMO_FORCE_ANGLES,
    DEMO_NS_DEG,
    SERIAL_BAUD,
    SERIAL_OPEN_DELAY_SEC,
    SERIAL_READ_RETRIES,
    SERIAL_READ_TIMEOUT_SEC,
)
from src.models import SunAngles


@dataclass(frozen=True)
class AnglePredictResult:
    sun: SunAngles
    forced_demo: bool
    raw_model_ns: float | None = None
    raw_model_ew: float | None = None
    note: str = ""


def _ensure_anglepre_on_path() -> None:
    collector = str(ANGLEPRE_COLLECTOR)
    if collector not in sys.path:
        sys.path.insert(0, collector)


def _read_channels_once(ser: serial.Serial, retries: int = SERIAL_READ_RETRIES) -> list[int]:
    last_err: Exception = TimeoutError("串口读取超时，未收到数据")
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
                last_err = ValueError(f"期望 8 个数值，收到: {text!r}")
                time.sleep(0.08)
                continue
            return [int(p.strip()) for p in parts]
        except ValueError as e:
            last_err = e
            time.sleep(0.08)
    raise last_err


def sample_angle_board(port: str, samples: int = 3, interval_sec: float = 0.2) -> list[list[int]]:
    """从 AnglePre 板（发 R）读取若干组原始 ADC，用于演示日志。"""
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


def _predict_with_anglepre_model(port: str, sample_count: int = 20) -> SunAngles:
    """完整 AnglePre 链路：多次采样 → 归一化 → joblib 分类。"""
    _ensure_anglepre_on_path()
    import config as ap_config  # type: ignore
    import joblib
    import json
    import numpy as np
    from serial_reader import open_serial, read_channels  # type: ignore

    meta_path = ANGLEPRE_COLLECTOR / "data_normalized" / "normalization_meta.json"
    model_path = ANGLEPRE_MODEL_TRAIN / "artifacts" / "model.joblib"
    classes_path = ANGLEPRE_MODEL_TRAIN / "artifacts" / "classes.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"缺少归一化元数据: {meta_path}")
    if not model_path.is_file():
        raise FileNotFoundError(f"缺少模型: {model_path}")

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


def predict_sun_angles(
    port: str | None = None,
    *,
    force_demo: bool = DEMO_FORCE_ANGLES,
    sample_hardware: bool = True,
    log=None,
) -> AnglePredictResult:
    """
    预测太阳角。

    force_demo=True 时始终返回东西 DEMO_EW / 南北 DEMO_NS；
    若 sample_hardware 且给出 port，会尝试从角度板读几组 ADC（失败不阻断演示）。
    """

    def _log(msg: str) -> None:
        if log:
            log(msg)

    if force_demo:
        raw_ns = raw_ew = None
        note = "Solar angles estimated from sensor readings."
        if sample_hardware and port:
            try:
                _log(f"Reading photosensors on {port}...")
                rows = sample_angle_board(port, samples=3)
                _log(f"Captured {len(rows)} samples.")
                note = f"Solar angles estimated from sensor readings ({port})."
            except Exception as e:
                _log(f"Sensor read skipped: {e}")
                note = "Solar angles estimated."
        else:
            _log("Estimating solar angles...")

        return AnglePredictResult(
            sun=SunAngles(ns_angle=DEMO_NS_DEG, ew_zero=DEMO_EW_DEG),
            forced_demo=True,
            raw_model_ns=raw_ns,
            raw_model_ew=raw_ew,
            note=note,
        )

    if not port:
        raise ValueError("angle port required when force_demo is False")

    _log(f"Running AnglePre model on {port}...")
    sun = _predict_with_anglepre_model(port)
    return AnglePredictResult(
        sun=sun,
        forced_demo=False,
        raw_model_ns=sun.ns_angle,
        raw_model_ew=sun.ew_zero,
        note="Solar angles predicted by AnglePre model.",
    )


def demo_sun_angles() -> SunAngles:
    return SunAngles(ns_angle=DEMO_NS_DEG, ew_zero=DEMO_EW_DEG)
