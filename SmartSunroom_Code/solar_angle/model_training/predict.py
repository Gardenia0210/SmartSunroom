"""
Load the model from train.py and predict one normalized (2,4) matrix.

Example:
  python predict.py --matrix "0.1,-0.2,..."   # 8 floats: row0 then row1, same order as classes.json
"""
from __future__ import print_function

import argparse
import json
import os
import sys

import joblib
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    ap = argparse.ArgumentParser(description="Inference: 8-D features -> angle class")
    ap.add_argument("--artifacts", default=os.path.join(ROOT, "artifacts"), help="contains model.joblib and classes.json")
    ap.add_argument(
        "--matrix",
        required=True,
        help="8 floats, comma-separated: E1 S1 W1 N1, E2 S2 W2 N2 (collection CSV order)",
    )
    args = ap.parse_args()

    model_path = os.path.join(args.artifacts, "model.joblib")
    classes_path = os.path.join(args.artifacts, "classes.json")
    if not os.path.isfile(model_path):
        print("model not found; run train.py first:", model_path, file=sys.stderr)
        sys.exit(1)

    vec = np.array([float(x.strip()) for x in args.matrix.split(",")], dtype=np.float64)
    if vec.size != 8:
        print("need 8 values, got:", vec.size, file=sys.stderr)
        sys.exit(1)

    clf = joblib.load(model_path)
    cid = int(clf.predict(vec.reshape(1, -1))[0])

    with open(classes_path, encoding="utf-8") as f:
        meta = json.load(f)
    row = next(x for x in meta["classes"] if x["class_id"] == cid)
    print("predicted class id:", cid)
    print("ns_deg:", row["ns_deg"], "ew_deg:", row["ew_deg"])


if __name__ == "__main__":
    main()
