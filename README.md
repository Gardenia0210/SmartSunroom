# SmartSunroom — 智能阳光房

通过 USB 相机拍摄人体照片，分割出 30 格（5×6）人体部位，结合用户类型、光线类型与太阳角度，经串口控制 Arduino Mega 驱动 31 路舵机（30 小 + 1 大），实现针对性遮阳。

**详细需求与遮挡规则** → [`Instruction.md`](Instruction.md)  
**开发进度记录** → [`log.md`](log.md)

---

## 快速开始

### 环境

```powershell
cd E:\SFK\Project3\SmartSunroom

# 可复用 BodyPart_Det 的 venv（已含 torch / opencv 等）
E:\SFK\Project3\BodyPart_Det\.venv\Scripts\pip install -r requirements.txt
E:\SFK\Project3\BodyPart_Det\.venv\Scripts\pip install -r requirements-dev.txt
```

### 纯软件分析（无需硬件 / 串口）

1. 把照片放进 [`data/photos/`](data/photos/)
2. 运行：

```powershell
python -m src.cli analyze ^
  --image data/photos/你的照片.jpg ^
  --age 25 ^
  --young-mode relaxation ^
  --light UVB ^
  --ns-angle 45 ^
  --ew-zero 30
```

终端会打印**与太阳平行 / 垂直的玻璃序号**；同时生成 `data/outputs/{照片名}_orientation.txt`、网格 CSV 与可视化图。

### GUI 演示向导（推荐演示流程）

```powershell
python -m src.gui
```

分 4 步：

1. **预测太阳角**（默认角度口 `COM11` / AnglePre）→ 界面固定显示东西 **60°**、南北 **75°**
2. **确认** → 大功率舵机到绝对角 **125°**（机械零点 110°）；需选择舵机板 COM
3. **选择模拟层** UVA / UVB / VIS / NIR（及年龄）→ 确认后弹出**需遮挡玻璃板高亮图**（红亮+黄框）
4. **执行翻板** → 双板下发：模块1 **COM8**（1–15+大舵机）+ 模块2 **COM10**（16–30）

可勾选「仅计算 / 不下发」做无硬件演练；可取消「从角度板采样」直接显示演示角度。

### Arduino 固件（双 Mega，两模块均为 0x40）

| 板子 | 固件 | 串口 | 内容 |
|------|------|------|------|
| 模块1 | [`firmware/mod1_mega/mod1_mega.ino`](firmware/mod1_mega/mod1_mega.ino) | COM8 | 20/21 + 大舵机 A1 → 舵机 1–15 |
| 模块2 | [`firmware/mod2_mega/mod2_mega.ino`](firmware/mod2_mega/mod2_mega.ino) | COM10 | 20/21 → 舵机 16–30 |

库：**Adafruit PWM Servo Driver**、**Adafruit BusIO**（无需 SoftwareWire）。  
上传后 115200 发 `PING` → `PONG`；模块1 应打印 `READY,MOD1`，模块2 为 `READY,MOD2`。

### CLI 命令

在项目根目录执行（将 `COM7` 换成你的端口）：

```powershell
# 串口 + 舵机测试
python -m src.cli servo-test --port COM7 --ns-angle 45 --small-angle 90

# 仅人体分割
python -m src.cli detect --image path\to\photo.jpg

# 列出串口
python -m src.cli list-ports

# 从已有 grid CSV 只算角度（不分割、不发串口）
python -m src.cli compute --grid-csv data/outputs/xxx_grid_5x6.csv --age 25 --young-mode relaxation --light UVB --ns-angle 45 --ew-zero 30

# 完整流程（只算角度，不发串口）
python -m src.cli run --age 25 --young-mode relaxation --light UVB --ns-angle 45 --ew-zero 30 --image path\to\photo.jpg --dry-run

# 完整流程（含串口下发）
python -m src.cli run --port COM7 --age 25 --young-mode relaxation --light UVB --ns-angle 45 --ew-zero 30 --capture
```

`run` 会额外输出 `data/outputs/{stem}_servos.csv` 与 `{stem}_session.json`。

---

## 「servo-test」在哪里？

**没有单独的 `servo_test.py` 文件。** `servo-test` 是 CLI 的一个子命令，定义在：

