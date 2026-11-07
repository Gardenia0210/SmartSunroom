from mechanical_control.models import BodyPart

# Fine class IDs -> coarse Chinese labels (CSV compat)
CLASS_TO_COARSE_CN: dict[int, str] = {
    1: "头部",
    2: "头部",
    9: "头部",
    3: "主体",
    4: "主体",
    5: "主体",
    7: "主体",
    16: "主体",
    12: "四肢",
    13: "四肢",
    14: "四肢",
    15: "四肢",
    6: "四肢",
}

CN_TO_BODY_PART: dict[str, BodyPart] = {
    "头部": BodyPart.HEAD,
    "主体": BodyPart.TORSO,
    "四肢": BodyPart.LIMBS,
    "空": BodyPart.EMPTY,
}

COARSE_COLORS: dict[str, tuple[int, int, int, int]] = {
    "Head": (255, 80, 80, 140),
    "Torso": (80, 200, 80, 140),
    "Limbs": (80, 120, 255, 140),
    "": (180, 180, 180, 60),
}

GRID_MASK_COLOR_OVERRIDE: dict[int, BodyPart] = {
    12: BodyPart.LIMBS,
    17: BodyPart.LIMBS,
}

# Logical overrides applied after model/CSV (used for angles + shading)
GRID_BODY_PART_OVERRIDE: dict[int, BodyPart] = {
    3: BodyPart.EMPTY,  # cell 3 forced empty (layout calibration)
}


def cn_label_to_body_part(label: str) -> BodyPart:
    return CN_TO_BODY_PART.get(label, BodyPart.EMPTY)
