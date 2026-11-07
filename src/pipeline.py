from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from src.bodypart.camera import capture_one
from src.bodypart.grid_mapper import (
    blank_grid_canvas,
    build_grid,
    draw_block_highlight,
    draw_grid_result,
    load_grid_csv,
    save_grid_csv,
)
from src.bodypart.segmentation import run_segmentation
from src.config import (
    DEFAULT_MODEL,
    DEMO_BIG_SERVO_ABS_DEG,
    DEMO_EW_DEG,
    OUTPUTS_DIR,
    PHOTOS_DIR,
)
from src.io.results import make_session_record, save_servo_csv, save_session_json
from src.models import GridCell, LightType, ServoCommand, SunAngles, UserCategory
from src.serial.mega_client import MegaClient, dispatch_servo_command
from src.sunroom_control import (
    GlassOrientationResult,
    classify_glass_orientation,
    compute_servo_angles,
    demo_big_servo_hold_command,
    format_glass_orientation,
    with_ns_servo,
)
from src.user_profile import resolve_user_category


@dataclass
class AnalyzeResult:
    detection: DetectionResult
    user: UserCategory
    light: LightType
    sun: SunAngles
    orientation: GlassOrientationResult
    servo_cmd: ServoCommand
    orientation_txt: Path
    servo_csv: Path
    session_json: Path


@dataclass
class DetectionResult:
    image_path: Path
    grid: list[GridCell]
    grid_csv: Path
    grid_png: Path
    mask_png: Path


@dataclass
class ControlResult:
    user: UserCategory
    light: LightType
    sun: SunAngles
    grid: list[GridCell]
    servo_cmd: ServoCommand
    servo_csv: Path
    session_json: Path


def detect_from_image(
    image_path: Path,
    output_dir: Path | None = None,
    model_name: str = DEFAULT_MODEL,
    name: str | None = None,
) -> DetectionResult:
    output_dir = output_dir or OUTPUTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    mask, image_pil = run_segmentation(image_path, model_name=model_name)
    grid = build_grid(mask)

    stem = name or image_path.stem
    grid_csv = output_dir / f"{stem}_grid_5x6.csv"
    grid_png = output_dir / f"{stem}_grid_5x6.png"
    mask_png = output_dir / f"{stem}_mask.png"

    save_grid_csv(grid_csv, grid)
    draw_grid_result(image_pil, grid).save(grid_png)
    Image.fromarray(mask).save(mask_png)

    return DetectionResult(
        image_path=image_path,
        grid=grid,
        grid_csv=grid_csv,
        grid_png=grid_png,
        mask_png=mask_png,
    )


def analyze_from_image(
    image_path: Path,
    age: int,
    light: LightType,
    sun: SunAngles,
    young_mode: str | None = None,
    output_dir: Path | None = None,
    model_name: str = DEFAULT_MODEL,
    name: str | None = None,
) -> AnalyzeResult:
    """纯软件流程：分割 → 判定平行/垂直玻璃序号（不涉及串口）。"""
    output_dir = output_dir or OUTPUTS_DIR
    user = resolve_user_category(age, young_mode)

    det = detect_from_image(image_path, output_dir=output_dir, model_name=model_name, name=name)
    orientation = classify_glass_orientation(det.grid, user, light)
    servo_cmd = compute_servo_angles(det.grid, user, light, sun)

    stem = name or image_path.stem
    orientation_txt = output_dir / f"{stem}_orientation.txt"
    servo_csv = output_dir / f"{stem}_servos.csv"
    session_json = output_dir / f"{stem}_session.json"

    orientation_txt.write_text(
        format_glass_orientation(orientation) + "\n",
        encoding="utf-8",
    )
    save_servo_csv(servo_csv, det.grid, servo_cmd, sun.ew_zero)
    save_session_json(session_json, make_session_record(user, light, sun, det.grid, servo_cmd))

    return AnalyzeResult(
        detection=det,
        user=user,
        light=light,
        sun=sun,
        orientation=orientation,
        servo_cmd=servo_cmd,
        orientation_txt=orientation_txt,
        servo_csv=servo_csv,
        session_json=session_json,
    )


