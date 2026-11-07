/*
 * 模块2（COM10）自检：
 *   小舵机 16–30（本板通道 1–15）→ 全部转到 10°
 *
 * 接线：PCA9685 0x40，SDA=20，SCL=21
 *       本地 L=1..15 → PCA 通道 L；全局编号 = 15 + L
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define SERVOMIN            150
#define SERVOMAX            600
#define SMALL_TARGET_DEG    10
#define SERVO_STEP_DELAY_MS 300
#define GLOBAL_FIRST        16
#define GLOBAL_LAST         30

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

  Serial.println(F("MOD2: small servos 16-30 -> 10 deg"));

  for (uint8_t id = GLOBAL_FIRST; id <= GLOBAL_LAST; id++) {
    setServoGlobal(id, SMALL_TARGET_DEG);
    Serial.print(F("  servo "));
    Serial.print(id);
    Serial.println(F(" -> 10"));
    delay(SERVO_STEP_DELAY_MS);
  }

  Serial.println(F("Done. Holding."));
}

void loop() {
  // hold
}
