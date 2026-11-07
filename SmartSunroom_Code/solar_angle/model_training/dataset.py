"""
Load normalized CSVs from data_collection/data_normalized into X (N, 2, 4) and labels.

Matrix layout (matches collection CSV columns):
  row 0: [E1, S1, W1, N1]
  row 1: [E2, S2, W2, N2]
Columns are four directions (ROWS_ORDER); rows are the two sensors per direction.
"""
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

_COLLECTOR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data_collection"))
if _COLLECTOR not in sys.path:
    sys.path.insert(0, _COLLECTOR)

import config  # noqa: E402

_FEATURE_ROUND_DECIMALS = 10


def sensor_matrix_columns() -> Tuple[List[str], List[str]]:
    """Return column names for the two rows of the 2x4 matrix."""
    row0 = ["{}_1".format(d) for d in config.ROWS_ORDER]
    row1 = ["{}_2".format(d) for d in config.ROWS_ORDER]
    return row0, row1


def list_normalized_csv_files(data_root: str) -> List[str]:
    """Recursively list CSVs under the normalized dir, excluding metadata files."""
    paths = []
    for dirpath, _dirnames, filenames in os.walk(data_root):
        for name in filenames:
            if not name.lower().endswith(".csv"):
                continue
            paths.append(os.path.join(dirpath, name))
    paths.sort()
    return paths


def is_session_csv_path(csv_path: str, data_root: str) -> bool:
    """True if path is under a session_* subfolder of data_root."""
    rel = os.path.relpath(os.path.abspath(csv_path), os.path.abspath(data_root))
    parts = rel.replace("\\", "/").split("/")
    return len(parts) >= 2 and parts[0].startswith("session_")


def _feature_key(row: np.ndarray) -> Tuple[float, ...]:
    return tuple(np.round(row, _FEATURE_ROUND_DECIMALS).tolist())


def count_exact_feature_overlap(X_a: np.ndarray, X_b: np.ndarray) -> int:
    """Count identical feature vectors between two sample sets."""
    keys_a: Set[Tuple[float, ...]] = {_feature_key(row) for row in X_a}
    keys_b: Set[Tuple[float, ...]] = {_feature_key(row) for row in X_b}
    return len(keys_a & keys_b)


def load_xy_from_normalized_dir(data_root: str) -> Tuple[np.ndarray, np.ndarray, List[Tuple[float, float]]]:
    """
    Returns
    -------
    X : ndarray, shape (N, 2, 4)
    y_class_index : ndarray, shape (N,), int
    class_order : list of (ns_deg, ew_deg) sorted, index = class id
    """
    paths = list_normalized_csv_files(data_root)
    if not paths:
        raise FileNotFoundError("no CSV found under {}".format(data_root))

    row0_cols, row1_cols = sensor_matrix_columns()
    frames = []
    for p in paths:
        df = pd.read_csv(p)
        frames.append(df)
    df = pd.concat(frames, axis=0, ignore_index=True)

    for c in row0_cols + row1_cols:
        if c not in df.columns:
            raise ValueError("CSV missing column {}; have {}".format(c, list(df.columns)))

    x0 = df[row0_cols].to_numpy(dtype=np.float64)
    x1 = df[row1_cols].to_numpy(dtype=np.float64)
    X = np.stack([x0, x1], axis=1)

    ns = df["ns_deg"].to_numpy(dtype=np.float64)
    ew = df["ew_deg"].to_numpy(dtype=np.float64)

    unique_pairs = sorted({(float(a), float(b)) for a, b in zip(ns, ew)})
    pair_to_id = {p: i for i, p in enumerate(unique_pairs)}
    y = np.array([pair_to_id[(float(a), float(b))] for a, b in zip(ns, ew)], dtype=np.int64)

    return X, y, unique_pairs


