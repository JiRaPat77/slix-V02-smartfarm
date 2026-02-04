#Test Read ADS1115 Port A0 

# from smbus2 import SMBus
# import time

# ADS1115_ADDRESS = 0x48
# ADS1115_POINTER_CONVERT = 0x00
# ADS1115_POINTER_CONFIG = 0x01
# ADS1115_CONFIG_SINGLE_0 = 0xC183  # AIN0, 4.096V, single-shot

# bus = SMBus(3)

# while True:
#     bus.write_i2c_block_data(ADS1115_ADDRESS, ADS1115_POINTER_CONFIG, [(ADS1115_CONFIG_SINGLE_0 >> 8) & 0xFF, ADS1115_CONFIG_SINGLE_0 & 0xFF])
#     time.sleep(0.1)
    
#     data = bus.read_i2c_block_data(ADS1115_ADDRESS, ADS1115_POINTER_CONVERT, 2)
#     value = (data[0] << 8) | data[1]
#     if value > 32767:
#         value -= 65535
#     voltage = value * 4.096 / 32768.0
#     print(f"Voltage A0: {voltage:.4f} V")
#     time.sleep(1)


#Test ADS1115 Read&Save Value Port A0

import time
import csv
from datetime import datetime, timezone, timedelta
from smbus2 import SMBus

# -----------------------------
# ตั้งค่าพื้นฐาน
# -----------------------------
I2C_BUS = 3        # ใช้ I2C ช่อง 3 (ตามที่คุณบอกว่า M1)
ADS1115_ADDR = 0x48
CSV_FILE = "/root/ads1115_external_data.csv"  # path ที่บันทึกไฟล์ (แก้ได้ตามต้องการ)

# -----------------------------
# ฟังก์ชันอ่านค่า ADS1115
# -----------------------------
def read_ads1115_channel0(bus):
    CONFIG_REG = 0x01
    CONVERSION_REG = 0x00

    # ตั้งค่า configuration สำหรับช่อง A0
    config = 0x4000  # AIN0 vs GND
    config |= 0x8000  # Start single conversion
    config |= 0x0183  # ±4.096V, single-shot, 128SPS

    # เขียนค่าลง register config
    bus.write_i2c_block_data(ADS1115_ADDR, CONFIG_REG, [(config >> 8) & 0xFF, config & 0xFF])
    time.sleep(0.2)  # รอให้แปลงเสร็จ

    # อ่านค่าผลลัพธ์ 2 bytes
    data = bus.read_i2c_block_data(ADS1115_ADDR, CONVERSION_REG, 2)
    raw_adc = (data[0] << 8) | data[1]

    # แปลง signed 16-bit
    if raw_adc > 0x7FFF:
        raw_adc -= 0x10000

    # แปลงเป็นโวลต์ (±4.096V => 1bit = 4.096/32768)
    voltage = raw_adc * 4.096 / 32768.0
    return voltage

# -----------------------------
# ฟังก์ชันบันทึกค่า CSV
# -----------------------------
def log_to_csv(voltage):
    th_tz = timezone(timedelta(hours=7))  # เวลาประเทศไทย
    now = datetime.now(th_tz).strftime("%Y-%m-%d %H:%M:%S")

    with open(CSV_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([now, f"{voltage:.4f}"])

    print(f"[{now}] Voltage (A0): {voltage:.4f} V")

# -----------------------------
# Main Loop
# -----------------------------
if __name__ == "__main__":
    print("Starting ADS1115 A0 reading...")
    bus = SMBus(I2C_BUS)

    # เขียน header ถ้าไฟล์ยังไม่มี
    try:
        with open(CSV_FILE, "x", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp (TH)", "Voltage (A0)"])
    except FileExistsError:
        pass

    try:
        while True:
            voltage = read_ads1115_channel0(bus)
            log_to_csv(voltage)
            time.sleep(60)  # อ่านทุก 2 วินาที
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        bus.close()
