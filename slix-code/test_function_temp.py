#!/usr/bin/env python3
import time
from class_temp_modbus import SensorAirTempHumidityRS30

# =================ตั้งค่า=================
PORT = "/dev/ttyS2" 
ADDR = 0x0E        # Address ของ Sensor
BAUD = 9600     # Baudrate ของ Sensor
# ========================================

def main():
    print(f"--- Start Testing Sensor on {PORT} (Addr: {ADDR}) ---")
    
    # สร้าง Object Sensor
    sensor = SensorAirTempHumidityRS30(port=PORT, slave_address=ADDR, baudrate=BAUD)

    # 1. ทดสอบอ่านค่า (เปิดใช้งาน)
    try:
        print("Reading data...")
        data = sensor.read_temp()
        if data:
            print(f"✅ Read Success: Temp={data['temperature']}°C, Hum={data['humidity']}%")
        else:
            print("❌ Read Failed (No response)")
    except Exception as e:
        print(f"Error: {e}")

    # ================================================================
    # โซนฟังก์ชันพิเศษ (เอาคอมเมนต์ออกเมื่อต้องการใช้งาน)
    # ================================================================

    # --- A. เช็ค Address (ใช้กรณีลืม Address และต่อ Sensor ตัวเดียว) ---
    # real_addr = sensor.check_address()
    # if real_addr:
    #     print(f"🔍 Found Sensor Address: {real_addr}")

    # --- B. เปลี่ยน Address (เช่น จาก 1 -> 2) ---
    # NEW_ADDR = 0x0E
    # if sensor.set_address(NEW_ADDR):
    #     print(f"Address changed to {NEW_ADDR}")

    # --- C. รีเซ็ตค่าโรงงาน (Addr=1, Baud=4800) ---
    # sensor.reset_to_default()

if __name__ == "__main__":
    main()