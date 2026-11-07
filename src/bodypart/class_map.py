from src.models import BodyPart

# 模型细分类 ID -> 中文粗分类
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

# 网格逻辑覆盖：覆盖模型/CSV 识别结果（完整流程算角、遮挡均以此为准）
GRID_BODY_PART_OVERRIDE: dict[int, BodyPart] = {
    3: BodyPart.EMPTY,  # 3 号格恒定为「空」（不再当作 Head）
}


def cn_label_to_body_part(label: str) -> BodyPart:
    return CN_TO_BODY_PART.get(label, BodyPart.EMPTY)