def format_analyze_summary(result: AnalyzeResult) -> str:
    lines = [
        f"image={result.detection.image_path}",
        f"user={result.user.value}",
        f"light={result.light.value}",
        f"ns_angle={result.servo_cmd.ns_angle}, ew_zero={result.sun.ew_zero}",
        "",
        format_glass_orientation(result.orientation),
        "",
        f"grid_csv={result.detection.grid_csv}",
        f"grid_png={result.detection.grid_png}",
        f"orientation_txt={result.orientation_txt}",
    ]
    return "\n".join(lines)


def compute_from_grid_csv(
    grid_csv: Path,
    age: int,
    light: LightType,
    sun: SunAngles,
    young_mode: str | None = None,
    output_dir: Path | None = None,
    stem: str | None = None,
) -> ControlResult:
    output_dir = output_dir or OUTPUTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    user = resolve_user_category(age, young_mode)
    grid = load_grid_csv(grid_csv)
    servo_cmd = compute_servo_angles(grid, user, light, sun)

    base = stem or grid_csv.stem.replace("_grid_5x6", "")
    servo_csv = output_dir / f"{base}_servos.csv"
    session_json = output_dir / f"{base}_session.json"

    save_servo_csv(servo_csv, grid, servo_cmd, sun.ew_zero)
    save_session_json(session_json, make_session_record(user, light, sun, grid, servo_cmd))

    return ControlResult(
        user=user,
        light=light,
        sun=sun,
        grid=grid,
        servo_cmd=servo_cmd,
        servo_csv=servo_csv,
        session_json=session_json,
    )


def run_pipeline(
    *,
    age: int,
    light: LightType,
    sun: SunAngles,
    port: str | None = None,
    image_path: Path | None = None,
    capture: bool = False,
    camera_index: int | None = None,
    grid_csv: Path | None = None,
    young_mode: str | None = None,
    output_dir: Path | None = None,
    model_name: str = DEFAULT_MODEL,
    name: str | None = None,
    dry_run: bool = False,
) -> ControlResult:
    output_dir = output_dir or OUTPUTS_DIR

    if grid_csv is not None:
        grid = load_grid_csv(grid_csv)
        stem = name or grid_csv.stem.replace("_grid_5x6", "")
    else:
        if capture:
            image_path = capture_one(camera_index=camera_index)
        if image_path is None:
            raise ValueError("provide image_path, capture=True, or grid_csv")
        det = detect_from_image(image_path, output_dir=output_dir, model_name=model_name, name=name)
        grid = det.grid
        stem = name or image_path.stem

    user = resolve_user_category(age, young_mode)
    servo_cmd = compute_servo_angles(grid, user, light, sun)

    servo_csv = output_dir / f"{stem}_servos.csv"
    session_json = output_dir / f"{stem}_session.json"
    save_servo_csv(servo_csv, grid, servo_cmd, sun.ew_zero)
    save_session_json(session_json, make_session_record(user, light, sun, grid, servo_cmd))

    result = ControlResult(
        user=user,
        light=light,
        sun=sun,
        grid=grid,
        servo_cmd=servo_cmd,
        servo_csv=servo_csv,
        session_json=session_json,
    )

    if not dry_run:
        # 单口兼容：若只给 port，视为仅 mod1（旧用法）；完整双板请用 run_boards_from_grid
        if not port:
            raise ValueError("port required when dry_run is False")
        with MegaClient(port) as client:
            if not client.ping():
                raise RuntimeError("PING failed")
            client.send_set_mod1(servo_cmd.ns_angle, servo_cmd.small_angles[:15])

    return result


def format_servo_summary(result: ControlResult) -> str:
    lines = [
        f"user={result.user.value}",
        f"light={result.light.value}",
        f"ns_angle={result.servo_cmd.ns_angle}",
        f"servo_csv={result.servo_csv}",
    ]
    for i, angle in enumerate(result.servo_cmd.small_angles, start=1):
        part = result.grid[i - 1].body_part.value or "空"
        mode = "parallel" if angle != int(result.sun.ew_zero) else "perpendicular"
        lines.append(f"  servo {i:02d}: {angle:3d}° ({mode}, {part})")
    return "\n".join(lines)


