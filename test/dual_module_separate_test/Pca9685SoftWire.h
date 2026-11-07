/*
 * PCA9685 over SoftwareWire — API 对齐 D2-4-4H / Adafruit：
 *   begin() → setPWMFreq(60) → setPWM(ch, 0, pulse)
 *
 * 用途：第二块模块与第一块同为 I2C 地址 0x40 时，走独立软件 I2C 总线。
 */
#ifndef PCA9685_SOFTWIRE_H
#define PCA9685_SOFTWIRE_H

#include <Arduino.h>
#include <SoftwareWire.h>

#define PCA9685_MODE1 0x00
#define PCA9685_PRESCALE 0xFE
#define PCA9685_LED0_ON_L 0x06
#define MODE1_RESTART 0x80
#define MODE1_SLEEP 0x10
#define MODE1_AI 0x20
#define PCA9685_PRESCALE_MIN 3
#define PCA9685_PRESCALE_MAX 255

class Pca9685SoftWire {
public:
  Pca9685SoftWire(SoftwareWire &wire, uint8_t addr = 0x40)
      : _wire(wire), _addr(addr), _oscillator_freq(25000000) {}

  void begin() {
    reset();
    setPWMFreq(60);
  }

  void setPWMFreq(float freq) {
    if (freq < 1.0f) freq = 1.0f;
    if (freq > 3500.0f) freq = 3500.0f;

    float prescaleval = ((_oscillator_freq / (freq * 4096.0f)) + 0.5f) - 1.0f;
    if (prescaleval < PCA9685_PRESCALE_MIN) prescaleval = PCA9685_PRESCALE_MIN;
    if (prescaleval > PCA9685_PRESCALE_MAX) prescaleval = PCA9685_PRESCALE_MAX;
    uint8_t prescale = (uint8_t)prescaleval;

    uint8_t oldmode = read8(PCA9685_MODE1);
    uint8_t newmode = (oldmode & ~MODE1_RESTART) | MODE1_SLEEP;
    write8(PCA9685_MODE1, newmode);
    write8(PCA9685_PRESCALE, prescale);
    write8(PCA9685_MODE1, oldmode);
    delay(5);
    write8(PCA9685_MODE1, oldmode | MODE1_RESTART | MODE1_AI);
  }

  void setPWM(uint8_t num, uint16_t on, uint16_t off) {
    uint8_t reg = PCA9685_LED0_ON_L + 4 * num;
    _wire.beginTransmission(_addr);
    _wire.write(reg);
    _wire.write(on & 0xFF);
    _wire.write(on >> 8);
    _wire.write(off & 0xFF);
    _wire.write(off >> 8);
    _wire.endTransmission();
  }

  void reset() {
    write8(PCA9685_MODE1, MODE1_RESTART);
    delay(10);
  }

private:
  SoftwareWire &_wire;
  uint8_t _addr;
  uint32_t _oscillator_freq;

  void write8(uint8_t reg, uint8_t data) {
    _wire.beginTransmission(_addr);
    _wire.write(reg);
    _wire.write(data);
    _wire.endTransmission();
  }

  uint8_t read8(uint8_t reg) {
    _wire.beginTransmission(_addr);
    _wire.write(reg);
    _wire.endTransmission(false);
    _wire.requestFrom((int)_addr, 1, true);
    if (_wire.available()) return _wire.read();
    return 0;
  }
};

#endif
