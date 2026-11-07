/*
 * 小舵机连通性自检 — 模块1（COM8）
 *
 * 接线：PCA9685 0x40，SDA=20，SCL=21
 *       舵机 N → PCA 通道 N（1–15；通道 0 不用）
 *
 * 动作：1→15 号依次：转到 150° → 停 2s → 转回 60° → 再下一号
 * 串口 115200 会打印当前测试的舵机号。
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define SERVOMIN       150
#define SERVOMAX       600
#define HOLD_MS        2000
#define BETWEEN_MS     200
#define LOCAL_FIRST    1
#define LOCAL_LAST     15

Adafruit_PWMServoDriver pwm(0x40, Wire);

int angleToPulse(int angle) {
  return map(constrain(angle, 0, 180), 0, 180, SERVOMIN, SERVOMAX);
}

void setServo(uint8_t id, int angle) {
  if (id < LOCAL_FIRST || id > LOCAL_LAST) return;
  pwm.setPWM(id, 0, angleToPulse(angle));
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(60);
  delay(500);

  Serial.println(F("MOD1 connectivity test: each servo 150deg (2s) then 60deg"));

  // 全部先归 60°
  for (uint8_t id = LOCAL_FIRST; id <= LOCAL_LAST; id++) {
    setServo(id, 60);
    delay(50);
  }
  delay(500);

  for (uint8_t id = LOCAL_FIRST; id <= LOCAL_LAST; id++) {
    Serial.print(F("Testing servo "));
    Serial.println(id);

    setServo(id, 150);
    delay(HOLD_MS);

    setServo(id, 60);
    delay(BETWEEN_MS);
  }

  Serial.println(F("MOD1 sweep done. All should be at 60deg."));
}

void loop() {
  // idle
}
