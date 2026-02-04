#Soil RK520-01 check specifically address

# from class_soil_modbus import SensorSoilMoistureTemp
# addr = 0x02
# sensor = SensorSoilMoistureTemp("/dev/ttyS2", slave_address=addr)
# value= sensor.read_data(addr)
# print(f"Address: 0x{addr:02X} | {value}")

import time
from class_soil_modbus import SensorSoilMoistureTemp

addr = 0x02
sensor = SensorSoilMoistureTemp("/dev/ttyS2", slave_address=addr)

print("Starting sensor reading... Press Ctrl+C to stop")

try:
    while True:
        try:
            value = sensor.read_data(addr)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Address: 0x{addr:02X} | {value}")
        except Exception as e:
            print(f"Error reading data: {e}")
        
        time.sleep(5)  
        
except KeyboardInterrupt:
    print("\nStopping sensor reading...")





#Soil RK520-01 check respond ALL address

# from class_soil_modbus import SensorSoilMoistureTemp
# if __name__ == "__main__":


#     devices = SensorSoilMoistureTemp.scan_addresses("/dev/ttyS2")

#     all_data = []

#     for addr in devices:
#         sensor = SensorSoilMoistureTemp("/dev/ttyS2", slave_address=addr)
#         data = sensor.read_data()
#         sensor.close()

#         if data is not None:
#             entry = {
#                 "address": f"0x{addr:02X}",
#                 "temperature": data["temperature"],
#                 "moisture": data["moisture"]
#             }
#             all_data.append(entry)

#     import json
#     print(json.dumps(all_data, indent=2))


#Soil set address

# from class_soil_modbus import SensorSoilMoistureTemp
# import time

# if __name__ == "__main__":
#     # สมมุติว่า sensor ปัจจุบันอยู่ที่ address 0x01
#     current_addr = 0x03
#     new_addr = 0x01

#     # สร้าง instance
#     sensor = SensorSoilMoistureTemp("/dev/ttyS2", slave_address=current_addr)

#     # สั่งเปลี่ยน address
#     print(f"Setting sensor at address 0x{current_addr:02X} to new address 0x{new_addr:02X}")
#     sensor.set_address(new_addr)
#     sensor.close()

#     print("Please restart sensor before use new address")

#     # รอ 5 วินาทีเผื่อ sensor restart
#     time.sleep(5)

#     # ทดลองอ่านค่าจาก address ใหม่
#     sensor_new = SensorSoilMoistureTemp("/dev/ttyS2", slave_address=new_addr)
#     data = sensor_new.read_data()
#     sensor_new.close()

#     if data:
#         print(f"✅ Read from new address 0x{new_addr:02X}:")
#         print(f"Temperature: {data['temperature']} °C")
#         print(f"Moisture: {data['moisture']} %")
#     else:
#         print("❌ Failed to read from new address.")

