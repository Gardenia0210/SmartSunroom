from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BodyPart(str, Enum):
    HEAD = "Head"
    TORSO = "Torso"
    LIMBS = "Limbs"
    EMPTY = ""


class UserCategory(str, Enum):
    CHILDREN = "Children"
    YOUNG_TANNING = "Young Adults (Tanning-oriented)"
    YOUNG_RELAX = "Young Adults (Relaxation-oriented)"
    MIDDLE_AGED = "Middle-aged Adults"
    ELDERLY = "Elderly"


class LightType(str, Enum):
    UVB = "UVB"
    UVA = "UVA"
    VIS = "VIS"
    NIR = "NIR"


@dataclass(frozen=True)
class GridCell:
    grid_id: int
    body_part: BodyPart


@dataclass(frozen=True)
class SunAngles:
    ns_angle: float
    ew_zero: float


@dataclass(frozen=True)
class ServoCommand:
    ns_angle: int
    small_angles: list[int]

    def __post_init__(self) -> None:
        if len(self.small_angles) != 30:
            raise ValueError("small_angles must have length 30")