def split_per_file_unique_blocks(
    data_root: str,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[str, int]]:
    """
    Chronological train/val/test split inside each CSV; dedupe identical feature vectors.

    If an 8-D vector repeats in a file, only the first occurrence decides its split,
    preventing the same reading from landing in both train and test.
    Each light angle still appears in all three subsets (early/mid/late in file).
    """
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 1e-6:
        raise ValueError("train_ratio + val_ratio + test_ratio must be 1, got {}".format(total))

    paths = list_normalized_csv_files(data_root)
    if not paths:
        raise FileNotFoundError("no CSV found under {}".format(data_root))

    row0_cols, row1_cols = sensor_matrix_columns()
    class_order_set = set()
    x_train: List[np.ndarray] = []
    x_val: List[np.ndarray] = []
    x_test: List[np.ndarray] = []
    y_train: List[int] = []
    y_val: List[int] = []
    y_test: List[int] = []
    n_raw = 0
    n_dropped_dup = 0

    for p in paths:
        df = pd.read_csv(p).sort_values("sample_index")
        ns = float(df["ns_deg"].iloc[0])
        ew = float(df["ew_deg"].iloc[0])
        class_order_set.add((ns, ew))

    class_order = sorted(class_order_set)
    pair_to_id = {pair: i for i, pair in enumerate(class_order)}

    for p in paths:
        df = pd.read_csv(p).sort_values("sample_index")
        ns = float(df["ns_deg"].iloc[0])
        ew = float(df["ew_deg"].iloc[0])
        cid = pair_to_id[(ns, ew)]
        feats = df[row0_cols + row1_cols].to_numpy(dtype=np.float64)
        n = len(feats)
        n_raw += n
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        seen_in_file: Set[Tuple[float, ...]] = set()

        for i, row in enumerate(feats):
            key = _feature_key(row)
            if key in seen_in_file:
                n_dropped_dup += 1
                continue
            seen_in_file.add(key)

            if i < n_train:
                x_train.append(row)
                y_train.append(cid)
            elif i < n_train + n_val:
                x_val.append(row)
                y_val.append(cid)
            else:
                x_test.append(row)
                y_test.append(cid)

    stats = {
        "n_raw_rows": n_raw,
        "n_duplicate_rows_dropped": n_dropped_dup,
        "n_train": len(y_train),
        "n_val": len(y_val),
        "n_test": len(y_test),
        "n_files": len(paths),
    }

    return (
        np.asarray(x_train, dtype=np.float64),
        np.asarray(x_val, dtype=np.float64),
        np.asarray(x_test, dtype=np.float64),
        np.asarray(y_train, dtype=np.int64),
        np.asarray(y_val, dtype=np.int64),
        np.asarray(y_test, dtype=np.int64),
        stats,
    )