| 文件 | 作用 |
|------|------|
| [`src/cli.py`](src/cli.py) | `cmd_servo_test()` — 命令行入口 |
| [`src/serial/mega_client.py`](src/serial/mega_client.py) | `MegaClient.ping()` / `send_set()` — 串口通信 |
| [`firmware/smart_sunroom_mega/smart_sunroom_mega.ino`](firmware/smart_sunroom_mega/smart_sunroom_mega.ino) | Mega 端解析 `PING` / `SET` 并驱动舵机 |

调用链：`python -m src.cli servo-test` → `cmd_servo_test` → `MegaClient` → 串口 → Arduino 固件。

---

## 代码结构

```
SmartSunroom/
├── Instruction.md          # 需求、遮挡规则、硬件接线
├── README.md               # 本文件：结构说明与用法
├── log.md                  # 开发进度日志
├── requirements.txt
├── firmware/
│   └── smart_sunroom_mega/
│       └── smart_sunroom_mega.ino   # Arduino 主固件
├── test/
│   ├── big_servo_test/
│   │   └── big_servo_test.ino       # 大舵机 ±30° 零点测试（A1）
│   └── small_servos_test/
│       └── small_servos_test.ino    # 30 路小舵机 10/90/170/0° 测试
├── src/
│   ├── cli.py              # CLI：detect / compute / run / servo-test / list-ports
│   ├── gui.py              # Tkinter GUI（确认拍摄 + 运行控制）
│   ├── pipeline.py         # 检测 / 算角 / 完整流程编排
│   ├── config.py           # 路径、网格 5×6、串口波特率等常量
│   ├── models.py           # BodyPart, UserCategory, LightType, GridCell, ServoCommand
│   ├── user_profile.py     # 年龄 → 用户类型（含 Young Adults 子类型）
│   ├── block_rules.py      # 用户类型 × 光线类型 → 需遮挡的身体部位
│   ├── sunroom_control.py  # 网格 + 规则 → 31 路舵机角度
│   ├── io/
│   │   └── results.py      # 舵机 CSV / session JSON 导出
│   ├── bodypart/           # 人体分割（迁移自 BodyPart_Det）
│   │   ├── class_map.py    # 模型细类 → Head/Torso/Limbs
│   │   ├── segmentation.py # fashn-human-parser 推理
│   │   ├── grid_mapper.py  # 5×6 网格、CSV 读写
│   │   └── camera.py       # USB 相机单帧采集
│   └── serial/
│       ├── mega_client.py  # pyserial 封装
│       └── ports.py        # 枚举 COM 口
├── tests/
│   ├── test_sunroom_control.py
│   └── test_io_and_rules.py
└── data/
    ├── captures/           # 拍照原图
    └── outputs/            # 网格 CSV、可视化 PNG
```

---

## 数据流

```
USB 相机拍照 (720×1280)
    ↓
人体分割 → 30 格 × (Head / Torso / Limbs / 空)
    ↓
用户输入：年龄、光线类型(UVB/UVA/VIS/NIR)、太阳角度(ns, ew_zero)
    ↓
block_rules：决定哪些部位需要遮挡
    ↓
sunroom_control：每格 → ew_zero 或 ew_zero+90；大舵机 → ns_angle
    ↓
串口 SET,ns,a1,...,a30 → Arduino → PCA9685 × 2 + A1
```

---

## 串口协议（115200 8N1）

| 发送 | 响应 | 说明 |
|------|------|------|
| `PING` | `PONG` | 连接测试 |
| `SET,<ns>,<a1>,...,<a30>` | `OK` | ns=大舵机角度；a1–a30=小舵机 1–30 角度（0–180） |
| 非法命令 | `ERR,...` | 解析失败 |

---

## 硬件概要

见 [`Instruction.md` § 硬件接线说明](Instruction.md)。要点：

- 模块 1：硬件 I2C Pin 20/21 → 舵机 1–15（通道 0–14）
- 模块 2：软件 I2C Pin 18/19 → 舵机 16–30（通道 0–14）
- 大功率舵机：A1
- 两块 PCA9685 均为地址 0x40，因焊盘不可改，采用 SoftwareWire 分总线

---

## 相关项目

| 路径 | 用途 |
|------|------|
| `E:\SFK\Project3\BodyPart_Det` | 人体分割参考实现（已迁移到 `src/bodypart/`） |
| `E:\SFK\Project3\AnglePre` | 串口采集参考（波特率 115200、打开延迟等） |
| `E:\SFK\Project3\arduino\` | PCA9685 / 大舵机测试 sketch |

---

## 测试

```powershell
python -m pytest tests/ -q
# 若无 pytest：pip install pytest
```
