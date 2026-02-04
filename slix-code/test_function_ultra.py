#!/usr/bin/env python3
from class_ultra_modbus import UltrasonicModbus
import json

ultra_sensor = UltrasonicModbus(port="/dev/ttyS2", slave_address=0x4E, baudrate=9600)
data = ultra_sensor.read_distance()
print(json.dumps(data, indent=2, ensure_ascii=False))

# ตัวอย่างการใช้งานฟังก์ชันใหม่
# print("\n=== Check Current Address ===")
# addr_check = ultra_sensor.check_address()
# print(json.dumps(addr_check, indent=2, ensure_ascii=False))
    
# print("\n=== Change Address to 0x33 ===")
# change_result = ultra_sensor.change_address(0x4E)
# print(json.dumps(change_result, indent=2, ensure_ascii=False))
    
# # หลังเปลี่ยน address แล้ว ต้องใช้ address ใหม่
# if change_result.get("success"):
#     print("\n=== Check Address After Change ===")
#     addr_check2 = ultra_sensor.check_address()
#     print(json.dumps(addr_check2, indent=2, ensure_ascii=False))
    
# print("\n=== Reset Address to Default (0x32) ===")
# reset_result = ultra_sensor_sensor.reset_address()
# print(json.dumps(reset_result, indent=2, ensure_ascii=False))
    
# print("\n=== Check Address After Reset ===")
# addr_check3 = ultra_sensor.check_address()
# print(json.dumps(addr_check3, indent=2, ensure_ascii=False))
