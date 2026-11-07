"""
Train classifier on normalized CSVs: input is a (2,4) matrix (flattened to 8-D),
output is the (N-S, E-W) angle-pair class present in the dataset.

Default: chronological 80/10/10 split per CSV, drop duplicate readings to avoid leakage.
Default data dir: ../data_collection/data_normalized
Model output: artifacts/model.joblib, artifacts/classes.json
"""
from __future__ import print_function

import argparse
import json
import os
import sys
from typing import Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

_COLLECTOR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data_collection"))
if _COLLECTOR not in sys.path:
    sys.path.insert(0, _COLLECTOR)
import config  # noqa: E402

from dataset import (  # noqa: E402
    count_exact_feature_overlap,
    get_train_val_test_split,
    load_xy_from_normalized_dir,
    per_class_split_counts,
)


def _apply_label_noise(y: np.ndarray, noise_rate: float, n_classes: int, rng: np.random.Generator) -> np.ndarray:
    """Randomly replace training labels (fit only)."""
    if noise_rate <= 0.0:
        return y
    y_noisy = y.copy()
    n = len(y)
    n_flip = int(round(n * noise_rate))
    if n_flip <= 0:
        return y_noisy
    idx = rng.choice(n, size=min(n_flip, n), replace=False)
    for i in idx:
        choices = [c for c in range(n_classes) if c != y[i]]
        if choices:
            y_noisy[i] = int(rng.choice(choices))
    return y_noisy


def _augment_features(X: np.ndarray, noise_std: float, copies: int, rng: np.random.Generator) -> Tuple[np.ndarray, np.ndarray]:
    """Duplicate training features with Gaussian noise; return (X_aug, repeat_indices)."""
    if noise_std <= 0.0 or copies <= 1:
        return X, np.arange(len(X))
    parts = [X]
    for _ in range(copies - 1):
        parts.append(X + rng.normal(0.0, noise_std, size=X.shape))
    X_aug = np.vstack(parts)
    rep_idx = np.tile(np.arange(len(X)), copies)
    return X_aug, rep_idx


def _eval_split(name, y_true, y_pred, class_order):
    labels = list(range(len(class_order)))
    acc = accuracy_score(y_true, y_pred)
    p_macro, r_macro, f_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )
    p_w, r_w, f_w, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="weighted", zero_division=0
    )
    print("=== {} (n={}) ===".format(name, len(y_true)))
    target_names = ["ns_{}_ew_{}".format(ns, ew) for ns, ew in class_order]
    print(
        classification_report(
            y_true,
            y_pred,
            labels=labels,
            target_names=target_names,
            zero_division=0,
        )
    )
    return {
        "n_samples": int(len(y_true)),
        "accuracy": float(acc),
        "precision_macro": float(p_macro),
        "recall_macro": float(r_macro),
        "f1_macro": float(f_macro),
        "precision_weighted": float(p_w),
        "recall_weighted": float(r_w),
        "f1_weighted": float(f_w),
    }


