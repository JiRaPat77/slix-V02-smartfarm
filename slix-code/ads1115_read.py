# -*- coding: utf-8 -*-

import smbus
import time

# Create I2C bus
bus = smbus.SMBus(3)  # Use 0 for older Raspberry Pi models

# ADS1115 I2C address
address = 0x49

# Configure ADS1115:
# - AIN0 vs GND
# - Gain = ±2.048V
# - Single-shot mode
# - 128 samples/sec
config = [0x84, 0x83]  # MSB, LSB for config register

# Write config to register 0x01
bus.write_i2c_block_data(address, 0x01, config)

# Wait for conversion
time.sleep(0.1)

# Read conversion result from register 0x00
data = bus.read_i2c_block_data(address, 0x00, 2)
raw_adc = data[0] << 8 | data[1]

# Convert to signed integer
if raw_adc > 32767:
    raw_adc -= 65536

print("ADC Value:", raw_adc)