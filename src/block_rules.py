from __future__ import annotations

from src.models import BodyPart, LightType, UserCategory

BLOCK_RULES: dict[tuple[LightType, UserCategory], frozenset[BodyPart]] = {
    (LightType.UVB, UserCategory.CHILDREN): frozenset(),
    (LightType.UVB, UserCategory.YOUNG_TANNING): frozenset({BodyPart.TORSO, BodyPart.LIMBS}),
    (LightType.UVB, UserCategory.YOUNG_RELAX): frozenset({BodyPart.LIMBS}),
    (LightType.UVB, UserCategory.MIDDLE_AGED): frozenset({BodyPart.HEAD, BodyPart.TORSO, BodyPart.LIMBS}),
    (LightType.UVB, UserCategory.ELDERLY): frozenset({BodyPart.TORSO, BodyPart.LIMBS}),
    (LightType.UVA, UserCategory.CHILDREN): frozenset(),
    (LightType.UVA, UserCategory.YOUNG_TANNING): frozenset({BodyPart.LIMBS}),
    (LightType.UVA, UserCategory.YOUNG_RELAX): frozenset(),
    (LightType.UVA, UserCategory.MIDDLE_AGED): frozenset(),
    (LightType.UVA, UserCategory.ELDERLY): frozenset(),
    (LightType.VIS, UserCategory.CHILDREN): frozenset({BodyPart.HEAD, BodyPart.TORSO, BodyPart.LIMBS}),
    (LightType.VIS, UserCategory.YOUNG_TANNING): frozenset({BodyPart.HEAD}),
    (LightType.VIS, UserCategory.YOUNG_RELAX): frozenset({BodyPart.HEAD, BodyPart.TORSO}),
    (LightType.VIS, UserCategory.MIDDLE_AGED): frozenset({BodyPart.TORSO}),
    (LightType.VIS, UserCategory.ELDERLY): frozenset({BodyPart.HEAD}),
    (LightType.NIR, UserCategory.CHILDREN): frozenset({BodyPart.HEAD, BodyPart.TORSO, BodyPart.LIMBS}),
    (LightType.NIR, UserCategory.YOUNG_TANNING): frozenset({BodyPart.HEAD}),
    (LightType.NIR, UserCategory.YOUNG_RELAX): frozenset({BodyPart.TORSO}),
    (LightType.NIR, UserCategory.MIDDLE_AGED): frozenset({BodyPart.TORSO, BodyPart.LIMBS}),
    (LightType.NIR, UserCategory.ELDERLY): frozenset({BodyPart.LIMBS}),
}


def get_block_parts(user: UserCategory, light: LightType) -> frozenset[BodyPart]:
    key = (light, user)
    if key not in BLOCK_RULES:
        raise KeyError(f"no block rule for {light} + {user}")
    return BLOCK_RULES[key]