def main() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    default_data = os.path.abspath(os.path.join(root, "..", "data_collection", "data_normalized"))
    default_out = os.path.join(root, "artifacts")

    ap = argparse.ArgumentParser(description="Photoresistor 2x4 matrix -> angle class")
    ap.add_argument("--data-dir", default=default_data, help="normalized CSV root")
    ap.add_argument("--out-dir", default=default_out, help="save model and class table")
    ap.add_argument("--train-ratio", type=float, default=0.8, help="train ratio")
    ap.add_argument("--val-ratio", type=float, default=0.1, help="val ratio")
    ap.add_argument("--test-ratio", type=float, default=0.1, help="test ratio")
    ap.add_argument("--seed", type=int, default=42, help="random seed")
    ap.add_argument("--trees", type=int, default=200, help="random-forest tree count")
    ap.add_argument("--max-depth", type=int, default=8, help="max tree depth (reduce overfitting)")
    ap.add_argument("--min-samples-leaf", type=int, default=2, help="min samples per leaf")
    ap.add_argument(
        "--split-method",
        default="session_generalization",
        choices=["per_file_unique_blocks", "session_generalization"],
        help="data split strategy",
    )
    ap.add_argument(
        "--standalone-test-fraction",
        type=float,
        default=0.12,
        help="fraction of non-session CSVs used for test (0,1] (default 0.12)",
    )
    ap.add_argument("--feature-noise-std", type=float, default=0.0, help="train feature Gaussian noise std")
    ap.add_argument("--feature-noise-copies", type=int, default=1, help="augmentation copies including original")
    ap.add_argument("--label-noise-rate", type=float, default=0.0, help="label flip rate on train [0,1)")
    args = ap.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    _, _, class_order = load_xy_from_normalized_dir(data_dir)
    n_classes = len(class_order)

    X_train, X_val, X_test, y_train, y_val, y_test, split_stats = get_train_val_test_split(
        data_dir,
        split_method=args.split_method,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        standalone_test_fraction=args.standalone_test_fraction,
        standalone_test_seed=args.seed,
    )

    overlap_train_test = count_exact_feature_overlap(X_train, X_test)
    overlap_train_val = count_exact_feature_overlap(X_train, X_val)

    print("split strategy:", args.split_method)
    if args.split_method == "session_generalization":
        print(
            "test set: session tail {} + standalone {}".format(
                split_stats.get("n_test_session_tail", "?"),
                split_stats.get("n_test_standalone", "?"),
            )
        )
    print(
        "raw rows: {}, after dedupe: {}, unique train/val/test: {}/{}/{}".format(
            split_stats["n_raw_rows"],
            split_stats["n_duplicate_rows_dropped"],
            split_stats["n_train"],
            split_stats["n_val"],
            split_stats["n_test"],
        )
    )
    print("num classes:", n_classes)
    print("exact feature overlaps train/test:", overlap_train_test, " (should be 0)")

    clf = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=args.trees,
                    max_depth=args.max_depth,
                    min_samples_leaf=args.min_samples_leaf,
                    random_state=args.seed,
                    class_weight="balanced_subsample",
                    n_jobs=-1,
                ),
            ),
        ]
    )

    rng = np.random.default_rng(args.seed)
    y_fit = _apply_label_noise(y_train, args.label_noise_rate, n_classes, rng)
    X_fit, rep_idx = _augment_features(X_train, args.feature_noise_std, args.feature_noise_copies, rng)
    y_fit = y_fit[rep_idx]

    clf.fit(X_fit, y_fit)

    metrics = {
        "train": _eval_split("train", y_train, clf.predict(X_train), class_order),
        "val": _eval_split("val", y_val, clf.predict(X_val), class_order),
        "test": _eval_split("test", y_test, clf.predict(X_test), class_order),
    }

    model_path = os.path.join(out_dir, "model.joblib")
    classes_path = os.path.join(out_dir, "classes.json")
    meta_path = os.path.join(out_dir, "train_meta.json")
    metrics_path = os.path.join(out_dir, "eval_metrics.json")
    split_path = os.path.join(out_dir, "split_summary.json")

    joblib.dump(clf, model_path)

    classes_payload = {
        "input_layout": {
            "shape": [2, 4],
            "description": "Rows: resistor 1/2 per direction; columns: four directions in rows_order.",
            "rows_order": list(config.ROWS_ORDER),
            "row0_columns": ["{}_1".format(d) for d in config.ROWS_ORDER],
            "row1_columns": ["{}_2".format(d) for d in config.ROWS_ORDER],
        },
        "output_type": "classification",
        "classes": [
            {"class_id": i, "ns_deg": float(ns), "ew_deg": float(ew)}
            for i, (ns, ew) in enumerate(class_order)
        ],
    }

    with open(classes_path, "w", encoding="utf-8") as f:
        json.dump(classes_payload, f, indent=2, ensure_ascii=False)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "data_dir": data_dir,
                "split_method": args.split_method,
                "n_samples_raw": split_stats["n_raw_rows"],
                "n_samples_unique": split_stats["n_train"] + split_stats["n_val"] + split_stats["n_test"],
                "n_duplicate_rows_dropped": split_stats["n_duplicate_rows_dropped"],
                "train_test_feature_overlap": overlap_train_test,
                "train_val_feature_overlap": overlap_train_val,
                "n_classes": n_classes,
                "train_ratio": args.train_ratio,
                "val_ratio": args.val_ratio,
                "test_ratio": args.test_ratio,
                "standalone_test_fraction": args.standalone_test_fraction,
                "n_test_session_tail": split_stats.get("n_test_session_tail"),
                "n_test_standalone": split_stats.get("n_test_standalone"),
                "standalone_test_files": split_stats.get("standalone_test_files"),
                "random_seed": args.seed,
                "n_estimators": args.trees,
                "max_depth": args.max_depth,
                "min_samples_leaf": args.min_samples_leaf,
                "feature_noise_std": args.feature_noise_std,
                "feature_noise_copies": args.feature_noise_copies,
                "label_noise_rate": args.label_noise_rate,
                "n_train": split_stats["n_train"],
                "n_val": split_stats["n_val"],
                "n_test": split_stats["n_test"],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    split_summary = per_class_split_counts(y_train, y_val, y_test, n_classes)
    split_summary["totals"] = {
        "train": int(len(y_train)),
        "val": int(len(y_val)),
        "test": int(len(y_test)),
    }
    split_summary["split_method"] = args.split_method
    with open(split_path, "w", encoding="utf-8") as f:
        json.dump(split_summary, f, indent=2, ensure_ascii=False)

    print("saved:", model_path)
    print("classes:", classes_path)
    print("metrics:", metrics_path)
    print("split stats:", split_path)


if __name__ == "__main__":
    main()
