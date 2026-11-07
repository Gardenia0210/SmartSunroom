/*
 * 小舵机连通性自检 — 模块2（COM10）
 *
 * 接线：PCA9685 0x40，SDA=20，SCL=21
 *       本地 L=1..15 → PCA 通道 L；全局编号 = 15 + L（16–30）
 *
 * 动作：16→30 号依次：转到 150° → 停 2s → 转回 60° → 再下一号
 * 串口 115200 会打印当前测试的全局舵机号。
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define SERVOMIN       150
#define SERVOMAX       600
#define HOLD_MS        2000
#define BETWEEN_MS     200
#define GLOBAL_FIRST   16
#define GLOBAL_LAST    30

Adafruit_PWMServoDriver pwm(0x40, Wire);

int angleToPulse(int angle) {
  return map(constrain(angle, 0, 180), 0, 180, SERVOMIN, SERVOMAX);
}

void setServoGlobal(uint8_t globalId, int angle) {
  if (globalId < GLOBAL_FIRST || globalId > GLOBAL_LAST) return;
  uint8_t ch = globalId - 15;  // 16→1 ... 30→15
  pwm.setPWM(ch, 0, angleToPulse(angle));
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(60);
  delay(500);

  Serial.println(F("MOD2 connectivity test: each servo 150deg (2s) then 60deg"));

  for (uint8_t id = GLOBAL_FIRST; id <= GLOBAL_LAST; id++) {
    setServoGlobal(id, 60);
    delay(50);
  }
  delay(500);

  for (uint8_t id = GLOBAL_FIRST; id <= GLOBAL_LAST; id++) {
    Serial.print(F("Testing servo "));
    Serial.println(id);

    setServoGlobal(id, 150);
    delay(HOLD_MS);

    setServoGlobal(id, 60);
    delay(BETWEEN_MS);
  }

  Serial.println(F("MOD2 sweep done. All should be at 60deg."));
}

void loop() {
  // idle
}
