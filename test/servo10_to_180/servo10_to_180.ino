/*
 * 单独测试：10 号舵机转到 180°
 *
 * 烧到模块1 那块 Mega（舵机 1–15，通常 COM8）
 * 接线：PCA9685 0x40，SDA=20，SCL=21
 *       舵机 10 → PCA 通道 10
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define SERVOMIN 150
#define SERVOMAX 600
#define SERVO_ID 10
#define TARGET_DEG 180

Adafruit_PWMServoDriver pwm(0x40, Wire);

int angleToPulse(int angle) {
  return map(constrain(angle, 0, 180), 0, 180, SERVOMIN, SERVOMAX);
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(60);
  delay(500);

  pwm.setPWM(SERVO_ID, 0, angleToPulse(TARGET_DEG));
  Serial.print(F("Servo "));
  Serial.print(SERVO_ID);
  Serial.print(F(" -> "));
  Serial.println(TARGET_DEG);
}

void loop() {
  // hold
}
