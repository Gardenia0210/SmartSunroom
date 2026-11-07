"""Project paths and runtime constants (no demo presets)."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
CODE_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PACKAGE_ROOT / "data"
PHOTOS_DIR = DATA_DIR / "photos"
CAPTURES_DIR = DATA_DIR / "captures"
OUTPUTS_DIR = DATA_DIR / "outputs"

# Sibling solar-angle package (collection + trained model artifacts)
SOLAR_ANGLE_ROOT = CODE_ROOT / "solar_angle"
ANGLE_COLLECTOR = SOLAR_ANGLE_ROOT / "data_collection"
ANGLE_MODEL_TRAIN = SOLAR_ANGLE_ROOT / "model_training"

GRID_COLS = 5
GRID_ROWS = 6
GRID_COUNT = GRID_COLS * GRID_ROWS

CAPTURE_WIDTH = 720
CAPTURE_HEIGHT = 1280

# Rotate full image 90 degrees clockwise before segmentation (matches glass layout)
IMAGE_ROTATE_CW90 = True

SERIAL_BAUD = 115200
# Opening USB resets Mega; wait until firmware enters loop before PING
SERIAL_OPEN_DELAY_SEC = 4.0
# Firmware SET uses ~300 ms per channel x 15; dual boards need a long read timeout
SERIAL_READ_TIMEOUT_SEC = 12.0
SERIAL_READ_RETRIES = 5

DEFAULT_MODEL = "fashn-ai/fashn-human-parser"

# Optional default COM ports (override in GUI / CLI; empty = pick from list)
DEFAULT_ANGLE_PORT = ""
DEFAULT_MEGA_PORT = ""   # module 1: servos 1-15 + big NS servo
DEFAULT_MEGA2_PORT = ""  # module 2: servos 16-30

# Mechanical zero of the large NS servo (degrees)
BIG_SERVO_ZERO_DEG = 110.0

# Block-highlight visualization colors (RGBA / RGB)
BLOCK_HIGHLIGHT_FILL = (255, 48, 48, 150)
BLOCK_HIGHLIGHT_OUTLINE = (255, 230, 40)
BLOCK_DIM_FILL = (20, 20, 20, 90)
