from __future__ import annotations

from dataclasses import dataclass

from src.block_rules import get_block_parts
from src.config import BIG_SERVO_ZERO_DEG, DEMO_BIG_SERVO_ABS_DEG, DEMO_EW_DEG
from src.models import BodyPart, GridCell, LightType, ServoCommand, SunAngles, UserCategory


@dataclass(frozen=True)
class GlassOrientationResult:
    parallel_ids: list[int]
    perpendicular_ids: list[int]
    details: list[tuple[int, BodyPart, str]]  # grid_id, bodypart, parallel|perpendicular


def clamp_angle(angle: float, lo: int = 0, hi: int = 180) -> int:
    return int(max(lo, min(hi, round(angle))))


def logical_ns_to_servo(
    ns_logical: float,
    *,
    zero: float = BIG_SERVO_ZERO_DEG,
) -> int:
    """逻辑南北角 → 大舵机绝对角（机械零点 + 逻辑角）。"""
    return clamp_angle(zero + ns_logical)


def resolve_ns_servo(
    ns_logical: float,
    *,
    abs_override: int | None = None,
    zero: float = BIG_SERVO_ZERO_DEG,
) -> int:
    if abs_override is not None:
        return clamp_angle(abs_override)
    return logical_ns_to_servo(ns_logical, zero=zero)


def with_ns_servo(cmd: ServoCommand, ns_abs: int) -> ServoCommand:
    return ServoCommand(ns_angle=clamp_angle(ns_abs), small_angles=list(cmd.small_angles))


def demo_big_servo_hold_command(
    *,
    ns_abs: int = DEMO_BIG_SERVO_ABS_DEG,
    ew_zero: float = DEMO_EW_DEG,
) -> ServoCommand:
    """演示第二步：大舵机到位，小舵机暂全部垂直（ew_zero）。"""
    hold = clamp_angle(ew_zero)
    return ServoCommand(ns_angle=clamp_angle(ns_abs), small_angles=[hold] * 30)


def classify_glass_orientation(
    grid: list[GridCell],
    user: UserCategory,
    light: LightType,
) -> GlassOrientationResult:
    block_parts = get_block_parts(user, light)
    parallel_ids: list[int] = []
    perpendicular_ids: list[int] = []
    details: list[tuple[int, BodyPart, str]] = []

    for cell in sorted(grid, key=lambda c: c.grid_id):
        if cell.body_part in block_parts and cell.body_part != BodyPart.EMPTY:
            parallel_ids.append(cell.grid_id)
            details.append((cell.grid_id, cell.body_part, "parallel"))
        else:
            perpendicular_ids.append(cell.grid_id)
            details.append((cell.grid_id, cell.body_part, "perpendicular"))

    return GlassOrientationResult(
        parallel_ids=parallel_ids,
        perpendicular_ids=perpendicular_ids,
        details=details,
    )


def format_glass_orientation(result: GlassOrientationResult) -> str:
    def fmt_ids(ids: list[int]) -> str:
        return ", ".join(str(i) for i in ids) if ids else "（无）"

    parallel_detail = []
    perpendicular_detail = []
    for grid_id, part, mode in result.details:
        label = part.value if part != BodyPart.EMPTY else "空"
        line = f"{grid_id}({label})"
        if mode == "parallel":
            parallel_detail.append(line)
        else:
            perpendicular_detail.append(line)

    lines = [
        "=== 玻璃板朝向（相对太阳）===",
        f"与太阳平行（ew_zero+90°，遮挡）序号: {fmt_ids(result.parallel_ids)}",
        f"  明细: {', '.join(parallel_detail) if parallel_detail else '（无）'}",
        f"与太阳垂直（ew_zero，不遮挡）序号:   {fmt_ids(result.perpendicular_ids)}",
        f"  明细: {', '.join(perpendicular_detail) if perpendicular_detail else '（无）'}",
    ]
    return "\n".join(lines)


def compute_servo_angles(    grid: list[GridCell],
    user: UserCategory,
    light: LightType,
    sun: SunAngles,
) -> ServoCommand:
    if len(grid) != 30:
        raise ValueError("grid must contain exactly 30 cells")

    block_parts = get_block_parts(user, light)
    by_id = {cell.grid_id: cell for cell in grid}

    small_angles: list[int] = []
    for grid_id in range(1, 31):
        cell = by_id.get(grid_id)
        if cell is None:
            raise ValueError(f"missing grid_id {grid_id}")

        if cell.body_part in block_parts and cell.body_part != BodyPart.EMPTY:
            angle = sun.ew_zero + 90
        else:
            angle = sun.ew_zero
        small_angles.append(clamp_angle(angle))

    return ServoCommand(
        ns_angle=clamp_angle(sun.ns_angle),
        small_angles=small_angles,
    )
