from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mechanical_control.config import DEFAULT_MODEL, OUTPUTS_DIR
from mechanical_control.models import LightType, SunAngles
from mechanical_control.pipeline import (
    analyze_from_image,
    compute_from_grid_csv,
    detect_from_image,
    format_analyze_summary,
    format_servo_summary,
    run_pipeline,
)
from mechanical_control.serial_comm.mega_client import MegaClient
from mechanical_control.serial_comm.ports import list_serial_ports
from mechanical_control.models import ServoCommand


def _parse_light(value: str) -> LightType:
    try:
        return LightType(value.upper())
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"light must be one of UVB, UVA, VIS, NIR; got {value!r}"
        ) from e


def cmd_detect(args: argparse.Namespace) -> int:
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"[ERROR] image not found: {image_path}", file=sys.stderr)
        return 1

    result = detect_from_image(
        image_path,
        output_dir=Path(args.output_dir),
        model_name=args.model,
        name=args.name,
    )
    for cell in result.grid:
        part = cell.body_part.value if cell.body_part.value else "empty"
        print(f"grid {cell.grid_id:02d} -> {part}")

    print(f"[INFO] grid image -> {result.grid_png}")
    print(f"[INFO] grid csv   -> {result.grid_csv}")
    print(f"[INFO] mask       -> {result.mask_png}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"[ERROR] image not found: {image_path}", file=sys.stderr)
        print(f"[INFO] place a photo under {Path('data/photos')} and retry", file=sys.stderr)
        return 1

    try:
        result = analyze_from_image(
            image_path,
            age=args.age,
            light=_parse_light(args.light),
            sun=SunAngles(ns_angle=args.ns_angle, ew_zero=args.ew_zero),
            young_mode=args.young_mode,
            output_dir=Path(args.output_dir),
            model_name=args.model,
            name=args.name,
        )
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    print(format_analyze_summary(result))
    return 0


def cmd_compute(args: argparse.Namespace) -> int:
    grid_csv = Path(args.grid_csv)
    if not grid_csv.exists():
        print(f"[ERROR] grid csv not found: {grid_csv}", file=sys.stderr)
        return 1

    try:
        result = compute_from_grid_csv(
            grid_csv,
            age=args.age,
            light=_parse_light(args.light),
            sun=SunAngles(ns_angle=args.ns_angle, ew_zero=args.ew_zero),
            young_mode=args.young_mode,
            output_dir=Path(args.output_dir),
        )
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    print(format_servo_summary(result))
    print(f"[INFO] session -> {result.session_json}")
    return 0


def cmd_servo_test(args: argparse.Namespace) -> int:
    from mechanical_control.serial_comm.mega_client import dispatch_servo_command

    cmd = ServoCommand(ns_angle=args.ns_angle, small_angles=[args.small_angle] * 30)
    port2 = getattr(args, "port2", None)
    if port2:
        print(f"[INFO] dual dispatch {args.port} + {port2} ...")
        dispatch_servo_command(cmd, args.port, port2, dry_run=False)
    else:
        with MegaClient(args.port) as client:
            print("[INFO] ping mod1...")
            if not client.ping():
                print("[ERROR] PING failed", file=sys.stderr)
                return 1
            print("[INFO] sending SET mod1 (15 servos + ns)...")
            client.send_set_mod1(cmd.ns_angle, cmd.small_angles[:15])
    print("[INFO] OK")
    return 0


def cmd_list_ports(_args: argparse.Namespace) -> int:
    ports = list_serial_ports()
    if not ports:
        print("[INFO] no serial ports found")
        return 0
    for p in ports:
        print(p)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        result = run_pipeline(
            age=args.age,
            light=_parse_light(args.light),
            sun=SunAngles(ns_angle=args.ns_angle, ew_zero=args.ew_zero),
            port=args.port,
            image_path=Path(args.image) if args.image else None,
            capture=args.capture,
            camera_index=args.camera_index,
            grid_csv=Path(args.grid_csv) if args.grid_csv else None,
            young_mode=args.young_mode,
            output_dir=Path(args.output_dir),
            model_name=args.model,
            name=args.name,
            dry_run=args.dry_run,
        )
    except (ValueError, RuntimeError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    print(format_servo_summary(result))
    if args.dry_run:
        print("[INFO] dry-run: skip serial")
    else:
        print("[INFO] servos updated")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SmartSunroom CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_detect = sub.add_parser("detect", help="Body segmentation + 5x6 grid")
    p_detect.add_argument("--image", required=True)
    p_detect.add_argument("--output_dir", default=str(OUTPUTS_DIR))
    p_detect.add_argument("--model", default=DEFAULT_MODEL)
    p_detect.add_argument("--name", default=None)
    p_detect.set_defaults(func=cmd_detect)

    p_analyze = sub.add_parser(
        "analyze",
        help="Software-only: segment photo -> parallel/perpendicular panel IDs",
    )
    p_analyze.add_argument("--image", required=True, help="Photo path, e.g. data/photos/xxx.jpg")
    p_analyze.add_argument("--age", type=int, required=True)
    p_analyze.add_argument("--young-mode", choices=["tanning", "relaxation"], default=None)
    p_analyze.add_argument("--light", required=True)
    p_analyze.add_argument("--ns-angle", type=float, required=True)
    p_analyze.add_argument("--ew-zero", type=float, required=True)
    p_analyze.add_argument("--output_dir", default=str(OUTPUTS_DIR))
    p_analyze.add_argument("--model", default=DEFAULT_MODEL)
    p_analyze.add_argument("--name", default=None)
    p_analyze.set_defaults(func=cmd_analyze)

    p_compute = sub.add_parser("compute", help="Compute servo angles from an existing grid CSV")
    p_compute.add_argument("--grid-csv", required=True)
    p_compute.add_argument("--age", type=int, required=True)
    p_compute.add_argument("--young-mode", choices=["tanning", "relaxation"], default=None)
    p_compute.add_argument("--light", required=True)
    p_compute.add_argument("--ns-angle", type=float, required=True)
    p_compute.add_argument("--ew-zero", type=float, required=True)
    p_compute.add_argument("--output_dir", default=str(OUTPUTS_DIR))
    p_compute.set_defaults(func=cmd_compute)

    p_servo = sub.add_parser("servo-test", help="Serial test: dual or single board")
    p_servo.add_argument("--port", required=True, help="Module 1 COM port")
    p_servo.add_argument("--port2", default=None, help="Module 2 COM port; omit to test module 1 only")
    p_servo.add_argument("--ns-angle", type=int, default=90)
    p_servo.add_argument("--small-angle", type=int, default=90)
    p_servo.set_defaults(func=cmd_servo_test)

    p_ports = sub.add_parser("list-ports", help="List available serial ports")
    p_ports.set_defaults(func=cmd_list_ports)

    p_run = sub.add_parser("run", help="Full pipeline: segment -> angles -> dispatch")
    p_run.add_argument("--port", default=None)
    p_run.add_argument("--age", type=int, required=True)
    p_run.add_argument("--young-mode", choices=["tanning", "relaxation"], default=None)
    p_run.add_argument("--light", required=True)
    p_run.add_argument("--ns-angle", type=float, required=True)
    p_run.add_argument("--ew-zero", type=float, required=True)
    p_run.add_argument("--image", default=None)
    p_run.add_argument("--grid-csv", default=None, help="Skip segmentation; use existing CSV")
    p_run.add_argument("--capture", action="store_true")
    p_run.add_argument("--camera-index", type=int, default=None)
    p_run.add_argument("--output_dir", default=str(OUTPUTS_DIR))
    p_run.add_argument("--model", default=DEFAULT_MODEL)
    p_run.add_argument("--name", default=None)
    p_run.add_argument("--dry-run", action="store_true", help="Compute only; do not send serial")
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run" and not args.dry_run and not args.port:
        print("[ERROR] --port required unless --dry-run", file=sys.stderr)
        return 1
    if args.command == "run" and not args.capture and not args.image and not args.grid_csv:
        print("[ERROR] provide --image, --capture, or --grid-csv", file=sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
