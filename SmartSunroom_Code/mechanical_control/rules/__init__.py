"""Shading rules and servo angle computation."""

from mechanical_control.rules.block_rules import BLOCK_RULES, get_block_parts
from mechanical_control.rules.user_profile import YoungAdultMode, resolve_user_category
from mechanical_control.rules.sunroom_control import (
    GlassOrientationResult,
    classify_glass_orientation,
    clamp_angle,
    compute_servo_angles,
    format_glass_orientation,
    logical_ns_to_servo,
    resolve_ns_servo,
    with_ns_servo,
)

__all__ = [
    "BLOCK_RULES",
    "GlassOrientationResult",
    "YoungAdultMode",
    "classify_glass_orientation",
    "clamp_angle",
    "compute_servo_angles",
    "format_glass_orientation",
    "get_block_parts",
    "logical_ns_to_servo",
    "resolve_ns_servo",
    "resolve_user_category",
    "with_ns_servo",
]
