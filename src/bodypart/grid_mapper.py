from __future__ import annotations

import csv
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

from src.bodypart.class_map import (
    CLASS_TO_COARSE_CN,
    COARSE_COLORS,
    GRID_BODY_PART_OVERRIDE,
    GRID_MASK_COLOR_OVERRIDE,
    cn_label_to_body_part,
)
from src.config import (
    BLOCK_DIM_FILL,
    BLOCK_HIGHLIGHT_FILL,
    BLOCK_HIGHLIGHT_OUTLINE,
    GRID_COLS,
    GRID_ROWS,
)
from src.models import BodyPart, GridCell


def dominant_coarse_in_region(mask: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> str:
    region = mask[y0:y1, x0:x1]
    counts: dict[str, int] = {"头部": 0, "主体": 0, "四肢": 0}
    for cls_id, coarse in CLASS_TO_COARSE_CN.items():
        counts[coarse] += int(np.sum(region == cls_id))
    best = max(counts, key=counts.get)
    if counts[best] == 0:
        return "空"
    return best


def build_grid(
    mask: np.ndarray,
    cols: int = GRID_COLS,
    rows: int = GRID_ROWS,
) -> list[GridCell]:
    h, w = mask.shape
    cell_w = w / cols
    cell_h = h / rows
    cells: list[GridCell] = []

    for row in range(rows):
        for col in range(cols):
            grid_id = row * cols + col + 1
            x0 = int(col * cell_w)
            y0 = int(row * cell_h)
            x1 = int((col + 1) * cell_w) if col < cols - 1 else w
            y1 = int((row + 1) * cell_h) if row < rows - 1 else h
            cn_label = dominant_coarse_in_region(mask, x0, y0, x1, y1)
            part = cn_label_to_body_part(cn_label)
            part = GRID_BODY_PART_OVERRIDE.get(grid_id, part)
            cells.append(GridCell(grid_id=grid_id, body_part=part))

    return cells


def draw_grid_result(
    image_pil: Image.Image,
    grid: list[GridCell],
    cols: int = GRID_COLS,
    rows: int = GRID_ROWS,
) -> Image.Image:
    img = image_pil.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    w, h = img.size
    cell_w = w / cols
    cell_h = h / rows

    for cell in grid:
        row = (cell.grid_id - 1) // cols
        col = (cell.grid_id - 1) % cols
        x0 = int(col * cell_w)
        y0 = int(row * cell_h)
        x1 = int((col + 1) * cell_w) if col < cols - 1 else w
        y1 = int((row + 1) * cell_h) if row < rows - 1 else h
        part = GRID_BODY_PART_OVERRIDE.get(
            cell.grid_id,
            GRID_MASK_COLOR_OVERRIDE.get(cell.grid_id, cell.body_part),
        )
        color = COARSE_COLORS[part.value]
        draw_overlay.rectangle([x0, y0, x1 - 1, y1 - 1], fill=color)

    composed = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(composed)

    for col in range(cols + 1):
        x = int(col * cell_w)
        draw.line([(x, 0), (x, h)], fill=(255, 255, 0), width=1)
    for row in range(rows + 1):
        y = int(row * cell_h)
        draw.line([(0, y), (w, y)], fill=(255, 255, 0), width=1)

    for cell in grid:
        row = (cell.grid_id - 1) // cols
        col = (cell.grid_id - 1) % cols
        x = int(col * cell_w + 4)
        y = int(row * cell_h + 4)
        label_part = GRID_BODY_PART_OVERRIDE.get(cell.grid_id, cell.body_part)
        label = label_part.value if label_part != BodyPart.EMPTY else "空"
        draw.text((x, y), f"{cell.grid_id}:{label}", fill=(255, 255, 255))

    return composed.convert("RGB")


def draw_block_highlight(
    image_pil: Image.Image,
    grid: list[GridCell],
    parallel_ids: set[int] | list[int],
    cols: int = GRID_COLS,
    rows: int = GRID_ROWS,
) -> Image.Image:
    """在分割网格图上高亮「需遮挡阳光」的玻璃板（parallel）。"""
    block_ids = set(parallel_ids)
    img = image_pil.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    w, h = img.size
    cell_w = w / cols
    cell_h = h / rows

    for cell in grid:
        row = (cell.grid_id - 1) // cols
        col = (cell.grid_id - 1) % cols
        x0 = int(col * cell_w)
        y0 = int(row * cell_h)
        x1 = int((col + 1) * cell_w) if col < cols - 1 else w
        y1 = int((row + 1) * cell_h) if row < rows - 1 else h
        box = [x0, y0, x1 - 1, y1 - 1]
        if cell.grid_id in block_ids:
            draw_overlay.rectangle(box, fill=BLOCK_HIGHLIGHT_FILL)
        else:
            draw_overlay.rectangle(box, fill=BLOCK_DIM_FILL)

    composed = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(composed)

    for col in range(cols + 1):
        x = int(col * cell_w)
        draw.line([(x, 0), (x, h)], fill=(220, 220, 220), width=1)
    for row in range(rows + 1):
        y = int(row * cell_h)
        draw.line([(0, y), (w, y)], fill=(220, 220, 220), width=1)

    outline = BLOCK_HIGHLIGHT_OUTLINE
    for cell in grid:
        row = (cell.grid_id - 1) // cols
        col = (cell.grid_id - 1) % cols
        x0 = int(col * cell_w)
        y0 = int(row * cell_h)
        x1 = int((col + 1) * cell_w) if col < cols - 1 else w
        y1 = int((row + 1) * cell_h) if row < rows - 1 else h
        label = cell.body_part.value if cell.body_part != BodyPart.EMPTY else "空"
        if cell.grid_id in block_ids:
            draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=outline, width=4)
            tag = f"{cell.grid_id}:{label} shade"
            draw.text((x0 + 4, y0 + 4), tag, fill=outline)
        else:
            draw.text((x0 + 4, y0 + 4), f"{cell.grid_id}:{label}", fill=(220, 220, 220))

    draw.rectangle([8, h - 36, 28, h - 16], fill=(255, 48, 48), outline=outline, width=2)
    draw.text((34, h - 34), "Highlight = panels to shade (parallel to sun)", fill=(255, 255, 255))

    return composed.convert("RGB")


