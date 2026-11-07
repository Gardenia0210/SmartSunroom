"""
Quick test: Mega returns 8 ADC channels. Usage:
  python test_serial.py
  python test_serial.py COM7
  python test_serial.py COM7 --loop
"""
from __future__ import print_function

import argparse
import sys
import time

import serial

import config
from serial_reader import open_serial, read_channels


def main() -> None:
    p = argparse.ArgumentParser(description="Send R to Mega and print one line of 8 values")
    p.add_argument("port", nargs="?", default="COM7", help="serial port, default COM7")
    p.add_argument("--loop", action="store_true", help="read every 0.5s until Ctrl+C")
    args = p.parse_args()

    try:
        print(
            "open {}, baud {}, reset wait {:.1f}s...".format(
                args.port, config.SERIAL_BAUD, config.SERIAL_OPEN_DELAY_SEC
            )
        )
        ser = open_serial(args.port, config.SERIAL_BAUD)
    except serial.SerialException as e:
        print("failed to open serial:", e, file=sys.stderr)
        sys.exit(1)

    def once():
        try:
            vals = read_channels(ser)
        except Exception as e:
            print(str(e), file=sys.stderr)
            return False
        print(
            "S(A0,A1): {:4d} {:4d}  W(A2,A3): {:4d} {:4d}  N(A4,A5): {:4d} {:4d}  E(A6,A7): {:4d} {:4d}".format(
                *vals
            )
        )
        return True

    try:
        if args.loop:
            print("looping (Ctrl+C to stop)")
            while True:
                once()
                time.sleep(0.5)
        else:
            once()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
