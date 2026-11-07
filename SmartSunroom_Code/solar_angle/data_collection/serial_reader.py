import time
from typing import List, Optional

import serial

import config


def open_serial(port: str, baud: int, timeout: Optional[float] = None) -> serial.Serial:
    """Open serial port and clear buffer after board reset."""
    if timeout is None:
        timeout = config.SERIAL_READ_TIMEOUT_SEC
    ser = serial.Serial(port, baud, timeout=timeout)
    time.sleep(config.SERIAL_OPEN_DELAY_SEC)
    ser.reset_input_buffer()
    return ser


def read_channels(ser: serial.Serial, retries: int = None) -> List[int]:
    """Send R, read one line of 8 ADC values; on failure clear buffer and retry."""
    retries = config.SERIAL_READ_RETRIES if retries is None else retries
    last_err: Exception = TimeoutError("serial read timeout; no data received")

    for _ in range(retries):
        try:
            ser.reset_input_buffer()
            ser.write(b"R\r\n")
            ser.flush()
            line = ser.readline()
            if not line:
                last_err = TimeoutError(
                    "serial read timeout; no data received. "
                    "Close Arduino Serial Monitor, check COM port and baud 115200; "
                    "unplug/replug USB if it still fails."
                )
                time.sleep(0.08)
                continue
            text = line.decode("ascii", errors="replace").strip()
            parts = text.split(",")
            if len(parts) != 8:
                last_err = ValueError(f"expected 8 values, got: {text!r}")
                time.sleep(0.08)
                continue
            return [int(p.strip()) for p in parts]
        except ValueError as e:
            last_err = e
            time.sleep(0.08)

    raise last_err
