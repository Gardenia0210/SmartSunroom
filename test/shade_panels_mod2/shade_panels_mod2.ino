/*
 * 单独测试 — 模块2（接 COM10 那块 Mega）
 *
 * 接线：PCA9685 0x40，SDA=20，SCL=21
 *       本地 L=1..15 → PCA 通道 L；全局编号 = 15 + L（16–30）
 *
 * 动作：全局 22,23,24,27,28,29 → 150°；本板其余 → 60°
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define SERVOMIN            150
#define SERVOMAX            600
#define SERVO_STEP_DELAY_MS 300

Adafruit_PWMServoDriver pwm(0x40, Wire);

// 本板负责的全局编号里，需翻到 150° 的
const uint8_t PARALLEL_IDS[] = {22, 23, 24, 27, 28, 29};
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

void setServoGlobal(uint8_t globalId, int angle) {
  // 全局 16–30 → 本地通道 1–15
  if (globalId < 16 || globalId > 30) return;
  uint8_t ch = globalId - 15;  // 16→1 ... 30→15
  pwm.setPWM(ch, 0, angleToPulse(angle));
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(60);
  delay(500);

  Serial.println(F("MOD2: set parallel panels to 150, others 60"));

  for (uint8_t id = 16; id <= 30; id++) {
    int angle = isParallel(id) ? 150 : 60;
    setServoGlobal(id, angle);
    Serial.print(F("  servo "));
    Serial.print(id);
    Serial.print(F(" -> "));
    Serial.println(angle);
    delay(SERVO_STEP_DELAY_MS);
  }

  Serial.println(F("MOD2 done. Holding."));
}

void loop() {
  // hold
}
