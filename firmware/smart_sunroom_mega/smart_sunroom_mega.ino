/*
 * SmartSunroom — Arduino Mega 2560 舵机固件
 *
 * ========== 双模块同地址 0x40：必须分总线接线 ==========
 *   模块 1 (0x40)：硬件 I2C  SDA=20, SCL=21  → 小舵机 1–15，PCA 通道 0–14
 *   模块 2 (0x40)：软件 I2C  SDA=18, SCL=19  → 小舵机 16–30，PCA 通道 0–14
 *   大功率舵机：A1
 *
 *   VCC / V+ / GND 可共用；SDA、SCL 绝不可两块并联到同一组脚！
 *   模块 2 的 SDA→18、SCL→19（从 20/21 上拆下来）。
 *
 * 依赖库：Adafruit PWM Servo Driver、Adafruit BusIO、SoftwareWire、Servo
 *
 * 串口 115200：
 *   PING          → PONG
 *   SET,ns,a1..a30 → OK
 *   TEST1         → 只动模块1（舵机1→10°，其余模块1 保持）
 *   TEST2         → 只动模块2（舵机16→10°，其余模块2 保持）
 */

#include <Wire.h>
#include <SoftwareWire.h>
#include <Adafruit_PWMServoDriver.h>
#include <Servo.h>
#include "Pca9685SoftWire.h"

#define SERIAL_BAUD     115200
#define BIG_SERVO_PIN   A1
#define SERVOMIN        150
#define SERVOMAX        600
#define SMALL_SERVO_CNT 30
#define LINE_BUF_SIZE   256

// 模块 2：软件 I2C（与硬件 I2C 分离，故可同为 0x40）
#define SOFT_SDA        18
#define SOFT_SCL        19

#define I2C_ADDR        0x40

SoftwareWire softWire(SOFT_SDA, SOFT_SCL);
Adafruit_PWMServoDriver pwm1(I2C_ADDR, Wire);   // 模块1：20/21
Pca9685SoftWire pwm2(softWire, I2C_ADDR);       // 模块2：18/19
Servo bigServo;

char lineBuf[LINE_BUF_SIZE];
uint8_t lineLen = 0;

int angleToPulse(int angle) {
  angle = constrain(angle, 0, 180);
  return map(angle, 0, 180, SERVOMIN, SERVOMAX);
}

// id 1–15 → 模块1 通道 0–14；id 16–30 → 模块2 通道 0–14
void setSmallServo(uint8_t id, int angle) {
  if (id < 1 || id > SMALL_SERVO_CNT) return;
  int pulse = angleToPulse(angle);
  if (id <= 15) {
    pwm1.setPWM(id - 1, 0, pulse);
  } else {
    pwm2.setPWM(id - 16, 0, pulse);
  }
}

void setModule1Servos(int angle) {
  for (uint8_t id = 1; id <= 15; id++) {
    setSmallServo(id, angle);
  }
}

void setModule2Servos(int angle) {
  for (uint8_t id = 16; id <= 30; id++) {
    setSmallServo(id, angle);
  }
}

void setAllSmallServos(int angle) {
  setModule1Servos(angle);
  setModule2Servos(angle);
}

void initPwmBoards() {
  Wire.begin();
  softWire.begin();

  pwm1.begin();
  pwm1.setPWMFreq(60);
  delay(10);

  pwm2.begin();  // 内部已 setPWMFreq(60)
  delay(10);
}

bool parseSetCommand(const char *line, int *nsAngle, int *smallAngles) {
  if (strncmp(line, "SET,", 4) != 0) return false;

  const char *p = line + 4;
  char *endPtr = NULL;

  *nsAngle = (int)strtol(p, &endPtr, 10);
  if (endPtr == p || *endPtr != ',') return false;
  p = endPtr + 1;

  for (uint8_t i = 0; i < SMALL_SERVO_CNT; i++) {
    smallAngles[i] = (int)strtol(p, &endPtr, 10);
    if (endPtr == p) return false;
    if (i < SMALL_SERVO_CNT - 1) {
      if (*endPtr != ',') return false;
      p = endPtr + 1;
    }
  }
  return true;
}

void handleLine(const char *line) {
  if (strcmp(line, "PING") == 0) {
    Serial.println(F("PONG"));
    return;
  }

  // 分模块自检：确认接线是否分开（模块2必须在 18/19）
  if (strcmp(line, "TEST1") == 0) {
    setModule1Servos(60);
    setSmallServo(1, 10);
    Serial.println(F("OK,TEST1"));  // 应只有模块1 的 1 号舵机动到 10°
    return;
  }
  if (strcmp(line, "TEST2") == 0) {
    setModule2Servos(60);
    setSmallServo(16, 10);
    Serial.println(F("OK,TEST2"));  // 应只有模块2 的 16 号舵机动到 10°
    return;
  }

  if (strncmp(line, "SET,", 4) == 0) {
    int nsAngle = 90;
    int smallAngles[SMALL_SERVO_CNT];
    if (!parseSetCommand(line, &nsAngle, smallAngles)) {
      Serial.println(F("ERR,parse"));
      return;

    }
    bigServo.write(constrain(nsAngle, 0, 180));
    for (uint8_t i = 0; i < SMALL_SERVO_CNT; i++) {
      setSmallServo(i + 1, smallAngles[i]);
    }
    Serial.println(F("OK"));
    return;
  }

  Serial.println(F("ERR,unknown"));
}

void setup() {
  Serial.begin(SERIAL_BAUD);

  initPwmBoards();

  bigServo.attach(BIG_SERVO_PIN);
  delay(500);
  bigServo.write(110);
  setAllSmallServos(60);

  Serial.println(F("READY"));
  Serial.println(F("I2C: mod1=Wire(20/21)@0x40 servos1-15; mod2=Soft(18/19)@0x40 servos16-30"));
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      lineBuf[lineLen] = '\0';
      if (lineLen > 0) handleLine(lineBuf);
      lineLen = 0;
      continue;
    }
    if (lineLen < LINE_BUF_SIZE - 1) {
      lineBuf[lineLen++] = c;
    }
  }
}
