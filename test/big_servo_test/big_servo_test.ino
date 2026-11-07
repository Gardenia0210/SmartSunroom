/*
 * 大功率舵机测试 — SmartSunroom
 *
 * 接线：信号线 → Mega A1
 * 逻辑：上电后将当前校准位置标为 0 点，依次转动
 *       0+30° → 0° → 0-30° → 回归 0°，循环
 *
 * 使用前：手动将舵机摆至期望零点位置，再上电/复位。
 *         程序启动后会用 ZERO_US 锁定该点为逻辑 0°（默认 1500μs）。
 *         若零点有偏差，可修改下方 ZERO_US 或在首次启动后微调。
 */

#include <Servo.h>

#define BIG_SERVO_PIN   A1
#define SERVO_MIN_US    500
#define SERVO_MAX_US    2500
#define MOVE_DELAY_MS   3000
#define PAUSE_MS        1500

Servo bigServo;
int zeroUs = 1500;

int usForRelativeAngle(int deg) {
  long span = (long)(SERVO_MAX_US - SERVO_MIN_US);
  int us = zeroUs + (int)((long)deg * span / 180L);
  return constrain(us, SERVO_MIN_US, SERVO_MAX_US);
}

void moveRelative(int deg) {
  int us = usForRelativeAngle(deg);
  bigServo.writeMicroseconds(us);
  Serial.print(F("  -> "));
  Serial.print(deg);
  Serial.print(F(" deg (rel), us="));
  Serial.println(us);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }

  Serial.println(F("Big Servo Test (A1)"));
  Serial.println(F("Place horn at desired ZERO, then wait..."));
  delay(2000);

  bigServo.attach(BIG_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  delay(300);

  // 将当前校准点标为逻辑 0 点（默认 1500us ≈ 中位）
  zeroUs = 1500;
  bigServo.writeMicroseconds(zeroUs);
  delay(800);

  Serial.print(F("Zero set at us="));
  Serial.println(zeroUs);
  Serial.println(F("Sequence: +30 -> 0 -> -30 -> 0"));
  delay(PAUSE_MS);
}

void loop() {
  Serial.println(F("+30 deg"));
  moveRelative(30);
  delay(MOVE_DELAY_MS);

  Serial.println(F("0 deg"));
  moveRelative(0);
  delay(MOVE_DELAY_MS);

  Serial.println(F("-30 deg"));
  moveRelative(-30);
  delay(MOVE_DELAY_MS);

  Serial.println(F("return 0 deg"));
  moveRelative(0);
  delay(MOVE_DELAY_MS);

  Serial.println(F("--- cycle ---"));
  delay(PAUSE_MS);
}
