/*
 * Photoresistor array serial reader — Arduino Mega
 * A0-A7: 8 analog inputs (2 per direction E/S/W/N; order is A0..A7)
 *
 * Protocol (115200 8N1):
 *   Host sends one-line command 'R' or 'r' (optional CR/LF)
 *   Board replies: v0,v1,v2,v3,v4,v5,v6,v7\n
 *   Values are raw analogRead 0-1023
 */

const unsigned long BAUD_RATE = 115200;

void setup() {
  Serial.begin(BAUD_RATE);
  analogReference(DEFAULT);
}

void flushLine() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r')
      break;
  }
}

void sendReading() {
  for (int i = 0; i < 8; i++) {
    if (i > 0)
      Serial.print(',');
    Serial.print(analogRead(A0 + i));
  }
  Serial.println();
}

void loop() {
  if (Serial.available() <= 0)
    return;

  char cmd = Serial.read();
  if (cmd == 'R' || cmd == 'r') {
    flushLine();
    sendReading();
    return;
  }
  // Skip unknown bytes until newline to avoid buffer pile-up
  if (cmd != '\n' && cmd != '\r')
    flushLine();
}
