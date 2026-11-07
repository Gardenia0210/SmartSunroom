"""SmartSunroom wizard: predict angles → segment body → select light & drive servos."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from PIL import Image, ImageTk

from src.angle_predict import AnglePredictResult, predict_sun_angles
from src.config import (
    DEFAULT_ANGLE_PORT,
    DEFAULT_DEMO_AGE,
    DEFAULT_DEMO_YOUNG_MODE,
    DEFAULT_MEGA_PORT,
    DEFAULT_MEGA2_PORT,
    DEFAULT_POS1_GRID_CSV,
    DEFAULT_POS1_GRID_PNG,
    DEMO_BIG_SERVO_ABS_DEG,
    DEMO_EW_DEG,
    DEMO_FORCE_ANGLES,
    DEMO_NS_DEG,
    OUTPUTS_DIR,
    PHOTOS_DIR,
)
from src.models import LightType, SunAngles
from src.pipeline import (
    detect_from_image,
    format_servo_summary,
    render_block_highlight_preview,
    run_boards_from_grid,
)
from src.serial.ports import list_serial_ports

STEPS = (
    "1 · Solar angles — Confirm to continue",
    "2 · Body-part segmentation — Confirm to continue",
    "3 · Select light band & drive servos — Confirm to run",
)

DEFAULT_PHOTO = PHOTOS_DIR / "pos1.jpg"


class SmartSunroomApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SmartSunroom")
        self.geometry("760x700")
        self.resizable(True, True)

        self._busy = False
        self._step = 0
        self._phase_done = False
        self._predict: AnglePredictResult | None = None
        self._sun = SunAngles(ns_angle=DEMO_NS_DEG, ew_zero=DEMO_EW_DEG)
        self._grid_ready = False
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._preview_win: tk.Toplevel | None = None

        self._build_ui()
        self._refresh_ports()
        self._goto_step(0)
        self.after(400, self._start_step1_predict)

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}
        root = ttk.Frame(self)
        root.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        self.step_var = tk.StringVar()
        ttk.Label(root, textvariable=self.step_var, font=("", 12, "bold")).grid(
            row=0, column=0, columnspan=3, sticky=tk.W, **pad
        )
        self.hint_var = tk.StringVar(value="")
        ttk.Label(root, textvariable=self.hint_var, foreground="#0a5").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, **pad
        )

        ttk.Label(root, text="Angle sensor port").grid(row=2, column=0, sticky=tk.W, **pad)
        self.angle_port_var = tk.StringVar(value=DEFAULT_ANGLE_PORT)
        self.angle_port_combo = ttk.Combobox(root, textvariable=self.angle_port_var, width=14)
        self.angle_port_combo.grid(row=2, column=1, sticky=tk.W, **pad)

        ttk.Label(root, text="Servo board 1 (panels 1–15 + NS)").grid(
            row=3, column=0, sticky=tk.W, **pad
        )
        self.mega_port_var = tk.StringVar(value=DEFAULT_MEGA_PORT)
        self.mega_port_combo = ttk.Combobox(root, textvariable=self.mega_port_var, width=14)
        self.mega_port_combo.grid(row=3, column=1, sticky=tk.W, **pad)
        ttk.Button(root, text="Refresh ports", command=self._refresh_ports).grid(
            row=3, column=2, sticky=tk.W, **pad
        )

        ttk.Label(root, text="Servo board 2 (panels 16–30)").grid(
            row=4, column=0, sticky=tk.W, **pad
        )
        self.mega2_port_var = tk.StringVar(value=DEFAULT_MEGA2_PORT)
        self.mega2_port_combo = ttk.Combobox(root, textvariable=self.mega2_port_var, width=14)
        self.mega2_port_combo.grid(row=4, column=1, sticky=tk.W, **pad)

        self.sample_hw_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            root,
            text="Read angle sensor before estimating solar angles",
            variable=self.sample_hw_var,
        ).grid(row=5, column=0, columnspan=3, sticky=tk.W, **pad)

        self.dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            root,
            text="Compute only (do not send servo commands)",
            variable=self.dry_run_var,
        ).grid(row=6, column=0, columnspan=3, sticky=tk.W, **pad)

        self.resegment_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            root,
            text="Re-run segmentation model in step 2 (otherwise use saved result)",
            variable=self.resegment_var,
        ).grid(row=7, column=0, columnspan=3, sticky=tk.W, **pad)

        pred_frm = ttk.LabelFrame(root, text="1 · Estimated solar angles")
        pred_frm.grid(row=8, column=0, columnspan=3, sticky=tk.EW, **pad)
        self.pred_ns_var = tk.StringVar(value="—")
        self.pred_ew_var = tk.StringVar(value="—")
        self.pred_note_var = tk.StringVar(value="Starting…")
        ttk.Label(pred_frm, text="N–S").grid(row=0, column=0, sticky=tk.W, padx=8, pady=6)
        ttk.Label(pred_frm, textvariable=self.pred_ns_var, font=("", 20, "bold")).grid(
            row=0, column=1, sticky=tk.W, padx=8
        )
        ttk.Label(pred_frm, text="E–W").grid(row=0, column=2, sticky=tk.W, padx=8)
        ttk.Label(pred_frm, textvariable=self.pred_ew_var, font=("", 20, "bold")).grid(
            row=0, column=3, sticky=tk.W, padx=8
        )
        ttk.Label(pred_frm, textvariable=self.pred_note_var, wraplength=680).grid(
            row=1, column=0, columnspan=4, sticky=tk.W, padx=8, pady=(0, 8)
        )

        layer_frm = ttk.LabelFrame(root, text="3 · Light band & user profile")
        layer_frm.grid(row=9, column=0, columnspan=3, sticky=tk.EW, **pad)
        ttk.Label(layer_frm, text="Light band").grid(row=0, column=0, sticky=tk.W, padx=8, pady=4)
        self.light_var = tk.StringVar(value="UVB")
        self.light_combo = ttk.Combobox(
            layer_frm,
            textvariable=self.light_var,
            values=["UVB", "UVA", "VIS", "NIR"],
            width=12,
            state="disabled",
        )
        self.light_combo.grid(row=0, column=1, sticky=tk.W, padx=8, pady=4)
        ttk.Label(layer_frm, text="Age").grid(row=0, column=2, sticky=tk.W, padx=8)
        self.age_var = tk.StringVar(value=str(DEFAULT_DEMO_AGE))
        self.age_entry = ttk.Entry(layer_frm, textvariable=self.age_var, width=8, state="disabled")
        self.age_entry.grid(row=0, column=3, sticky=tk.W, padx=8)
        ttk.Label(layer_frm, text="Young-adult mode").grid(
            row=1, column=0, sticky=tk.W, padx=8, pady=4
        )
        self.young_var = tk.StringVar(value=DEFAULT_DEMO_YOUNG_MODE)
        self.young_combo = ttk.Combobox(
            layer_frm,
            textvariable=self.young_var,
            values=["tanning", "relaxation"],
            width=12,
            state="disabled",
        )
        self.young_combo.grid(row=1, column=1, sticky=tk.W, padx=8, pady=4)

        grid_frm = ttk.LabelFrame(root, text="2 · Segmentation result")
        grid_frm.grid(row=10, column=0, columnspan=3, sticky=tk.EW, **pad)
        self.grid_var = tk.StringVar(value=str(DEFAULT_POS1_GRID_CSV))
        self.seg_status_var = tk.StringVar(value="Not ready")
        ttk.Label(grid_frm, textvariable=self.seg_status_var).grid(
            row=0, column=0, columnspan=3, sticky=tk.W, padx=8, pady=4
        )
        ttk.Entry(grid_frm, textvariable=self.grid_var, width=64).grid(
            row=1, column=0, sticky=tk.EW, padx=8, pady=4
        )
        ttk.Button(grid_frm, text="Browse…", command=self._browse_grid).grid(
            row=1, column=1, padx=4
        )
        ttk.Button(grid_frm, text="Default", command=self._use_pos1).grid(row=1, column=2, padx=4)
        grid_frm.columnconfigure(0, weight=1)

        btn_frm = ttk.Frame(root)
        btn_frm.grid(row=11, column=0, columnspan=3, sticky=tk.W, **pad)
        self.btn_confirm = ttk.Button(btn_frm, text="Confirm", command=self._on_confirm)
        self.btn_confirm.pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frm, text="Retry step", command=self._on_redo_step).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(btn_frm, text="Reset", command=self._on_reset).pack(side=tk.LEFT, padx=4)

        self.log = scrolledtext.ScrolledText(root, height=12, state=tk.DISABLED)
        self.log.grid(row=12, column=0, columnspan=3, sticky=tk.NSEW, **pad)
        root.rowconfigure(12, weight=1)
        root.columnconfigure(1, weight=1)

    def _log(self, msg: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _refresh_ports(self) -> None:
        ports = list_serial_ports()
        self.angle_port_combo["values"] = ports
        self.mega_port_combo["values"] = ports
        self.mega2_port_combo["values"] = ports
        if DEFAULT_ANGLE_PORT in ports:
            self.angle_port_var.set(DEFAULT_ANGLE_PORT)
        elif ports and self.angle_port_var.get() not in ports:
            self.angle_port_var.set(ports[0])
        if DEFAULT_MEGA_PORT in ports:
            self.mega_port_var.set(DEFAULT_MEGA_PORT)
        elif ports and (
            not self.mega_port_var.get() or self.mega_port_var.get() not in ports
        ):
            picked = next(
                (p for p in ports if p.upper() != self.angle_port_var.get().upper()),
                ports[0],
            )
            self.mega_port_var.set(picked)
        if DEFAULT_MEGA2_PORT in ports:
            self.mega2_port_var.set(DEFAULT_MEGA2_PORT)
        elif ports and (
            not self.mega2_port_var.get() or self.mega2_port_var.get() not in ports
        ):
            used = {
                self.angle_port_var.get().upper(),
                self.mega_port_var.get().upper(),
            }
            picked2 = next((p for p in ports if p.upper() not in used), ports[0])
            self.mega2_port_var.set(picked2)

    def _browse_grid(self) -> None:
        path = filedialog.askopenfilename(
            title="Select grid CSV",
            initialdir=str(OUTPUTS_DIR),
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
        )
        if path:
            self.grid_var.set(path)

    def _use_pos1(self) -> None:
        self.grid_var.set(str(DEFAULT_POS1_GRID_CSV))

    def _set_layer_enabled(self, enabled: bool) -> None:
        state = "readonly" if enabled else "disabled"
        entry_state = "normal" if enabled else "disabled"
        self.light_combo.configure(state=state)
        self.young_combo.configure(state=state)
        self.age_entry.configure(state=entry_state)

    def _goto_step(self, step: int, *, awaiting_confirm: bool = False) -> None:
        self._step = max(0, min(step, len(STEPS) - 1))
        self._phase_done = awaiting_confirm
        self.step_var.set(f"Current: {STEPS[self._step]}")
        self._set_layer_enabled(self._step == 2 and awaiting_confirm)
        if awaiting_confirm:
            if self._step == 0:
                self.hint_var.set("Solar angles ready. Confirm to start body-part segmentation.")
                self.btn_confirm.configure(text="Confirm → Segmentation", state=tk.NORMAL)
            elif self._step == 1:
                self.hint_var.set("Segmentation ready. Confirm to choose the light band.")
                self.btn_confirm.configure(text="Confirm → Light band", state=tk.NORMAL)
            else:
                self.hint_var.set("Choose light band, then confirm to shade panels and move servos.")
                self.btn_confirm.configure(text="Confirm → Drive servos", state=tk.NORMAL)
        else:
            self.hint_var.set("Working… please wait.")
            self.btn_confirm.configure(state=tk.DISABLED)

    def _run_async(self, fn) -> None:
        if self._busy:
            messagebox.showwarning("Busy", "Please wait for the current task to finish.")
            return
        self._busy = True

        def worker() -> None:
            try:
                fn()
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.after(0, lambda: self._log(f"[ERROR] {e}"))
                self.after(0, lambda: self.btn_confirm.configure(state=tk.NORMAL))
            finally:
                self.after(0, lambda: setattr(self, "_busy", False))

        threading.Thread(target=worker, daemon=True).start()

    def _show_image_window(self, image_path: Path, title: str, caption: str) -> None:
        if not image_path.is_file():
            self._log(f"[WARN] Preview image missing: {image_path}")
            return
        img = Image.open(image_path).convert("RGB")
        max_w, max_h = 560, 720
        w, h = img.size
        scale = min(max_w / w, max_h / h, 1.0)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        if self._preview_win is not None and self._preview_win.winfo_exists():
            self._preview_win.destroy()

        win = tk.Toplevel(self)
        win.title(title)
        self._preview_win = win
        self._preview_photo = ImageTk.PhotoImage(img)
        ttk.Label(win, image=self._preview_photo).pack(padx=8, pady=8)
        ttk.Label(win, text=caption).pack(pady=(0, 8))

    def _start_step1_predict(self) -> None:
        self._goto_step(0, awaiting_confirm=False)
        port = self.angle_port_var.get().strip() or None
        sample_hw = self.sample_hw_var.get()

        def task() -> None:
            self.after(0, lambda: self._log("======== Step 1: Solar angles ========"))
            result = predict_sun_angles(
                port,
                force_demo=DEMO_FORCE_ANGLES,
                sample_hardware=sample_hw,
                log=lambda m: self.after(0, lambda msg=m: self._log(msg)),
            )
            self._predict = result
            self._sun = result.sun

            def ui() -> None:
                self.pred_ns_var.set(f"{result.sun.ns_angle:.0f}°")
                self.pred_ew_var.set(f"{result.sun.ew_zero:.0f}°")
                self.pred_note_var.set(result.note)
                self._log(
                    f"[OK] N–S {result.sun.ns_angle:.0f}° / E–W {result.sun.ew_zero:.0f}°"
                )
                self._goto_step(0, awaiting_confirm=True)

            self.after(0, ui)

        self._run_async(task)

    def _start_step2_segment(self) -> None:
        self._goto_step(1, awaiting_confirm=False)
        resegment = self.resegment_var.get()

        def task() -> None:
            self.after(0, lambda: self._log("======== Step 2: Segmentation ========"))
            if resegment and DEFAULT_PHOTO.is_file():
                self.after(0, lambda: self._log(f"[INFO] Running model on {DEFAULT_PHOTO.name}"))
                det = detect_from_image(DEFAULT_PHOTO, output_dir=OUTPUTS_DIR, name="pos1")
                grid_csv = det.grid_csv
                grid_png = det.grid_png
                note = f"Segmentation complete → {grid_csv.name}"
            else:
                grid_csv = Path(self.grid_var.get().strip() or str(DEFAULT_POS1_GRID_CSV))
                if not grid_csv.is_file():
                    grid_csv = DEFAULT_POS1_GRID_CSV
                if not grid_csv.is_file():
                    raise FileNotFoundError(f"Grid CSV not found: {grid_csv}")
                grid_png = DEFAULT_POS1_GRID_PNG
                if not grid_png.is_file():
                    stem = grid_csv.stem.replace("_grid_5x6", "")
                    alt = OUTPUTS_DIR / f"{stem}_grid_5x6.png"
                    grid_png = alt if alt.is_file() else grid_png
                note = f"Segmentation ready → {grid_csv.name}"

            self._grid_ready = True

            def ui() -> None:
                self.grid_var.set(str(grid_csv))
                self.seg_status_var.set(note)
                self._log(f"[OK] {note}")
                if grid_png.is_file():
                    self._log(f"[OK] Preview → {grid_png.name}")
                    self._show_image_window(
                        grid_png,
                        "Body-part grid (5×6)",
                        "Review the segmentation, then confirm to continue.",
                    )
                self._goto_step(1, awaiting_confirm=True)

            self.after(0, ui)

        self._run_async(task)

    def _start_step3_servos(self) -> None:
        try:
            age = int(self.age_var.get())
            light = LightType(self.light_var.get())
            young = self.young_var.get() if 15 <= age <= 44 else None
        except (ValueError, KeyError) as e:
            messagebox.showerror("Invalid input", str(e))
            return

        grid_path = Path(self.grid_var.get().strip())
        if not grid_path.is_file():
            messagebox.showerror("Missing grid", f"Not found: {grid_path}")
            return

        dry = self.dry_run_var.get()
        mega = self.mega_port_var.get().strip() or None
        mega2 = self.mega2_port_var.get().strip() or None
        if not dry and (not mega or not mega2):
            messagebox.showwarning(
                "Missing ports",
                "Select servo board 1 and board 2, or enable compute-only mode.",
            )
            return

        self._goto_step(2, awaiting_confirm=False)
        sun = self._sun

        def task() -> None:
            self.after(
                0,
                lambda: self._log(f"======== Step 3: {light.value} shading ========"),
            )
            out_path, orientation = render_block_highlight_preview(
                grid_csv=grid_path,
                age=age,
                light=light,
                young_mode=young,
                output_dir=OUTPUTS_DIR,
            )
            ids = (
                ", ".join(str(i) for i in orientation.parallel_ids)
                if orientation.parallel_ids
                else "(none)"
            )
            self.after(0, lambda: self._log(f"[OK] Panels to shade: {ids}"))
            self.after(0, lambda: self._log(f"[OK] Highlight map → {out_path.name}"))
            self.after(
                0,
                lambda: self._show_image_window(
                    out_path,
                    f"Shading plan — {light.value}",
                    "Highlighted panels will shade; sending servo commands…",
                ),
            )

            self.after(
                0,
                lambda: self._log(
                    f"[INFO] Driving board1={mega}, board2={mega2} for {light.value}"
                ),
            )
            result = run_boards_from_grid(
                grid_csv=grid_path,
                age=age,
                light=light,
                sun=sun,
                mega_port=mega,
                mega2_port=mega2,
                young_mode=young,
                output_dir=OUTPUTS_DIR,
                ns_servo_abs=DEMO_BIG_SERVO_ABS_DEG,
                dry_run=dry,
            )
            summary = format_servo_summary(result)
            for line in summary.splitlines():
                self.after(0, lambda ln=line: self._log(ln))

            def done() -> None:
                mode = "compute-only" if dry else f"sent to {mega} + {mega2}"
                self._log(f"[OK] Step 3 complete ({mode})")
                self.hint_var.set("Done. Use Reset to run again.")
                self.btn_confirm.configure(text="Done", state=tk.DISABLED)
                self._phase_done = False
                messagebox.showinfo(
                    "Complete",
                    f"Servo control finished ({mode}).\nPanels to shade: {ids}",
                )

            self.after(0, done)

        self._run_async(task)

    def _on_confirm(self) -> None:
        if self._busy:
            messagebox.showwarning("Busy", "Please wait for the current task to finish.")
            return
        if not self._phase_done:
            messagebox.showinfo("Please wait", "This step is not ready yet.")
            return

        if self._step == 0:
            self._log("[Confirm] Proceeding to segmentation")
            self._start_step2_segment()
        elif self._step == 1:
            self._log("[Confirm] Proceeding to light-band selection")
            self._goto_step(2, awaiting_confirm=True)
            self._log("[INFO] Select UVA / UVB / VIS / NIR, then confirm.")
        elif self._step == 2:
            self._log(f"[Confirm] Light band={self.light_var.get()} — driving servos")
            self._start_step3_servos()

    def _on_redo_step(self) -> None:
        if self._busy:
            return
        if self._step == 0:
            self._start_step1_predict()
        elif self._step == 1:
            self._start_step2_segment()
        else:
            self._goto_step(2, awaiting_confirm=True)

    def _on_reset(self) -> None:
        if self._busy:
            messagebox.showwarning("Busy", "Please wait for the current task to finish.")
            return
        self._predict = None
        self._grid_ready = False
        self._sun = SunAngles(ns_angle=DEMO_NS_DEG, ew_zero=DEMO_EW_DEG)
        self.pred_ns_var.set("—")
        self.pred_ew_var.set("—")
        self.pred_note_var.set("Restarting…")
        self.seg_status_var.set("Not ready")
        self._use_pos1()
        self._log("[INFO] Reset — starting from step 1")
        self._start_step1_predict()


def main() -> None:
    app = SmartSunroomApp()
    app.mainloop()


if __name__ == "__main__":
    main()
