from class_RKL01 import SensorWaterLevelRKL01 


sensor = SensorWaterLevelRKL01(port="/dev/ttyS4", slave_address=0x25)

#read value
level_data = sensor.read_level()
if level_data["success"]:
    # print(f"Water level: {level_data['water_level']:.2f}m")
    print(level_data)

#Chance address
# sensor.set_address(0x25)   # 37-48 (0x25-0x30)

#scan address
# found = SensorWaterLevelRKL01.scan_addresses()
