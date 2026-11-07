import pytest

from src.block_rules import get_block_parts
from src.models import BodyPart, GridCell, LightType, SunAngles, UserCategory
from src.sunroom_control import compute_servo_angles
from src.user_profile import resolve_user_category


def test_resolve_user_category():
    assert resolve_user_category(10) == UserCategory.CHILDREN
    assert resolve_user_category(25, "tanning") == UserCategory.YOUNG_TANNING
    assert resolve_user_category(25, "relaxation") == UserCategory.YOUNG_RELAX
    assert resolve_user_category(50) == UserCategory.MIDDLE_AGED
    assert resolve_user_category(70) == UserCategory.ELDERLY


def test_uvb_children_none():
    parts = get_block_parts(UserCategory.CHILDREN, LightType.UVB)
    assert parts == frozenset()


def test_uvb_young_tanning():
    parts = get_block_parts(UserCategory.YOUNG_TANNING, LightType.UVB)
    assert parts == frozenset({BodyPart.TORSO, BodyPart.LIMBS})


def _grid_with_parts(parts_by_id: dict[int, BodyPart]) -> list[GridCell]:
    return [GridCell(grid_id=i, body_part=parts_by_id.get(i, BodyPart.EMPTY)) for i in range(1, 31)]


def test_classify_glass_orientation():
    from src.sunroom_control import classify_glass_orientation

    grid = _grid_with_parts({2: BodyPart.LIMBS, 3: BodyPart.TORSO, 1: BodyPart.HEAD})
    result = classify_glass_orientation(grid, UserCategory.YOUNG_TANNING, LightType.UVB)
    assert result.parallel_ids == [2, 3]
    assert result.perpendicular_ids == [1] + list(range(4, 31))


def test_compute_servo_angles_parallel_on_blocked_parts():
    grid = _grid_with_parts({1: BodyPart.HEAD, 2: BodyPart.LIMBS, 3: BodyPart.TORSO})
    sun = SunAngles(ns_angle=45, ew_zero=30)
    cmd = compute_servo_angles(
        grid,
        UserCategory.YOUNG_TANNING,
        LightType.UVB,
        sun,
    )
    assert cmd.ns_angle == 45
    assert cmd.small_angles[0] == 30  # Head not blocked for UVB tanning
    assert cmd.small_angles[1] == 120  # Limbs blocked -> parallel
    assert cmd.small_angles[2] == 120  # Torso blocked -> parallel


def test_compute_all_perpendicular_when_none():
    grid = _grid_with_parts({i: BodyPart.LIMBS for i in range(1, 31)})
    sun = SunAngles(ns_angle=10, ew_zero=20)
    cmd = compute_servo_angles(grid, UserCategory.CHILDREN, LightType.UVB, sun)
    assert all(a == 20 for a in cmd.small_angles)


def test_angle_clamp_at_180():
    grid = _grid_with_parts({1: BodyPart.HEAD})
    sun = SunAngles(ns_angle=200, ew_zero=100)
    cmd = compute_servo_angles(grid, UserCategory.ELDERLY, LightType.VIS, sun)
    assert cmd.ns_angle == 180
    assert cmd.small_angles[0] == 180  # 100+90 clamped