def resolve_grid_preview_base(grid_csv: Path, grid: list[GridCell]) -> Image.Image:
    """优先用已有 *_grid_5x6.png；否则对照片画部位网格；再否则空白画布。"""
    stem = grid_csv.stem.replace("_grid_5x6", "")
    grid_png_candidates = [
        grid_csv.with_name(f"{stem}_grid_5x6.png"),
        OUTPUTS_DIR / f"{stem}_grid_5x6.png",
    ]
    for path in grid_png_candidates:
        if path.is_file():
            return Image.open(path).convert("RGB")

    for path in (
        PHOTOS_DIR / f"{stem}.jpg",
        PHOTOS_DIR / f"{stem}.jpeg",
        PHOTOS_DIR / f"{stem}.png",
    ):
        if path.is_file():
            return draw_grid_result(Image.open(path).convert("RGB"), grid)

    return draw_grid_result(blank_grid_canvas(), grid)


def render_block_highlight_preview(
    *,
    grid_csv: Path,
    age: int,
    light: LightType,
    young_mode: str | None = None,
    output_dir: Path | None = None,
    stem: str | None = None,
) -> tuple[Path, GlassOrientationResult]:
    """根据光线类型 + 网格识别结果，生成需遮挡玻璃板高亮图。"""
    output_dir = output_dir or OUTPUTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    user = resolve_user_category(age, young_mode)
    grid = load_grid_csv(grid_csv)
    orientation = classify_glass_orientation(grid, user, light)
    base = resolve_grid_preview_base(grid_csv, grid)
    highlighted = draw_block_highlight(base, grid, orientation.parallel_ids)

    base_stem = stem or grid_csv.stem.replace("_grid_5x6", "")
    out_path = output_dir / f"{base_stem}_block_{light.value}.png"
    highlighted.save(out_path)

    orient_txt = output_dir / f"{base_stem}_orientation.txt"
    orient_txt.write_text(format_glass_orientation(orientation) + "\n", encoding="utf-8")
    return out_path, orientation


def apply_big_servo_demo(
    mega_port: str | None,
    *,
    mega2_port: str | None = None,
    ns_abs: int = DEMO_BIG_SERVO_ABS_DEG,
    ew_zero: float = DEMO_EW_DEG,
    dry_run: bool = False,
) -> ServoCommand:
    """大舵机到位，两模块小舵机暂垂直。"""
    cmd = demo_big_servo_hold_command(ns_abs=ns_abs, ew_zero=ew_zero)
    if dry_run:
        return cmd
    if not mega_port or not mega2_port:
        raise ValueError("mega_port (mod1) and mega2_port (mod2) required when dry_run is False")
    dispatch_servo_command(cmd, mega_port, mega2_port, dry_run=False)
    return cmd


def run_boards_from_grid(
    *,
    grid_csv: Path,
    age: int,
    light: LightType,
    sun: SunAngles,
    mega_port: str | None = None,
    mega2_port: str | None = None,
    young_mode: str | None = None,
    output_dir: Path | None = None,
    ns_servo_abs: int = DEMO_BIG_SERVO_ABS_DEG,
    dry_run: bool = False,
    stem: str | None = None,
) -> ControlResult:
    """按网格 + 规则翻小舵机；双板下发 COM8(mod1)+COM10(mod2)。"""
    result = compute_from_grid_csv(
        grid_csv=grid_csv,
        age=age,
        light=light,
        sun=sun,
        young_mode=young_mode,
        output_dir=output_dir,
        stem=stem,
    )
    servo_cmd = with_ns_servo(result.servo_cmd, ns_servo_abs)
    save_servo_csv(result.servo_csv, result.grid, servo_cmd, sun.ew_zero)
    save_session_json(
        result.session_json,
        make_session_record(result.user, light, sun, result.grid, servo_cmd),
    )
    result = ControlResult(
        user=result.user,
        light=result.light,
        sun=result.sun,
        grid=result.grid,
        servo_cmd=servo_cmd,
        servo_csv=result.servo_csv,
        session_json=result.session_json,
    )
    if not dry_run:
        if not mega_port or not mega2_port:
            raise ValueError("mega_port and mega2_port required when dry_run is False")
        dispatch_servo_command(servo_cmd, mega_port, mega2_port, dry_run=False)
    return result
