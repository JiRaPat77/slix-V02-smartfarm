#Wind RK210-01 check specifically address
from class_wind_modbus import SensorWindSpeedDirection
addr = 0x1A
sensor = SensorWindSpeedDirection("/dev/ttyS2", slave_address=addr)
value= sensor.read_wind(addr)
print(f"Address: 0x{addr:02X} | {value}")

#Wind sensor set address
# from class_wind_modbus import SensorWindSpeedDirection
# sensor = SensorWindSpeedDirection(port="/dev/ttyS2", slave_address=0x19)
# sensor.set_address(0x19)
# sensor.close()