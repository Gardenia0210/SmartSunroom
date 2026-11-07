这是一个智能阳光房项目代码：

代码核心功能：
1. 通过识别相片人体位置分割、用户类型&太阳角度，控制整块阳光房房顶&模块的角度变化，从而做到为人体不同部位遮挡阳光中不同类型的光线（UVB、UVA、VIS、NIR）

核心硬件：
arduino mega（1块）
舵机模块（2块，分别驱动1-15号舵机&16-30号舵机）
大功率舵机（1个，直接连Mega）
小功率舵机（30个，分别驱动1-30号玻璃板）

核心逻辑：
人体位置分割部分：
1. 输入：我点击确认拍摄键后，通过USB相机模块捕捉一张1280（高）* 720（宽）的相片
2. 使用人体分割模型对相片进行人体分割（只需要把所有类别聚类为3种：头部、肢体、主干（Head、Limbs、Torso））
3. 将相片**整体顺时针旋转 90°** 后，把旋转后的图像宽高等距分割为5（宽）*6（高）的30个方格并从左往右、从上往下依次编号
4. 每个方格如果有检测到人体部位，就以检测到面积最大的人体部位给该方格命名（头部、肢体、主干（Head、Limbs、Torso）3种其一），如果没有识别到人体部位该格记为空
5. 输出：玻璃序号&对应人体部位
可以参考E:\SFK\Project3\BodyPart_Det已经实现功能的代码

太阳角度：
1. 我输入给你（2个数值，一个南北角度：控制大功率舵机角度，一个东西角度：作为30个小功率舵机的初始零点）

用户类型：
1. 输入：年龄（一个1-100的整数）
对应用户类型：
0-14：children
15-44：Young Adults 
45-60：Middle-aged Adults
61-100： Elderly
若定义用户为：Young Adults 
需要进一步给出选项：
确认用户需求为：Relaxation-oriented/Tanning-oriented
从而将用户归类为：
Children
Young Adults (Tanning-oriented)
Young Adults (Relaxation-oriented)
Middle-aged Adults
Elderly
其中的一类

需要阻挡的光线类型：
1. 我输入给你（给我UVB、UVA、VIS、NIR4个选项4选一）

然后通过控制USB接口控制arduino Mega板以及其驱动的舵机模块来控制每个舵机

控制逻辑是：
1. 玻璃板（小舵机驱动）分为两类：需要与太阳角度平行的（零点角度+90度）/需要与太阳角度垂直的（保持零点角度）
2. 大舵机（把初始位置设为零点，以此为基准顺时针旋转之前输入的南北角度）

具体哪些序号的小玻璃板需要与太阳角度平行，需要根据用户类型&需要阻挡的光线类型决定，对应关系如下：
UVB：
Children：none
Young Adults (Tanning-oriented)：Torso、Limbs
Young Adults (Relaxation-oriented)：Limbs
Middle-aged Adults：Head、Torso、Limbs
Elderly：Torso、Limbs

UVA：
Children：none
Young Adults (Tanning-oriented)：Limbs
Young Adults(Relaxation-oriented)：none
Middle-aged Adults：none
Elderly：none

VIS：
Children：Head、Torso、Limbs
Young Adults (Tanning-oriented)：Head
Young Adults(Relaxation-oriented)：Head、Torso
Middle-aged Adults：Torso
Elderly：Head

NIR：
Children：Head、Torso、Limbs
Young Adults (Tanning-oriented)：Head
Young Adults(Relaxation-oriented)：Torso
Middle-aged Adults：Torso、Limbs
Elderly：Limbs

---

## 硬件接线说明

### 器件清单

| 器件 | 数量 | 说明 |
|------|------|------|
| Arduino Mega 2560 | 1 | 主控，USB 串口通信 |
| D2-4-4H 舵机驱动模块（PCA9685，16 路） | 2 | 各接 15 个小舵机，通道 15 留空 |
| 小功率 180° 舵机 | 30 | 1–30 号玻璃板 |
| 大功率 180° 舵机 | 1 | 南北向整体旋转，信号线直连 Mega **A1** |
| 5V 大电流电源 | 1 | 供舵机 V+（30 路同时动时电流大，勿仅靠 Mega 5V） |

### 单块 D2-4-4H 模块 ↔ Arduino Mega

| 模块引脚 | 接 Mega | 说明 |
|---------|---------|------|
| GND | GND | 共地 |
| OE | **不接** | 输出使能，悬空即可 |
| SCL | **Pin 21（SCL）** | I2C 时钟（模块说明书的 A5 对应 Uno；Mega 用 Pin 21） |
| SDA | **Pin 20（SDA）** | I2C 数据（模块说明书的 A4 对应 Uno；Mega 用 Pin 20） |
| VCC | 5V | 模块逻辑供电 |
| V+ | 5V（大电流电源） | 舵机动力电 |

> **引脚说明**：D2-4-4H 说明书按 Uno 标注 A4/A5；Mega 2560 的硬件 I2C 为 **Pin 20=SDA、Pin 21=SCL**，请按 Mega 丝印连接。

### 两块模块（各 15 路）— 双 Mega 方案（当前）

模块出厂 I2C 地址均为 **0x40**，焊盘无法改地址时，**一块 Mega 上两模块并联会同动**。  
当前采用 **两块 Arduino Mega**，各接一块模块（各自只用硬件 I2C 20/21）：

| 板子 | 默认串口 | 固件 | 接线 | 驱动 |
|------|----------|------|------|------|
| Mega 模块1 | **COM8** | `firmware/mod1_mega/` | SDA=**20**，SCL=**21**；大舵机 **A1** | 小舵机 1–15 + 大舵机 |
| Mega 模块2 | **COM10** | `firmware/mod2_mega/` | SDA=**20**，SCL=**21** | 小舵机 16–30 |

PCA 通道：每块板上舵机本地号 **N → 通道 N（1–15）**，通道 0 不用（与现场从 ch1 起的接线一致）。  
模块2：本地 1–15 = 全局舵机 16–30。

串口协议 115200：
- 模块1：`SET,ns,a1,...,a15`
- 模块2：`SET,a1,...,a15`（对应全局 16–30）

两板的舵机电源 V+/GND 建议共地到同一外部 5V 大电流电源。

### 电源要点

- Mega 5V → 两块模块 VCC（逻辑）
- 外部 5V 大电流 → 两块模块 V+ 及舵机红线（建议 ≥ 10A）
- **所有 GND 必须相连**：Mega、两块模块、外部电源负极、舵机 GND
- 上电顺序：先接好线 → 开舵机电源 → 再插 Mega USB
