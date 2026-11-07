from pathlib import Path

from src.config import DEFAULT_POS1_GRID_CSV
from src.models import LightType
from src.pipeline import render_block_highlight_preview
from src.sunroom_control import classify_glass_orientation
from src.bodypart.grid_mapper import load_grid_csv
from src.user_profile import resolve_user_category


def test_pos1_uvb_relax_block_ids():
    grid = load_grid_csv(DEFAULT_POS1_GRID_CSV)
    user = resolve_user_category(25, "relaxation")
    # UVB + Young Relax → 遮挡 Limbs
    orient = classify_glass_orientation(grid, user, LightType.UVB)
    assert orient.parallel_ids
    assert all(
        grid[i - 1].body_part.value == "Limbs" for i in orient.parallel_ids
    )


def test_render_block_highlight_writes_png(tmp_path: Path):
    out, orient = render_block_highlight_preview(
        grid_csv=DEFAULT_POS1_GRID_CSV,
        age=25,
        light=LightType.UVB,
        young_mode="relaxation",
        output_dir=tmp_path,
    )
    assert out.is_file()
    assert out.suffix == ".png"
    assert "UVB" in out.name
    assert orient.parallel_ids
