# Serial and sampling parameters (edit for your machine)
SERIAL_BAUD = 115200
# Opening USB often resets Mega; sketch needs ~1.5-2.5s before loop
SERIAL_OPEN_DELAY_SEC = 2.5
SERIAL_READ_TIMEOUT_SEC = 2.0
SERIAL_READ_RETRIES = 4
SAMPLE_INTERVAL_SEC = 0.5
SAMPLES_PER_SESSION = 100

# A0-A7 to matrix rows: each row is a pair of photoresistors for one direction
# Default order: East, South, West, North — reorder if wiring differs
ROWS_ORDER = ("east", "south", "west", "north")

# Arduino analog channel indices per direction (0 = A0)
PIN_GROUPS = {
    "south": (0, 1),
    "west": (2, 3),
    "north": (4, 5),
    "east": (6, 7),
}

OUTPUT_DIR = "data"
