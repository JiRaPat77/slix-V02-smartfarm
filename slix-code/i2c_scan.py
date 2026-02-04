# -*- coding: utf-8 -*-
import smbus
import time

def scan_i2c(bus_num=3):
    found_devices = []
    bus = smbus.SMBus(bus_num)
    
    print(f"Scanning I2C bus {bus_num} for devices...")
    for address in range(0x03, 0x77):
        try:
            bus.write_quick(address)
            found_devices.append(address)
            print(f"Found device at 0x{address:02X}")
        except OSError:
            pass 
    bus.close()
    
    if not found_devices:
        print("No I2C devices found.")
    return found_devices

# Example usage
devices = scan_i2c()