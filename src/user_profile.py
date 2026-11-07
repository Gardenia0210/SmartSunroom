from __future__ import annotations

from src.models import UserCategory


class YoungAdultMode:
    TANNING = "tanning"
    RELAXATION = "relaxation"


def resolve_user_category(age: int, young_mode: str | None = None) -> UserCategory:
    if not 0 <= age <= 100:
        raise ValueError("age must be between 0 and 100")

    if age <= 14:
        return UserCategory.CHILDREN
    if age <= 44:
        if young_mode is None:
            raise ValueError("young_mode required for age 15-44 (tanning or relaxation)")
        mode = young_mode.lower()
        if mode == YoungAdultMode.TANNING:
            return UserCategory.YOUNG_TANNING
        if mode == YoungAdultMode.RELAXATION:
            return UserCategory.YOUNG_RELAX
        raise ValueError("young_mode must be 'tanning' or 'relaxation'")
    if age <= 60:
        return UserCategory.MIDDLE_AGED
    return UserCategory.ELDERLY
