/*
 * 大功率舵机（A1）往复测试
 *
 * 烧到模块1 Mega（COM8）即可，可不接 PCA9685。
 *
 * 轨迹（1 个周期）：
 *   80° → 100° → 120° → 100° → 80° → 100°
 * 共循环 3 个周期，最后停在 100°。
 */

#include <Servo.h>

#define BIG_SERVO_PIN   A1
#define MOVE_SETTLE_MS  800
#define CYCLE_COUNT     3

Servo bigServo;

void goTo(int angle) {
  bigServo.write(constrain(angle, 0, 180));
  Serial.print(F("big servo -> "));
  Serial.println(angle);
  delay(MOVE_SETTLE_MS);
}

void setup() {
  Serial.begin(115200);
  bigServo.attach(BIG_SERVO_PIN);
  delay(500);

  // 起始到 80°
  goTo(80);

  for (uint8_t c = 1; c <= CYCLE_COUNT; c++) {
    Serial.print(F("===== cycle "));
    Serial.print(c);
    Serial.println(F(" ====="));

    goTo(100);
    goTo(120);
    goTo(100);
    goTo(80);
    goTo(100);
  }

  Serial.println(F("Done. Holding at 100 deg."));
}

void loop() {
  // hold at 100°
}
