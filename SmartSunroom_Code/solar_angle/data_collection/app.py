"""
Photoresistor solar-angle collection: read Mega over serial, one sample every 0.5s, save 100 rows to CSV.
"""
import csv
import os
import re
import threading
import time
from datetime import datetime
import tkinter as tk
from typing import List, Optional
from tkinter import messagebox, simpledialog, ttk

import serial
import serial.tools.list_ports

import config
from serial_reader import open_serial, read_channels


def create_session_output_dir() -> str:
    """Create a session subfolder under data/ (timestamped to avoid name clashes)."""
    root_dir = os.path.dirname(os.path.abspath(__file__))
    base = os.path.join(root_dir, config.OUTPUT_DIR)
    os.makedirs(base, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    session = os.path.join(base, f"session_{stamp}")
    os.makedirs(session, exist_ok=True)
    return session


def sanitize_filename(ns: float, ew: float) -> str:
    def one(x: float) -> str:
        s = f"{x:.2f}".replace(".", "p")
        return re.sub(r"[^\w\-]+", "_", s)

    return f"collect_ns{one(ns)}_ew{one(ew)}.csv"


def values_to_matrix_row(raw8: List[int]) -> List[int]:
    """Emit 8 columns in config direction order: East1 East2 South1 South2 ..."""
    row: List[int] = []
    for direction in config.ROWS_ORDER:
        a, b = config.PIN_GROUPS[direction]
        row.append(raw8[a])
        row.append(raw8[b])
    return row


class CollectorApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Photoresistor angle collection")
        self.root.geometry("520x280")

        self.ser: Optional[serial.Serial] = None
        self.collecting = False
        self.cancel_requested = False

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        row1 = ttk.Frame(main)
        row1.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(row1, text="Port:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(row1, textvariable=self.port_var, width=28, state="readonly")
        self.port_combo.pack(side=tk.LEFT, padx=(6, 12))
        ttk.Button(row1, text="Refresh ports", command=self.refresh_ports).pack(side=tk.LEFT)

        row2 = ttk.Frame(main)
        row2.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            row2,
            text="Click Start, enter N-S and E-W angles (deg), then collect 100 samples into this session folder under data/.",
        ).pack(anchor=tk.W)

        row3 = ttk.Frame(main)
        row3.pack(fill=tk.X, pady=(0, 12))
        self.btn_start = ttk.Button(row3, text="Start", command=self.on_start)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_pause = ttk.Button(row3, text="Pause", command=self.on_pause, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(main, maximum=config.SAMPLES_PER_SESSION)
        self.progress.pack(fill=tk.X, pady=(0, 8))

        self.log = tk.Text(main, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True)

        self.refresh_ports()

        self.session_out_dir = create_session_output_dir()
        self.log_line("Session folder: " + self.session_out_dir)

    def refresh_ports(self) -> None:
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def log_line(self, msg: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def ensure_serial(self) -> Optional[serial.Serial]:
        port = self.port_var.get().strip()
        if not port:
            messagebox.showerror("Error", "Select a serial port")
            return None
        try:
            return open_serial(port, config.SERIAL_BAUD)
        except Exception as e:
            messagebox.showerror("Serial error", str(e))
            return None

    def on_start(self) -> None:
        if self.collecting:
            messagebox.showinfo("Notice", "Collection in progress; pause first or wait until finished.")
            return

        ns_s = simpledialog.askstring("N-S angle", "Enter N-S angle in degrees (may be negative):", parent=self.root)
        if ns_s is None:
            return
        ew_s = simpledialog.askstring("E-W angle", "Enter E-W angle in degrees (may be negative):", parent=self.root)
        if ew_s is None:
            return
        try:
            ns = float(ns_s.strip())
            ew = float(ew_s.strip())
        except ValueError:
            messagebox.showerror("Error", "Angles must be numbers")
            return

        ser = self.ensure_serial()
        if ser is None:
            return

        self.ser = ser
        self.cancel_requested = False
        self.collecting = True
        self.btn_start.configure(state=tk.DISABLED)
        self.btn_pause.configure(state=tk.NORMAL)
        self.progress["value"] = 0

        self.log_line(f"Start collect: N-S={ns:g} deg, E-W={ew:g} deg, target {config.SAMPLES_PER_SESSION} samples")

        def worker() -> None:
            try:
                fname = sanitize_filename(ns, ew)
                path = os.path.join(self.session_out_dir, fname)
                headers = ["sample_index", "ns_deg", "ew_deg"]
                for direction in config.ROWS_ORDER:
                    headers.append(f"{direction}_1")
                    headers.append(f"{direction}_2")

                rows_written = 0
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(headers)
                    for i in range(config.SAMPLES_PER_SESSION):
                        if self.cancel_requested:
                            self.root.after(0, lambda: self.log_line("Paused; incomplete file discarded (current round did not reach 100 samples)."))
                            try:
                                os.remove(path)
                            except OSError:
                                pass
                            return

                        assert self.ser is not None
                        raw = read_channels(self.ser)
                        matrix_vals = values_to_matrix_row(raw)
                        w.writerow([i + 1, ns, ew] + matrix_vals)
                        rows_written += 1

                        def upd_prog(v: int) -> None:
                            self.progress["value"] = v

                        self.root.after(0, upd_prog, rows_written)
                        time.sleep(config.SAMPLE_INTERVAL_SEC)

                self.root.after(0, lambda: self.log_line(f"Done: saved {rows_written} rows -> {path}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Collection failed", str(e)))
                self.root.after(0, lambda: self.log_line(f"Error: {e}"))
            finally:
                self.collecting = False
                self.root.after(0, self._collection_finished)

        threading.Thread(target=worker, daemon=True).start()

    def _collection_finished(self) -> None:
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_pause.configure(state=tk.DISABLED)
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def on_pause(self) -> None:
        if self.collecting:
            self.cancel_requested = True
            self.log_line("Pause requested...")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    CollectorApp().run()


if __name__ == "__main__":
    main()
