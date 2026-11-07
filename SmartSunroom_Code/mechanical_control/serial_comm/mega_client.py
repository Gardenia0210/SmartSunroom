from __future__ import annotations

import time

import serial

from mechanical_control.config import (
    SERIAL_BAUD,
    SERIAL_OPEN_DELAY_SEC,
    SERIAL_READ_RETRIES,
    SERIAL_READ_TIMEOUT_SEC,
)
from mechanical_control.models import ServoCommand


class MegaClient:
    def __init__(self, port: str, baud: int = SERIAL_BAUD) -> None:
        self.port = port
        self.baud = baud
        self._ser: serial.Serial | None = None

    def open(self) -> None:
        if self._ser and self._ser.is_open:
            return
        self._ser = serial.Serial(self.port, self.baud, timeout=SERIAL_READ_TIMEOUT_SEC)
        time.sleep(SERIAL_OPEN_DELAY_SEC)
        self._ser.reset_input_buffer()

    def close(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None

    def __enter__(self) -> "MegaClient":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _readline(self) -> str:
        if not self._ser:
            raise RuntimeError("serial not open")
        line = self._ser.readline()
        if not line:
            raise TimeoutError(
                "serial read timeout; close Arduino Serial Monitor and check COM port / baud 115200"
            )
        return line.decode("ascii", errors="replace").strip()

    def _write_line(self, text: str) -> None:
        if not self._ser:
            raise RuntimeError("serial not open")
        self._ser.reset_input_buffer()
        self._ser.write((text + "\n").encode("ascii"))
        self._ser.flush()

    def _transact_ok(self, payload: str, retries: int = SERIAL_READ_RETRIES) -> None:
        last_err: Exception | None = None
        for _ in range(retries):
            try:
                self._write_line(payload)
                resp = self._readline()
                if resp == "OK" or resp.startswith("OK"):
                    return
                raise RuntimeError(f"unexpected response: {resp!r}")
            except Exception as e:
                last_err = e
                time.sleep(0.08)
        if last_err:
            raise last_err

    def ping(self, retries: int = SERIAL_READ_RETRIES) -> bool:
        last_err: Exception | None = None
        for _ in range(retries):
            try:
                self._write_line("PING")
                resp = self._readline()
                return resp == "PONG"
            except Exception as e:
                last_err = e
                time.sleep(0.08)
        if last_err:
            raise last_err
        return False

    def send_set_mod1(
        self,
        ns_angle: int,
        angles_1_to_15: list[int],
        retries: int = SERIAL_READ_RETRIES,
    ) -> None:
        """Module 1 board: SET,ns,a1..a15"""
        if len(angles_1_to_15) != 15:
            raise ValueError("mod1 needs exactly 15 small angles")
        parts = [str(ns_angle), *[str(a) for a in angles_1_to_15]]
        self._transact_ok("SET," + ",".join(parts), retries=retries)

    def send_set_mod2(
        self,
        angles_16_to_30: list[int],
        retries: int = SERIAL_READ_RETRIES,
    ) -> None:
        """Module 2 board: SET,a1..a15 (global servos 16-30)"""
        if len(angles_16_to_30) != 15:
            raise ValueError("mod2 needs exactly 15 small angles")
        parts = [str(a) for a in angles_16_to_30]
        self._transact_ok("SET," + ",".join(parts), retries=retries)

    def send_set(self, cmd: ServoCommand, retries: int = SERIAL_READ_RETRIES) -> None:
        """Legacy single-board SET with 31 channels (not used in dual-Mega setup)."""
        parts = [str(cmd.ns_angle), *[str(a) for a in cmd.small_angles]]
        self._transact_ok("SET," + ",".join(parts), retries=retries)


def dispatch_servo_command(
    cmd: ServoCommand,
    port_mod1: str,
    port_mod2: str,
    *,
    dry_run: bool = False,
) -> None:
    """Dual-Mega dispatch: mod1 = NS + servos 1-15; mod2 = servos 16-30."""
    if dry_run:
        return
    if not port_mod1 or not port_mod2:
        raise ValueError("port_mod1 and port_mod2 required")

    with MegaClient(port_mod1) as c1:
        if not c1.ping():
            raise RuntimeError(f"PING failed on mod1 ({port_mod1})")
        c1.send_set_mod1(cmd.ns_angle, cmd.small_angles[:15])

    with MegaClient(port_mod2) as c2:
        if not c2.ping():
            raise RuntimeError(f"PING failed on mod2 ({port_mod2})")
        c2.send_set_mod2(cmd.small_angles[15:])