def split_session_generalization(
    data_root: str,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    standalone_test_fraction: float = 1.0,
    standalone_test_seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    """
    Cross-session split: train/val from session_* CSV early 80% / mid 10%;
    test = last 10% of each session file + non-session root CSVs (deduped, optionally sampled).

    standalone_test_fraction in (0,1] controls how much of standalone CSVs go to test (rest discarded).
    """
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 1e-6:
        raise ValueError("train_ratio + val_ratio + test_ratio must be 1, got {}".format(total))
    if not 0.0 < standalone_test_fraction <= 1.0:
        raise ValueError("standalone_test_fraction must be in (0,1], got {}".format(standalone_test_fraction))

    data_root = os.path.abspath(data_root)
    paths = list_normalized_csv_files(data_root)
    if not paths:
        raise FileNotFoundError("no CSV found under {}".format(data_root))

    row0_cols, row1_cols = sensor_matrix_columns()
    class_order_set: Set[Tuple[float, float]] = set()
    for p in paths:
        df = pd.read_csv(p).sort_values("sample_index")
        class_order_set.add((float(df["ns_deg"].iloc[0]), float(df["ew_deg"].iloc[0])))

    class_order = sorted(class_order_set)
    pair_to_id = {pair: i for i, pair in enumerate(class_order)}

    x_train: List[np.ndarray] = []
    x_val: List[np.ndarray] = []
    x_test: List[np.ndarray] = []
    y_train: List[int] = []
    y_val: List[int] = []
    y_test: List[int] = []
    n_raw = 0
    n_dropped_dup = 0
    n_test_session_tail = 0
    n_test_standalone = 0
    standalone_files: List[str] = []
    rng = np.random.default_rng(standalone_test_seed)

    for p in paths:
        df = pd.read_csv(p).sort_values("sample_index")
        ns = float(df["ns_deg"].iloc[0])
        ew = float(df["ew_deg"].iloc[0])
        cid = pair_to_id[(ns, ew)]
        feats = df[row0_cols + row1_cols].to_numpy(dtype=np.float64)
        n = len(feats)
        n_raw += n
        in_session = is_session_csv_path(p, data_root)
        seen_in_file: Set[Tuple[float, ...]] = set()
        if in_session:
            n_train = int(n * train_ratio)
            n_val = int(n * val_ratio)
            for i, row in enumerate(feats):
                key = _feature_key(row)
                if key in seen_in_file:
                    n_dropped_dup += 1
                    continue
                seen_in_file.add(key)

                if i < n_train:
                    x_train.append(row)
                    y_train.append(cid)
                elif i < n_train + n_val:
                    x_val.append(row)
                    y_val.append(cid)
                else:
                    x_test.append(row)
                    y_test.append(cid)
                    n_test_session_tail += 1
        else:
            rel = os.path.relpath(p, data_root)
            standalone_files.append(rel.replace("\\", "/"))
            rows: List[np.ndarray] = []
            for row in feats:
                key = _feature_key(row)
                if key in seen_in_file:
                    n_dropped_dup += 1
                    continue
                seen_in_file.add(key)
                rows.append(row)
            if standalone_test_fraction < 1.0 and len(rows) > 0:
                k = max(1, int(round(len(rows) * standalone_test_fraction)))
                idx = rng.choice(len(rows), size=k, replace=False)
                rows = [rows[i] for i in sorted(idx)]
            for row in rows:
                x_test.append(row)
                y_test.append(cid)
                n_test_standalone += 1

    stats = {
        "n_raw_rows": n_raw,
        "n_duplicate_rows_dropped": n_dropped_dup,
        "n_train": len(y_train),
        "n_val": len(y_val),
        "n_test": len(y_test),
        "n_test_session_tail": n_test_session_tail,
        "n_test_standalone": n_test_standalone,
        "n_files": len(paths),
        "standalone_test_files": standalone_files,
        "standalone_test_fraction": standalone_test_fraction,
    }

    return (
        np.asarray(x_train, dtype=np.float64),
        np.asarray(x_val, dtype=np.float64),
        np.asarray(x_test, dtype=np.float64),
        np.asarray(y_train, dtype=np.int64),
        np.asarray(y_val, dtype=np.int64),
        np.asarray(y_test, dtype=np.int64),
        stats,
    )


def get_train_val_test_split(
    data_root: str,
    split_method: str,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    standalone_test_fraction: float = 1.0,
    standalone_test_seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    """Select split function by split_method."""
    if split_method in ("per_file_unique_blocks", "default"):
        return split_per_file_unique_blocks(
            data_root, train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio
        )
    if split_method == "session_generalization":
        return split_session_generalization(
            data_root,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            standalone_test_fraction=standalone_test_fraction,
            standalone_test_seed=standalone_test_seed,
        )
    raise ValueError("unknown split_method: {}".format(split_method))


def stratified_train_val_test_split(
    X: np.ndarray,
    y: np.ndarray,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Stratified random split (legacy; may leak duplicates across sets; kept for compatibility).
    """
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 1e-6:
        raise ValueError("train_ratio + val_ratio + test_ratio must be 1, got {}".format(total))

    stratify: Optional[np.ndarray] = y if np.min(np.bincount(y)) >= 2 else None

    holdout_ratio = val_ratio + test_ratio
    X_train, X_holdout, y_train, y_holdout = train_test_split(
        X,
        y,
        test_size=holdout_ratio,
        random_state=random_state,
        stratify=stratify,
    )

    if holdout_ratio <= 0:
        raise ValueError("val_ratio + test_ratio must be > 0")

    test_fraction_of_holdout = test_ratio / holdout_ratio
    stratify_holdout = y_holdout if np.min(np.bincount(y_holdout)) >= 2 else None
    X_val, X_test, y_val, y_test = train_test_split(
        X_holdout,
        y_holdout,
        test_size=test_fraction_of_holdout,
        random_state=random_state,
        stratify=stratify_holdout,
    )

    return X_train, X_val, X_test, y_train, y_val, y_test


def per_class_split_counts(
    y_train: np.ndarray,
    y_val: np.ndarray,
    y_test: np.ndarray,
    n_classes: int,
) -> Dict[str, List]:
    """Return per-class sample counts in train/val/test."""
    rows = []
    for cid in range(n_classes):
        rows.append(
            {
                "class_id": cid,
                "train": int(np.sum(y_train == cid)),
                "val": int(np.sum(y_val == cid)),
                "test": int(np.sum(y_test == cid)),
            }
        )
    return {"per_class": rows}
