/*
 * Arduino Uno — 数字引脚 0–8 直连舵机测试
 *
 * 动作：引脚 0→8 上的舵机依次转到 150°，每个停留 1 秒，再测下一个。
 *
 * 接线：各舵机信号线 → D0 … D8
 *       舵机电源用外部 5V，GND 与 Uno GND 共地（勿仅靠板载 5V）
 *
 * 注意：D0/D1 是串口 RX/TX。测试时请关闭串口监视器，
 *       否则可能干扰 0、1 号舵机。
 */

#include <Servo.h>

#define PIN_FIRST   0
#define PIN_LAST    8
#define TARGET_DEG  150
#define HOLD_MS     1000

Servo servos[9];  // index 0..8 对应引脚 0..8

void setup() {
  // 尽量少用 Serial，避免占用 D0/D1；需要调试时可临时打开
  // Serial.begin(115200);

  for (uint8_t pin = PIN_FIRST; pin <= PIN_LAST; pin++) {
    servos[pin].attach(pin);
    delay(50);
  }
  delay(300);

  for (uint8_t pin = PIN_FIRST; pin <= PIN_LAST; pin++) {
    servos[pin].write(TARGET_DEG);
    delay(HOLD_MS);
  }
}

void loop() {
  // hold
}
