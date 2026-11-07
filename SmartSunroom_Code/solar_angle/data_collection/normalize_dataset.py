"""
Normalize raw CSVs under data/ into data_normalized/; originals are not modified.

Reference: at ns_deg≈90, ew_deg≈90, per-channel mean across samples is the channel center;
norm = (raw - ref) / max(ref, 1) per channel so reference pose averages near 0.

Usage (from data_collection directory):
  python normalize_dataset.py
  python normalize_dataset.py --data-dir data --out-dir data_normalized
"""
from __future__ import print_function

import argparse
import csv
import json
import os
import sys
from typing import Dict, List, Tuple

import config


def sensor_columns() -> List[str]:
    cols = []
    for direction in config.ROWS_ORDER:
        cols.append("{}_1".format(direction))
        cols.append("{}_2".format(direction))
    return cols


def iter_csv_files(data_root: str) -> List[str]:
    out = []
    for dirpath, _dirnames, filenames in os.walk(data_root):
        for name in filenames:
            if name.lower().endswith(".csv"):
                out.append(os.path.join(dirpath, name))
    out.sort()
    return out


def load_rows_for_ref(
    paths: List[str], ns_target: float, ew_target: float, eps: float
) -> Tuple[Dict[str, List[float]], int]:
    """Collect channel readings at matching ns/ew rows for reference means."""
    cols = sensor_columns()
    buckets = {c: [] for c in cols}
    row_count = 0
    for path in paths:
        with open(path, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            if not r.fieldnames:
                continue
            for row in r:
                try:
                    ns = float(row["ns_deg"])
                    ew = float(row["ew_deg"])
                except (KeyError, ValueError):
                    continue
                if abs(ns - ns_target) > eps or abs(ew - ew_target) > eps:
                    continue
                row_count += 1
                for c in cols:
                    try:
                        buckets[c].append(float(row[c]))
                    except (KeyError, ValueError):
                        pass
    return buckets, row_count


def mean_ref(buckets: Dict[str, List[float]]) -> Dict[str, float]:
    ref = {}
    for c, vals in buckets.items():
        if not vals:
            ref[c] = 0.0
        else:
            ref[c] = sum(vals) / float(len(vals))
    return ref


def normalize_value(raw: float, ref: float) -> float:
    denom = ref if ref >= 1.0 else 1.0
    return (raw - ref) / denom


def process_file(
    src_path: str,
    dst_path: str,
    ref: Dict[str, float],
    cols: List[str],
) -> None:
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(src_path, newline="", encoding="utf-8") as fin:
        reader = csv.DictReader(fin)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            return
        with open(dst_path, "w", newline="", encoding="utf-8") as fout:
            writer = csv.DictWriter(fout, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                out = dict(row)
                for c in cols:
                    if c not in row:
                        continue
                    try:
                        raw = float(row[c])
                    except ValueError:
                        continue
                    out[c] = "{:.6f}".format(normalize_value(raw, ref.get(c, 1.0)))
                writer.writerow(out)


def main() -> None:
    root_dir = os.path.dirname(os.path.abspath(__file__))
    default_data = os.path.join(root_dir, config.OUTPUT_DIR)
    default_out = os.path.join(root_dir, "data_normalized")

    ap = argparse.ArgumentParser(description="Normalize CSVs into a separate folder")
    ap.add_argument("--data-dir", default=default_data, help="raw data root (default data_collection/data)")
    ap.add_argument("--out-dir", default=default_out, help="output dir (default data_collection/data_normalized)")
    ap.add_argument("--ns-ref", type=float, default=90.0, help="reference N-S angle")
    ap.add_argument("--ew-ref", type=float, default=90.0, help="reference E-W angle")
    ap.add_argument("--eps", type=float, default=1e-3, help="angle match tolerance")
    args = ap.parse_args()

    data_root = os.path.abspath(args.data_dir)
    out_root = os.path.abspath(args.out_dir)

    if not os.path.isdir(data_root):
        print("data directory not found:", data_root, file=sys.stderr)
        sys.exit(1)

    if os.path.normpath(out_root).startswith(os.path.normpath(data_root) + os.sep):
        print("output dir must not be inside the raw data dir (avoids re-scanning normalized files).", file=sys.stderr)
        sys.exit(1)

    paths = iter_csv_files(data_root)
    if not paths:
        print("no CSV found:", data_root, file=sys.stderr)
        sys.exit(1)

    buckets, n_ref_rows = load_rows_for_ref(paths, args.ns_ref, args.ew_ref, args.eps)
    ref = mean_ref(buckets)
    cols = sensor_columns()

    if n_ref_rows == 0:
        print(
            "no samples near ns_deg≈{}, ew_deg≈{}; cannot compute reference means. Collect that pose first.".format(
                args.ns_ref, args.ew_ref
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    meta = {
        "ns_ref": args.ns_ref,
        "ew_ref": args.ew_ref,
        "eps": args.eps,
        "reference_row_count": n_ref_rows,
        "reference_mean_per_channel": ref,
        "formula": "norm = (raw - ref) / max(ref, 1)",
        "sensor_columns": cols,
    }
    os.makedirs(out_root, exist_ok=True)
    meta_path = os.path.join(out_root, "normalization_meta.json")
    with open(meta_path, "w", encoding="utf-8") as mf:
        json.dump(meta, mf, indent=2, ensure_ascii=False)

    for src in paths:
        rel = os.path.relpath(src, data_root)
        dst = os.path.join(out_root, rel)
        process_file(src, dst, ref, cols)

    print("reference sample rows:", n_ref_rows)
    print("reference means written to:", meta_path)
    print("normalized {} files -> {}".format(len(paths), out_root))


if __name__ == "__main__":
    main()
