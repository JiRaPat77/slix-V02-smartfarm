#Pyranometer check specifically address and value
from class_solar_modbus import SensorPyranometer
addr = 0x0E
sensor = SensorPyranometer("/dev/ttyS2", slave_address=addr)
value= sensor.read_radiation(addr)
print(f"Address: 0x{addr:02X} | {value}")
current = sensor.read_current_address()
print(f"Current address: 0x{current:02X}")


#Pyranometer set address
# from class_solar_modbus import SensorPyranometer
# sensor = SensorPyranometer("/dev/ttyS2")
# sensor.set_address(0x0D)
# print("Success Set Address")