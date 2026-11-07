/*

 * 30 路小舵机测试 — SmartSunroom

 *

 * 参考 D2-4-4H 模块示例（16_channel_PWM_Test1.ino）：

 *   SERVOMIN=150, SERVOMAX=600, setPWMFreq(60), pwm.setPWM(ch, 0, pulse)

 *

 * 硬件：

 *   模块 1 (0x40)：硬件 I2C Pin 20/21 → 舵机 1–15，通道 0–14

 *   模块 2 (0x40)：软件 I2C Pin 18/19 → 舵机 16–30，通道 0–14

 *

 * 动作：10° → 90° → 170° → 0°，循环

 */



#include <Wire.h>

#include <SoftwareWire.h>

#include <Adafruit_PWMServoDriver.h>

#include "Pca9685SoftWire.h"



// 与 D2-4-4H 示例一致

#define SERVOMIN  150

#define SERVOMAX  600



#define SMALL_SERVO_CNT 30

#define MOVE_DELAY_MS   3000

#define PAUSE_MS        1500



#define SOFT_SDA        18

#define SOFT_SCL        19



SoftwareWire softWire(SOFT_SDA, SOFT_SCL);

Adafruit_PWMServoDriver pwm1(0x40, Wire);   // 模块 1，默认地址 0x40

Pca9685SoftWire pwm2(softWire, 0x40);     // 模块 2，同地址，走 SoftwareWire



int angleToPulse(int angle) {

  angle = constrain(angle, 0, 180);

  return map(angle, 0, 180, SERVOMIN, SERVOMAX);

}



void initPwmBoard1() {

  pwm1.begin();

  pwm1.setPWMFreq(60);   // 与模块示例一致：模拟舵机 ~60Hz

}



void setSmallServo(uint8_t id, int angle) {

  if (id < 1 || id > SMALL_SERVO_CNT) return;

  uint16_t pulse = (uint16_t)angleToPulse(angle);

  if (id <= 15) {

    pwm1.setPWM(id - 1, 0, pulse);

  } else {

    pwm2.setPWM(id - 16, 0, pulse);

  }

}



void setAllSmallServos(int angle) {

  for (uint8_t i = 1; i <= SMALL_SERVO_CNT; i++) {

    setSmallServo(i, angle);

  }

}



void moveAll(int angle) {

  Serial.print(F("All servos -> "));

  Serial.print(angle);

  Serial.println(F(" deg"));

  setAllSmallServos(angle);

}



void setup() {

  Serial.begin(115200);

  while (!Serial) { ; }



  Wire.begin();

  softWire.begin();



  initPwmBoard1();

  pwm2.begin();          // 内部同样 setPWMFreq(60)



  Serial.println(F("Small Servos Test (1-30)"));

  Serial.println(F("Sequence: 10 -> 90 -> 170 -> 0 deg"));

  delay(1000);



  moveAll(0);

  delay(PAUSE_MS);

}



void loop() {

  moveAll(10);

  delay(MOVE_DELAY_MS);



  moveAll(90);

  delay(MOVE_DELAY_MS);



  moveAll(170);

  delay(MOVE_DELAY_MS);



  moveAll(0);

  delay(MOVE_DELAY_MS);



  Serial.println(F("--- cycle ---"));

  delay(PAUSE_MS);

}


