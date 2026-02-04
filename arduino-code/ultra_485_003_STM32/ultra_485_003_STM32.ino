#include <SoftwareSerial.h>
#include <EEPROM.h>

#define RS485_RX PA3
#define RS485_TX PA2
#define PING_PIN PB5
#define ECHO_PIN PB6

#define DEFAULT_DEVICE_ID 0x4C  // Address เริ่มต้น
#define FUNC_READHR  0x03
#define FUNC_WRITESINGLE 0x06   // ฟังก์ชันเขียน single register
#define PACKET_LENGTH 8
#define RESPONSE_LENGTH 7
#define RX_TIMEOUT 200

// EEPROM addresses
#define EEPROM_ADDR_DEVICE_ID 0
#define EEPROM_MAGIC_ADDR 1
#define EEPROM_MAGIC_VALUE 0xCD  // ค่าเช็คว่ามี address ที่บันทึกไว้

SoftwareSerial rs485Serial(RS485_RX, RS485_TX);

byte rxBuf[16];  // เพิ่มขนาดรองรับ packet ที่ยาวขึ้น
int rxIndex = 0;
unsigned long lastRxMillis = 0;

byte DEVICE_ID = DEFAULT_DEVICE_ID;  // เปลี่ยนเป็น variable

// Special registers
#define REG_DISTANCE 0x0000       // Register สำหรับอ่านค่าระดับน้ำ
#define REG_DEVICE_ADDR 0x0100    // Register สำหรับเช็ค/เปลี่ยน address
#define REG_RESET_ADDR 0x0200     // Register สำหรับ reset address

// === Modbus CRC ===
unsigned int modbusCRC(byte *buf, int len) {
  unsigned int crc = 0xFFFF;
  for (int pos = 0; pos < len; pos++) {
    crc ^= (unsigned int)buf[pos];
    for (int i = 8; i != 0; i--) {
      if ((crc & 0x0001) != 0) {
        crc >>= 1;
        crc ^= 0xA001;
      } else {
        crc >>= 1;
      }
    }
  }
  return crc;
}

void printHexPacket(byte *data, int len) {
  for (int i = 0; i < len; i++) {
    if (data[i] < 0x10) Serial.print("0");
    Serial.print(data[i], HEX); Serial.print(" ");
  }
  Serial.println();
}

// บันทึก Device ID ลง EEPROM
void saveDeviceID(byte newID) {
  EEPROM.write(EEPROM_ADDR_DEVICE_ID, newID);
  EEPROM.write(EEPROM_MAGIC_ADDR, EEPROM_MAGIC_VALUE);
  Serial.print("Saved new Device ID to EEPROM: 0x");
  Serial.println(newID, HEX);
}

// โหลด Device ID จาก EEPROM
void loadDeviceID() {
  byte magic = EEPROM.read(EEPROM_MAGIC_ADDR);
  if (magic == EEPROM_MAGIC_VALUE) {
    DEVICE_ID = EEPROM.read(EEPROM_ADDR_DEVICE_ID);
    Serial.print("Loaded Device ID from EEPROM: 0x");
    Serial.println(DEVICE_ID, HEX);
  } else {
    DEVICE_ID = DEFAULT_DEVICE_ID;
    Serial.println("No saved ID, using default: 0x4C");
  }
}

// Reset Device ID กลับเป็นค่าเริ่มต้น
void resetDeviceID() {
  DEVICE_ID = DEFAULT_DEVICE_ID;
  EEPROM.write(EEPROM_MAGIC_ADDR, 0x00);  // ลบ magic value
  Serial.println("Device ID reset to default: 0x4C");
}

