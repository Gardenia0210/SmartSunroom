/*
 * 双模块分总线自检（两块均为 0x40）
 *
 * 接线：
 *   模块1 SDA=20 SCL=21 → 舵机 1–15
 *   模块2 SDA=18 SCL=19 → 舵机 16–30（必须从 20/21 拆开！）
 *
 * 动作：先只动模块1 全部到 90°，停 2s；再只动模块2 全部到 90°。
 * 若两阶段两块板一起动 → 模块2 仍接在硬件 I2C 上。
 */

#include <Wire.h>
#include <SoftwareWire.h>
#include <Adafruit_PWMServoDriver.h>
#include "Pca9685SoftWire.h"

#define SERVOMIN 150
#define SERVOMAX 600
#define SOFT_SDA 18
#define SOFT_SCL 19

SoftwareWire softWire(SOFT_SDA, SOFT_SCL);
Adafruit_PWMServoDriver pwm1(0x40, Wire);
Pca9685SoftWire pwm2(softWire, 0x40);

int angleToPulse(int angle) {
  return map(constrain(angle, 0, 180), 0, 180, SERVOMIN, SERVOMAX);
}

void setMod1(int angle) {
  int p = angleToPulse(angle);
  for (int ch = 0; ch < 15; ch++) pwm1.setPWM(ch, 0, p);
}

void setMod2(int angle) {
  int p = angleToPulse(angle);
  for (int ch = 0; ch < 15; ch++) pwm2.setPWM(ch, 0, p);
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  softWire.begin();
  pwm1.begin();
  pwm1.setPWMFreq(60);
  pwm2.begin();
  delay(500);

  Serial.println(F("Phase A: ONLY module1 -> 90deg (20/21)"));
  setMod1(90);
  delay(2000);

  Serial.println(F("Phase B: ONLY module2 -> 90deg (18/19)"));
  setMod2(90);
  delay(2000);

  Serial.println(F("Done. If both boards moved in both phases, rewire module2 to 18/19."));
}

void loop() {}
