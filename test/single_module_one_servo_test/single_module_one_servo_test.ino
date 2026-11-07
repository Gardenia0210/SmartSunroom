/*
 * Mega + 1 块 PCA9685 + 1 个 SG90（通道 0）
 *
 * 接线：
 *   SDA=20, SCL=21, VCC=5V, GND=GND, V+=外部5V, OE不接
 *   舵机：通道0，棕=GND，红=V+，黄=信号
 *
 * 库：Adafruit PWM Servo Driver Library, Adafruit BusIO
 *
 * 动作：0° -> 90° -> 180° -> 90° -> 0°，每步 2 秒
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#define SERVOMIN  150
#define SERVOMAX  600
#define SERVO_CH  0

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40, Wire);

int angleToPulse(int angle) {
  angle = constrain(angle, 0, 180);
  return map(angle, 0, 180, SERVOMIN, SERVOMAX);
}

void setAngle(int angle) {
  int pulse = angleToPulse(angle);
  pwm.setPWM(SERVO_CH, 0, pulse);
  Serial.print(F("CH0 -> "));
  Serial.print(angle);
  Serial.print(F(" deg, pulse="));
  Serial.println(pulse);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; }

  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(60);

  Serial.println(F("=== Single module + 1 servo test ==="));
  Serial.println(F("PCA9685 @ 0x40, channel 0"));
  delay(1000);

  setAngle(90);
  delay(2000);
}

void loop() {
  setAngle(0);
  delay(2000);

  setAngle(90);
  delay(2000);

  setAngle(180);
  delay(2000);

  setAngle(90);
  delay(2000);

  Serial.println(F("--- cycle ---"));
}