// วัดระยะทาง Ultrasonic
unsigned int measureDistance() {
  digitalWrite(PING_PIN, LOW); 
  delayMicroseconds(2);
  digitalWrite(PING_PIN, HIGH); 
  delayMicroseconds(10);
  digitalWrite(PING_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // max wait 30ms
  unsigned int distance_cm = (duration > 0) ? duration / 29 / 2 : 0;
  
  return distance_cm;
}

void handleModbusRequest() {
  if (rxIndex < PACKET_LENGTH) return;
  
  Serial.print("Recv FRAME: "); printHexPacket(rxBuf, rxIndex);

  byte addr = rxBuf[0];
  byte func = rxBuf[1];
  
  // ตรวจสอบว่าเป็น broadcast (0x00) หรือ address ตัวเองหรือไม่
  if (addr != DEVICE_ID && addr != 0x00) {
    Serial.println("Not for this device");
    rxIndex = 0;
    return;
  }

  // ตรวจสอบ CRC
  int crcPos = rxIndex - 2;
  unsigned int crc_calc = modbusCRC(rxBuf, crcPos);
  unsigned int crc_recv = rxBuf[crcPos] | (rxBuf[crcPos + 1] << 8);

  Serial.print("CRC check: recv=0x");
  Serial.print(crc_recv, HEX);
  Serial.print(" calc=0x");
  Serial.println(crc_calc, HEX);

  if (crc_recv != crc_calc) {
    Serial.println("CRC mismatch, ignore.");
    rxIndex = 0;
    return;
  }

  // ========== Function 0x03: Read Holding Register ==========
  if (func == FUNC_READHR && rxIndex == 8) {
    byte reg_hi = rxBuf[2];
    byte reg_lo = rxBuf[3];
    byte len_hi = rxBuf[4];
    byte len_lo = rxBuf[5];
    unsigned int regAddr = (reg_hi << 8) | reg_lo;
    unsigned int qty = (len_hi << 8) | len_lo;

    // อ่านค่าระดับน้ำ (Register 0x0000)
    if (regAddr == REG_DISTANCE && qty == 1) {
      unsigned int distance_cm = measureDistance();
      
      byte response[RESPONSE_LENGTH];
      response[0] = DEVICE_ID;
      response[1] = FUNC_READHR;
      response[2] = 2;
      response[3] = highByte(distance_cm);
      response[4] = lowByte(distance_cm);
      unsigned int crc_resp = modbusCRC(response, 5);
      response[5] = lowByte(crc_resp);
      response[6] = highByte(crc_resp);

      Serial.print("RESP Distance: ");
      Serial.print(distance_cm);
      Serial.println(" cm");
      printHexPacket(response, RESPONSE_LENGTH);
      
      for (int i = 0; i < RESPONSE_LENGTH; i++) rs485Serial.write(response[i]);
      rs485Serial.flush();
    }
    // เช็ค Address ปัจจุบัน (Register 0x0100)
    else if (regAddr == REG_DEVICE_ADDR && qty == 1) {
      byte response[RESPONSE_LENGTH];
      response[0] = DEVICE_ID;
      response[1] = FUNC_READHR;
      response[2] = 2;
      response[3] = 0x00;
      response[4] = DEVICE_ID;
      unsigned int crc_resp = modbusCRC(response, 5);
      response[5] = lowByte(crc_resp);
      response[6] = highByte(crc_resp);

      Serial.print("RESP Current Address: 0x");
      Serial.println(DEVICE_ID, HEX);
      printHexPacket(response, RESPONSE_LENGTH);
      
      for (int i = 0; i < RESPONSE_LENGTH; i++) rs485Serial.write(response[i]);
      rs485Serial.flush();
    }
  }
  
  // ========== Function 0x06: Write Single Register ==========
  else if (func == FUNC_WRITESINGLE && rxIndex == 8) {
    byte reg_hi = rxBuf[2];
    byte reg_lo = rxBuf[3];
    byte val_hi = rxBuf[4];
    byte val_lo = rxBuf[5];
    unsigned int regAddr = (reg_hi << 8) | reg_lo;
    byte newAddr = val_lo;

    // เปลี่ยน Address (Register 0x0100)
    if (regAddr == REG_DEVICE_ADDR && newAddr >= 0x01 && newAddr <= 0xF7) {
      Serial.print("Changing address from 0x");
      Serial.print(DEVICE_ID, HEX);
      Serial.print(" to 0x");
      Serial.println(newAddr, HEX);

      // ส่ง response ด้วย address เดิมก่อน
      byte response[8];
      for (int i = 0; i < 8; i++) response[i] = rxBuf[i];
      
      Serial.print("RESP Address Change: "); printHexPacket(response, 8);
      for (int i = 0; i < 8; i++) rs485Serial.write(response[i]);
      rs485Serial.flush();

      // เปลี่ยน address
      DEVICE_ID = newAddr;
      saveDeviceID(DEVICE_ID);
    }
    // Reset Address (Register 0x0200)
    else if (regAddr == REG_RESET_ADDR) {
      Serial.println("Reset address command received");
      
      // ส่ง response ก่อน reset
      byte response[8];
      for (int i = 0; i < 8; i++) response[i] = rxBuf[i];
      response[4] = 0x00;
      response[5] = DEFAULT_DEVICE_ID;
      unsigned int crc_resp = modbusCRC(response, 6);
      response[6] = lowByte(crc_resp);
      response[7] = highByte(crc_resp);
      
      Serial.print("RESP Reset Address: "); printHexPacket(response, 8);
      for (int i = 0; i < 8; i++) rs485Serial.write(response[i]);
      rs485Serial.flush();

      delay(100);  // รอส่ง response เสร็จ
      resetDeviceID();
    }
  }

  rxIndex = 0;
}

void setup() {
  Serial.begin(115200);
  rs485Serial.begin(9600);
  pinMode(PING_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  
  loadDeviceID();  // โหลด address ที่บันทึกไว้
  
  Serial.println("Ultrasonic Modbus RS485 slave with Address Management");
  Serial.print("Current Device ID: 0x");
  Serial.println(DEVICE_ID, HEX);
}

void loop() {
  // Log status ทุก 5 วินาที
  static unsigned long lastLog = 0;
  if (millis() - lastLog >= 5000) {
    lastLog = millis();
    Serial.print("Device ID: 0x");
    Serial.print(DEVICE_ID, HEX);
    Serial.print(" | Distance: ");
    Serial.print(measureDistance());
    Serial.println(" cm");
  }

  // === RS485 receive and frame processing ===
  while (rs485Serial.available() > 0) {
    byte incoming = rs485Serial.read();
    unsigned long tNow = millis();

    // timeout protection
    if (rxIndex > 0 && (tNow - lastRxMillis > RX_TIMEOUT)) {
      Serial.println("TIMEOUT (reset rxIndex)");
      rxIndex = 0;
    }
    lastRxMillis = tNow;

    // sync: first byte must be DEVICE_ID or broadcast (0x00)
    if (rxIndex == 0 && incoming != DEVICE_ID && incoming != 0x00) continue;

    rxBuf[rxIndex++] = incoming;

    // จำกัดขนาด buffer
    if (rxIndex >= sizeof(rxBuf)) {
      Serial.println("Buffer overflow, reset");
      rxIndex = 0;
      continue;
    }

    // ตรวจสอบ packet ตาม function code
    if (rxIndex >= 2) {
      byte func = rxBuf[1];
      // Function 0x03 และ 0x06 ใช้ 8 bytes
      if ((func == FUNC_READHR || func == FUNC_WRITESINGLE) && rxIndex == 8) {
        handleModbusRequest();
      }
    }
  }

  // Reset frame buffer if timeout occurs
  if (rxIndex > 0 && (millis() - lastRxMillis > RX_TIMEOUT)) {
    Serial.println("FRAME TIMEOUT: reset rxIndex");
    rxIndex = 0;
  }
}
