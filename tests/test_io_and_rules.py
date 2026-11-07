import csv
import tempfile
from pathlib import Path

import pytest

from src.block_rules import BLOCK_RULES, get_block_parts
from src.bodypart.grid_mapper import load_grid_csv, save_grid_csv
from src.models import BodyPart, GridCell, LightType, UserCategory


def test_block_rules_cover_all_combinations():
    lights = list(LightType)
    users = list(UserCategory)
    assert len(BLOCK_RULES) == len(lights) * len(users)
    for light in lights:
        for user in users:
            get_block_parts(user, light)


def test_load_grid_csv_roundtrip():
    grid = [
        GridCell(grid_id=i, body_part=BodyPart.HEAD if i == 1 else BodyPart.EMPTY)
        for i in range(1, 31)
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "grid.csv"
        save_grid_csv(path, grid)
        loaded = load_grid_csv(path)
    assert len(loaded) == 30
    assert loaded[0].body_part == BodyPart.HEAD
    assert loaded[1].body_part == BodyPart.EMPTY


def test_load_grid_csv_cn_labels():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "grid.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["grid_id", "col", "row", "bodypart"])
            for i in range(1, 31):
                label = "头部" if i == 5 else "空"
                w.writerow([i, 1, 1, label])
        loaded = load_grid_csv(path)
    assert loaded[4].body_part == BodyPart.HEAD
