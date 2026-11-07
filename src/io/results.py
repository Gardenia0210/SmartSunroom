from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from src.models import BodyPart, GridCell, LightType, ServoCommand, SunAngles, UserCategory


@dataclass
class SessionRecord:
    timestamp: str
    user: str
    light: str
    ns_angle: float
    ew_zero: float
    ns_servo: int
    small_angles: list[int]
    grid: list[dict]


def save_servo_csv(path: Path, grid: list[GridCell], cmd: ServoCommand, ew_zero: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_id = {c.grid_id: c for c in grid}
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["servo_id", "grid_id", "bodypart", "angle", "mode"])
        for i, angle in enumerate(cmd.small_angles, start=1):
            cell = by_id.get(i)
            part = cell.body_part.value if cell and cell.body_part != BodyPart.EMPTY else "空"
            mode = "parallel" if angle != int(ew_zero) else "perpendicular"
            writer.writerow([i, i, part, angle, mode])
        writer.writerow(["ns", "", "", cmd.ns_angle, "big_servo"])


def save_session_json(path: Path, record: SessionRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=2), encoding="utf-8")


def make_session_record(
    user: UserCategory,
    light: LightType,
    sun: SunAngles,
    grid: list[GridCell],
    cmd: ServoCommand,
) -> SessionRecord:
    return SessionRecord(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        user=user.value,
        light=light.value,
        ns_angle=sun.ns_angle,
        ew_zero=sun.ew_zero,
        ns_servo=cmd.ns_angle,
        small_angles=list(cmd.small_angles),
        grid=[
            {
                "grid_id": c.grid_id,
                "bodypart": c.body_part.value if c.body_part != BodyPart.EMPTY else "空",
            }
            for c in grid
        ],
    )
