# SmartSunroom_Code

Cleaned, self-contained copy of the Smart Sunroom software stack.
Source projects (`SmartSunroom`, `AnglePre`) are **not** modified.

## Layout

```
SmartSunroom_Code/
├── solar_angle/                 # Photoresistor solar-angle model
│   ├── data_collection/         # Serial ADC collection + normalization
│   ├── model_training/          # Train / predict classifiers
│   └── firmware/
│       └── photoresistor_reader/
├── mechanical_control/          # Body grid + shading rules + dual Mega control
│   ├── rules/                   # Block rules, user profile, servo math
│   ├── bodypart/                # Segmentation + 5x6 grid mapping
│   ├── angle_inference/         # Call trained solar-angle model
│   ├── serial_comm/             # Dual Mega PING/SET protocol
│   ├── io/                      # Session / servo CSV writers
│   ├── firmware/
│   │   ├── mod1_mega/           # Servos 1-15 + big NS servo
│   │   └── mod2_mega/           # Servos 16-30
│   ├── gui.py                   # Interactive wizard UI
│   ├── cli.py                   # Command-line tools
│   └── pipeline.py              # End-to-end orchestration
├── run_gui.py
├── run_cli.py
├── requirements.txt
└── README.md
```

## Install

```bash
cd SmartSunroom_Code
pip install -r requirements.txt
```

Place trained artifacts under:

- `solar_angle/data_collection/data_normalized/normalization_meta.json`
- `solar_angle/model_training/artifacts/model.joblib`
- `solar_angle/model_training/artifacts/classes.json`

(Copy from the original AnglePre project after training.)

## Typical workflow

1. **Collect** photoresistor samples (`solar_angle/data_collection`).
2. **Train** the angle classifier (`solar_angle/model_training`).
3. Flash Mega firmware (`mechanical_control/firmware/mod1_mega`, `mod2_mega`).
4. Run GUI or CLI:

```bash
python run_gui.py

python run_cli.py list-ports
python run_cli.py detect --image path/to/photo.jpg
python run_cli.py analyze --image path/to/photo.jpg --age 30 --young-mode relaxation --light UVB --ns-angle 20 --ew-zero 60
python run_cli.py compute --grid-csv path/to/grid_5x6.csv --age 30 --young-mode relaxation --light UVB --ns-angle 20 --ew-zero 60
```

## Input / output (no demo presets)

| Stage | Required inputs | Outputs |
|-------|-----------------|---------|
| Angle inference | Angle-board COM port + trained model | N–S / E–W degrees |
| Segmentation | Photo path (or existing grid CSV) | `*_grid_5x6.csv` / `.png` |
| Shading | Age, young-mode (15–44), light band, sun angles, grid | Servo angles, highlight map |
| Dispatch | Mega1 + Mega2 COM ports | `SET` commands over serial |

Age, young-adult mode, COM ports, and solar angles are **user-provided or model-predicted** — demo force-angles and preset ages are removed.

## Dual Mega protocol

- **Module 1**: `PING` → `PONG`; `SET,ns,a1..a15`
- **Module 2**: `PING` → `PONG`; `SET,a1..a15` (global panels 16–30)
- Channel index N drives servo N on the PCA9685 (`setPWM(id, ...)`).
- Big NS servo absolute angle = `BIG_SERVO_ZERO_DEG (110) + logical N–S`.

## Notes

- Comments and UI strings are English.
- Grid cell CSV may still use the label `空` for empty cells (compatibility with existing datasets).
- Run Python with `SmartSunroom_Code` as the working directory (or on `PYTHONPATH`) so `mechanical_control` imports resolve.
