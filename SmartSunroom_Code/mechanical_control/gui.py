"""SmartSunroom wizard: predict angles -> segment body -> select light & drive servos."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from PIL import Image, ImageTk

from mechanical_control.angle_inference.predict import AnglePredictResult, predict_sun_angles
from mechanical_control.config import (
    DEFAULT_ANGLE_PORT,
    DEFAULT_MEGA_PORT,
    DEFAULT_MEGA2_PORT,
    OUTPUTS_DIR,
    PHOTOS_DIR,
)
from mechanical_control.models import LightType, SunAngles
from mechanical_control.pipeline import (
    detect_from_image,
    format_servo_summary,
    render_block_highlight_preview,
    run_boards_from_grid,
)
from mechanical_control.serial_comm.ports import list_serial_ports

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
        self._sun: SunAngles | None = None
        self._grid_ready = False
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._preview_win: tk.Toplevel | None = None

        self._build_ui()
        self._refresh_ports()
        self._goto_step(0)
        # Do not auto-start prediction; wait for user to select port and confirm/start

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

        self.dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            root,
            text="Compute only (do not send servo commands)",
            variable=self.dry_run_var,
        ).grid(row=5, column=0, columnspan=3, sticky=tk.W, **pad)

        self.resegment_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            root,
            text="Re-run segmentation model in step 2 (otherwise use selected grid CSV)",
            variable=self.resegment_var,
        ).grid(row=6, column=0, columnspan=3, sticky=tk.W, **pad)

        pred_frm = ttk.LabelFrame(root, text="1 · Predicted solar angles")
        pred_frm.grid(row=7, column=0, columnspan=3, sticky=tk.EW, **pad)
        self.pred_ns_var = tk.StringVar(value="—")
        self.pred_ew_var = tk.StringVar(value="—")
        self.pred_note_var = tk.StringVar(value="Select angle port, then start step 1")
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
        layer_frm.grid(row=8, column=0, columnspan=3, sticky=tk.EW, **pad)
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
        self.age_var = tk.StringVar(value="")
        self.age_entry = ttk.Entry(layer_frm, textvariable=self.age_var, width=8, state="disabled")
        self.age_entry.grid(row=0, column=3, sticky=tk.W, padx=8)
        ttk.Label(layer_frm, text="Young-adult mode").grid(
            row=1, column=0, sticky=tk.W, padx=8, pady=4
        )
        self.young_var = tk.StringVar(value="")
        self.young_combo = ttk.Combobox(
            layer_frm,
            textvariable=self.young_var,
            values=["tanning", "relaxation"],
            width=12,
            state="disabled",
        )
        self.young_combo.grid(row=1, column=1, sticky=tk.W, padx=8, pady=4)

        grid_frm = ttk.LabelFrame(root, text="2 · Segmentation result")
        grid_frm.grid(row=9, column=0, columnspan=3, sticky=tk.EW, **pad)
        self.grid_var = tk.StringVar(value="")
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
        ttk.Button(grid_frm, text="Browse photo…", command=self._browse_photo).grid(
            row=1, column=2, padx=4
        )
        self.photo_var = tk.StringVar(value=str(DEFAULT_PHOTO) if DEFAULT_PHOTO.is_file() else "")
        grid_frm.columnconfigure(0, weight=1)

        btn_frm = ttk.Frame(root)
        btn_frm.grid(row=10, column=0, columnspan=3, sticky=tk.W, **pad)
        self.btn_confirm = ttk.Button(btn_frm, text="Start step 1", command=self._on_confirm)
        self.btn_confirm.pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frm, text="Retry step", command=self._on_redo_step).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(btn_frm, text="Reset", command=self._on_reset).pack(side=tk.LEFT, padx=4)

        self.log = scrolledtext.ScrolledText(root, height=12, state=tk.DISABLED)
        self.log.grid(row=11, column=0, columnspan=3, sticky=tk.NSEW, **pad)
        root.rowconfigure(11, weight=1)
        root.columnconfigure(1, weight=1)

        self._goto_step(0, awaiting_confirm=True)
        self.hint_var.set("Select the angle sensor port, then click Start step 1.")
        self.btn_confirm.configure(text="Start step 1", state=tk.NORMAL)

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
        if DEFAULT_ANGLE_PORT and DEFAULT_ANGLE_PORT in ports:
            self.angle_port_var.set(DEFAULT_ANGLE_PORT)
        elif ports and not self.angle_port_var.get():
            self.angle_port_var.set(ports[0])
        if DEFAULT_MEGA_PORT and DEFAULT_MEGA_PORT in ports:
            self.mega_port_var.set(DEFAULT_MEGA_PORT)
        if DEFAULT_MEGA2_PORT and DEFAULT_MEGA2_PORT in ports:
            self.mega2_port_var.set(DEFAULT_MEGA2_PORT)

    def _browse_grid(self) -> None:
        path = filedialog.askopenfilename(
            title="Select grid CSV",
            initialdir=str(OUTPUTS_DIR),
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
        )
        if path:
            self.grid_var.set(path)

    def _browse_photo(self) -> None:
        path = filedialog.askopenfilename(
            title="Select photo for segmentation",
            initialdir=str(PHOTOS_DIR),
            filetypes=[("Images", "*.jpg;*.jpeg;*.png"), ("All", "*.*")],
        )
        if path:
            self.photo_var.set(path)
            self.resegment_var.set(True)
            self._log(f"[INFO] Photo selected: {path}")

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
                self.hint_var.set("Ready for solar-angle prediction.")
                self.btn_confirm.configure(text="Start step 1", state=tk.NORMAL)
            elif self._step == 1:
                self.hint_var.set("Segmentation ready. Confirm to choose the light band.")
                self.btn_confirm.configure(text="Confirm → Light band", state=tk.NORMAL)
            else:
                self.hint_var.set("Enter age / mode, choose light band, then confirm.")
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
        port = self.angle_port_var.get().strip()
        if not port:
            messagebox.showwarning("Missing port", "Select the angle sensor COM port.")
            self._goto_step(0, awaiting_confirm=True)
            return

        self._goto_step(0, awaiting_confirm=False)

        def task() -> None:
            self.after(0, lambda: self._log("======== Step 1: Solar angles ========"))
            result = predict_sun_angles(
                port,
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
                self.hint_var.set("Solar angles ready. Confirm to start body-part segmentation.")
                self.btn_confirm.configure(text="Confirm → Segmentation", state=tk.NORMAL)

            self.after(0, ui)

        self._run_async(task)

    def _start_step2_segment(self) -> None:
        self._goto_step(1, awaiting_confirm=False)
        resegment = self.resegment_var.get()
        photo = Path(self.photo_var.get().strip()) if self.photo_var.get().strip() else DEFAULT_PHOTO

        def task() -> None:
            self.after(0, lambda: self._log("======== Step 2: Segmentation ========"))
            if resegment:
                if not photo.is_file():
                    raise FileNotFoundError(f"Photo not found: {photo}")
                self.after(0, lambda: self._log(f"[INFO] Running model on {photo.name}"))
                det = detect_from_image(photo, output_dir=OUTPUTS_DIR, name=photo.stem)
                grid_csv = det.grid_csv
                grid_png = det.grid_png
                note = f"Segmentation complete → {grid_csv.name}"
            else:
                grid_csv = Path(self.grid_var.get().strip())
                if not grid_csv.is_file():
                    raise FileNotFoundError(
                        "Grid CSV not found. Browse a CSV or enable re-run segmentation."
                    )
                stem = grid_csv.stem.replace("_grid_5x6", "")
                grid_png = grid_csv.with_name(f"{stem}_grid_5x6.png")
                if not grid_png.is_file():
                    alt = OUTPUTS_DIR / f"{stem}_grid_5x6.png"
                    grid_png = alt if alt.is_file() else grid_png
                note = f"Using grid CSV → {grid_csv.name}"

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
            young = self.young_var.get().strip() or None
            if 15 <= age <= 44 and not young:
                raise ValueError("young-adult mode required for age 15-44")
        except (ValueError, KeyError) as e:
            messagebox.showerror("Invalid input", str(e))
            self._goto_step(2, awaiting_confirm=True)
            return

        grid_path = Path(self.grid_var.get().strip())
        if not grid_path.is_file():
            messagebox.showerror("Missing grid", f"Not found: {grid_path}")
            self._goto_step(2, awaiting_confirm=True)
            return

        if self._sun is None:
            messagebox.showerror("Missing angles", "Complete step 1 first.")
            return

        dry = self.dry_run_var.get()
        mega = self.mega_port_var.get().strip() or None
        mega2 = self.mega2_port_var.get().strip() or None
        if not dry and (not mega or not mega2):
            messagebox.showwarning(
                "Missing ports",
                "Select servo board 1 and board 2, or enable compute-only mode.",
            )
            self._goto_step(2, awaiting_confirm=True)
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

        if self._step == 0 and self._sun is None:
            self._start_step1_predict()
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
            self._log("[INFO] Enter age, select light band, then confirm.")
        elif self._step == 2:
            self._log(f"[Confirm] Light band={self.light_var.get()} — driving servos")
            self._start_step3_servos()

    def _on_redo_step(self) -> None:
        if self._busy:
            return
        if self._step == 0:
            self._sun = None
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
        self._sun = None
        self.pred_ns_var.set("—")
        self.pred_ew_var.set("—")
        self.pred_note_var.set("Select angle port, then start step 1")
        self.seg_status_var.set("Not ready")
        self.grid_var.set("")
        self.age_var.set("")
        self.young_var.set("")
        self._log("[INFO] Reset — starting from step 1")
        self._goto_step(0, awaiting_confirm=True)
        self.hint_var.set("Select the angle sensor port, then click Start step 1.")
        self.btn_confirm.configure(text="Start step 1", state=tk.NORMAL)


def main() -> None:
    app = SmartSunroomApp()
    app.mainloop()


if __name__ == "__main__":
    main()
