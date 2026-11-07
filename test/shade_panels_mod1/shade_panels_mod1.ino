/*
 * 单独测试 — 模块1（接 COM8 那块 Mega）
 *
 * 接线：PCA9685 0x40，SDA=20，SCL=21
 *       舵机 N → PCA 通道 N（1–15；通道 0 不用）
 *
 * 动作：全局 6,9,10,11,12 → 150°；本板其余 → 60°
 *       （22–29 在模块2 上，见 shade_panels_mod2）
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define SERVOMIN            150
#define SERVOMAX            600
#define SERVO_STEP_DELAY_MS 300

Adafruit_PWMServoDriver pwm(0x40, Wire);

// 本板负责的全局编号里，需翻到 150° 的
const uint8_t PARALLEL_IDS[] = {6, 9, 10, 11, 12};
const uint8_t PARALLEL_CNT = sizeof(PARALLEL_IDS) / sizeof(PARALLEL_IDS[0]);

int angleToPulse(int angle) {
  return map(constrain(angle, 0, 180), 0, 180, SERVOMIN, SERVOMAX);
}

bool isParallel(uint8_t globalId) {
  for (uint8_t i = 0; i < PARALLEL_CNT; i++) {
    if (PARALLEL_IDS[i] == globalId) return true;
  }
  return false;
}

void setServo(uint8_t globalId, int angle) {
  // 本板全局 1–15 → 通道 1–15
  if (globalId < 1 || globalId > 15) return;
  pwm.setPWM(globalId, 0, angleToPulse(angle));
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(60);
  delay(500);

  Serial.println(F("MOD1: set parallel panels to 150, others 60"));

  for (uint8_t id = 1; id <= 15; id++) {
    int angle = isParallel(id) ? 150 : 60;
    setServo(id, angle);
    Serial.print(F("  servo "));
    Serial.print(id);
    Serial.print(F(" -> "));
    Serial.println(angle);
    delay(SERVO_STEP_DELAY_MS);
  }

  Serial.println(F("MOD1 done. Holding."));
}

void loop() {
  // hold
}