def blank_grid_canvas(
    cols: int = GRID_COLS,
    rows: int = GRID_ROWS,
    cell_px: int = 96,
) -> Image.Image:
    w, h = cols * cell_px, rows * cell_px
    img = Image.new("RGB", (w, h), (40, 44, 52))
    draw = ImageDraw.Draw(img)
    for c in range(cols + 1):
        x = c * cell_px
        draw.line([(x, 0), (x, h)], fill=(90, 90, 90), width=1)
    for r in range(rows + 1):
        y = r * cell_px
        draw.line([(0, y), (w, y)], fill=(90, 90, 90), width=1)
    return img


def save_grid_csv(path: Path, grid: list[GridCell], cols: int = GRID_COLS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["grid_id", "col", "row", "bodypart"])
        for cell in grid:
            col = (cell.grid_id - 1) % cols
            row = (cell.grid_id - 1) // cols
            part = cell.body_part.value if cell.body_part != BodyPart.EMPTY else "空"
            writer.writerow([cell.grid_id, col + 1, row + 1, part])


def load_grid_csv(path: Path) -> list[GridCell]:
    """从 detect 导出的 CSV 读取 30 格人体部位。"""
    cells: list[GridCell] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            grid_id = int(row["grid_id"])
            raw = (row.get("bodypart") or "").strip()
            if raw in ("空", "", "EMPTY"):
                part = BodyPart.EMPTY
            else:
                try:
                    part = BodyPart(raw)
                except ValueError:
                    part = cn_label_to_body_part(raw)
            cells.append(GridCell(grid_id=grid_id, body_part=part))
    cells.sort(key=lambda c: c.grid_id)
    if len(cells) != 30:
        raise ValueError(f"expected 30 grid rows, got {len(cells)}")
    # 与 build_grid 一致：应用强制覆盖（如 3 号格恒为空）
    overridden: list[GridCell] = []
    for cell in cells:
        part = GRID_BODY_PART_OVERRIDE.get(cell.grid_id, cell.body_part)
        overridden.append(
            cell if part is cell.body_part else GridCell(grid_id=cell.grid_id, body_part=part)
        )
    return overridden