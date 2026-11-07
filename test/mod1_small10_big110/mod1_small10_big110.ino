/*
 * 模块1（COM8）自检：
 *   小舵机 1–15 → 全部转到 10°
 *   大功率舵机 A1 → 转到 110°
 *
 * 接线：PCA9685 0x40，SDA=20，SCL=21
 *       舵机 N → PCA 通道 N（1–15）
 *       大舵机信号 → A1
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <Servo.h>

#define SERVOMIN            150
#define SERVOMAX            600
#define BIG_SERVO_PIN       A1
#define SMALL_TARGET_DEG    10
#define BIG_TARGET_DEG      110
#define SERVO_STEP_DELAY_MS 300

Adafruit_PWMServoDriver pwm(0x40, Wire);
Servo bigServo;

int angleToPulse(int angle) {
  return map(constrain(angle, 0, 180), 0, 180, SERVOMIN, SERVOMAX);
}

void setSmallServo(uint8_t id, int angle) {
  if (id < 1 || id > 15) return;
  pwm.setPWM(id, 0, angleToPulse(angle));
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(60);

  bigServo.attach(BIG_SERVO_PIN);
  delay(500);

  Serial.println(F("MOD1: small servos 1-15 -> 10 deg"));
  for (uint8_t id = 1; id <= 15; id++) {
    setSmallServo(id, SMALL_TARGET_DEG);
    Serial.print(F("  servo "));
    Serial.print(id);
    Serial.println(F(" -> 10"));
    delay(SERVO_STEP_DELAY_MS);
  }

  Serial.println(F("MOD1: big servo -> 110 deg"));
  bigServo.write(BIG_TARGET_DEG);
  delay(600);

  Serial.println(F("Done. Holding."));
}

void loop() {
  // hold
}
