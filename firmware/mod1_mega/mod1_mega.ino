/*
 * SmartSunroom — 模块1 板（默认 COM8）
 *
 * 硬件：
 *   PCA9685 0x40：硬件 I2C SDA=20, SCL=21 → 小舵机 1–15
 *   通道映射：舵机 N → PCA 通道 N（1–15；通道 0 不用）
 *   大功率舵机：A1
 *
 * 串口 115200：
 *   PING                 → PONG
 *   SET,ns,a1,...,a15    → OK   （逐路间隔 SERVO_STEP_DELAY_MS，再回 OK）
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <Servo.h>

#define SERIAL_BAUD           115200
#define BIG_SERVO_PIN         A1
#define SERVOMIN              150
#define SERVOMAX              600
#define LOCAL_CNT             15
#define LINE_BUF_SIZE         128

// 逐路驱动间隔，避免同时抢电流 / 来不及转到位
#define SERVO_STEP_DELAY_MS   300
#define BIG_SERVO_SETTLE_MS   600
#define BATCH_SETTLE_MS       400

Adafruit_PWMServoDriver pwm(0x40, Wire);
Servo bigServo;

char lineBuf[LINE_BUF_SIZE];
uint8_t lineLen = 0;

int angleToPulse(int angle) {
  return map(constrain(angle, 0, 180), 0, 180, SERVOMIN, SERVOMAX);
}

void setLocalServo(uint8_t id, int angle) {
  if (id < 1 || id > LOCAL_CNT) return;
  pwm.setPWM(id, 0, angleToPulse(angle));
}

void setAllLocal(int angle, bool slow) {
  for (uint8_t i = 1; i <= LOCAL_CNT; i++) {
    setLocalServo(i, angle);
    if (slow) delay(SERVO_STEP_DELAY_MS);
  }
}

bool parseSet(const char *line, int *ns, int *angles) {
  if (strncmp(line, "SET,", 4) != 0) return false;
  const char *p = line + 4;
  char *end = NULL;
  *ns = (int)strtol(p, &end, 10);
  if (end == p || *end != ',') return false;
  p = end + 1;
  for (uint8_t i = 0; i < LOCAL_CNT; i++) {
    angles[i] = (int)strtol(p, &end, 10);
    if (end == p) return false;
    if (i < LOCAL_CNT - 1) {
      if (*end != ',') return false;
      p = end + 1;
    }
  }
  return true;
}

void handleLine(const char *line) {
  if (strcmp(line, "PING") == 0) {
    Serial.println(F("PONG"));
    return;
  }
  if (strncmp(line, "SET,", 4) == 0) {
    int ns = 110;
    int angles[LOCAL_CNT];
    if (!parseSet(line, &ns, angles)) {
      Serial.println(F("ERR,parse"));
      return;
    }

    // 先大舵机，留足时间
    bigServo.write(constrain(ns, 0, 180));
    delay(BIG_SERVO_SETTLE_MS);

    // 再逐路小舵机
    for (uint8_t i = 0; i < LOCAL_CNT; i++) {
      setLocalServo(i + 1, angles[i]);
      delay(SERVO_STEP_DELAY_MS);
    }
    delay(BATCH_SETTLE_MS);

    Serial.println(F("OK"));
    return;
  }
  Serial.println(F("ERR,unknown"));
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(60);
  bigServo.attach(BIG_SERVO_PIN);
  delay(500);
  // 上电快速归位，勿用长延时，否则上位机 PING 会超时
  bigServo.write(110);
  delay(300);
  setAllLocal(60, false);
  Serial.println(F("READY,MOD1"));
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      lineBuf[lineLen] = '\0';
      if (lineLen > 0) handleLine(lineBuf);
      lineLen = 0;
      continue;
    }
    if (lineLen < LINE_BUF_SIZE - 1) lineBuf[lineLen++] = c;
  }
}
