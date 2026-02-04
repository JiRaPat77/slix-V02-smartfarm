# from Modbus_485 import Modbus_Film69

# class SensorUltrasonic:
#     def __init__(self, port="/dev/ttyS2", slave_address=38, baudrate=9600):
#         self.slave_address = slave_address
#         self.modbus = Modbus_Film69(port=port, slaveaddress=slave_address, baudrate=baudrate)

#     def read_distance(self, addr=None):
#         try:
#             address = addr if addr is not None else self.slave_address

#             command = f"{address:02X} 03 00 00 00 01"
#             response, _ = self.modbus.send(command, resopne_len=7, ID=address)
#             parts = response.split()

#             if len(parts) < 7:
#                 raise ValueError("Invalid response length")

#             value = int(parts[3] + parts[4], 16)
#             return {"distance_cm": value,
#                     "response" : parts
#                     }

#         except Exception as e:
#             print(f"Read failed: {e}")
#             return None

#     def close(self):
#         self.modbus.close()

# if __name__ == "__main__":

#     sensor = SensorUltrasonic("/dev/ttyS2", slave_address=38, baudrate=9600)
#     data = sensor.read_distance()
#     if data:
#         print(f"Ultrasonic Distance: {data} cm")
#     else:
#         print("Unable to read distance.")
#     sensor.close()



# from Modbus_485 import Modbus_Film69


# class SensorUltrasonic:
#     def __init__(self, port="/dev/ttyS2", slave_address=26, baudrate=2400):
#         self.slave_address = slave_address
#         self.modbus = Modbus_Film69(port=port, slaveaddress=slave_address, baudrate=baudrate)


#     def read_distance(self, addr=None):
#         try:
#             address = addr if addr is not None else self.slave_address
#             # คำสั่ง Modbus RTU: [address] 03 00 00 00 01
#             command = f"{address:02X} 03 00 00 00 01"
#             response, _ = self.modbus.send(command, resopne_len=7, ID=address)
#             print("Command:", command)
#             parts = response.split()
#             print("RX:", parts)
#             if len(parts) < 7:
#                 raise ValueError("Invalid response length")
#             # parts: [address, funccode, length, ValHi, ValLo, crcL, crcH]
#             #value = int(parts[3] + parts[4], 16)
#             value = (int(parts[3], 16) << 8) + int(parts[4], 16)
#             print("Value",value)
#             return {"distance_cm": value}
#         except Exception as e:
#             print(f"Read failed: {e}")
#             return None


#     def close(self):
#         self.modbus.close()


# if __name__ == "__main__":
#     sensor = SensorUltrasonic("/dev/ttyS2", slave_address=26, baudrate=9600)
#     data = sensor.read_distance()
#     if data:
#         print(f"Ultrasonic Distance: {data['distance_cm']} cm")
#     else:
#         print("Unable to read distance.")
#     sensor.close()  
         



# import serial

# def modbus_crc(buf):
#     crc = 0xFFFF
#     for b in buf:
#         crc ^= b
#         for _ in range(8):
#             if crc & 1:
#                 crc = (crc >> 1) ^ 0xa001
#             else:
#                 crc >>= 1
#     return crc

# ser = serial.Serial("/dev/ttyS2", 9600, timeout=1)
# cmd = [0x1A, 0x03, 0x00, 0x00, 0x00, 0x01]
# crc = modbus_crc(cmd)
# cmd += [crc & 0xFF, (crc >> 8) & 0xFF]
# print("TX:", [hex(b) for b in cmd])
# ser.write(bytearray(cmd))
# ser.flush()
# rx = ser.read(7)
# print("RX:", list(rx))


# import serial
# import time

# def modbus_crc(buf):
#     crc = 0xFFFF
#     for b in buf:
#         crc ^= b
#         for _ in range(8):
#             if crc & 1:
#                 crc = (crc >> 1) ^ 0xA001
#             else:
#                 crc >>= 1
#     return crc

# def read_ultrasonic(port="/dev/ttyS2", slave_addr=0x1A, timeout=1.0):
#     # สร้าง Modbus RTU query [addr][03][00][00][00][01][crc_l][crc_h]
#     cmd = [slave_addr, 0x03, 0x00, 0x00, 0x00, 0x01]
#     crc = modbus_crc(cmd)
#     cmd.append(crc & 0xFF)          # CRC Low
#     cmd.append((crc >> 8) & 0xFF)   # CRC High

#     print("TX:", [hex(c) for c in cmd])

#     ser = serial.Serial(port, baudrate=4800, bytesize=8, parity="N", stopbits=1, timeout=timeout)
#     ser.reset_input_buffer()
#     ser.write(bytearray(cmd))
#     ser.flush()

#     # รอรับ response 7 bytes
#     resp = ser.read(7)
#     print("RX RAW:", list(resp))
#     if len(resp) != 7:
#         print("Response incomplete")
#         ser.close()
#         return None

#     # ถอด response [addr, func, 2, hi, lo, crc_l, crc_h]
#     addr, func, bytecount, hi, lo, crc_l, crc_h = resp
#     # CRC check
#     resp_frame = [addr, func, bytecount, hi, lo]
#     crc_calc = modbus_crc(resp_frame)
#     if (crc_l != (crc_calc & 0xFF)) or (crc_h != ((crc_calc >> 8)&0xFF)):
#         print(f"CRC error! In resp: {crc_l:02X} {crc_h:02X}, calc: {crc_calc & 0xFF:02X} {(crc_calc >> 8) & 0xFF:02X}")
#         ser.close()
#         return None
#     # ดึงค่าระยะ
#     value = (hi << 8) | lo
#     print(f"Ultrasonic distance_cm = {value}")
#     ser.close()
#     return value

# if __name__ == "__main__":
#     value = read_ultrasonic("/dev/ttyS2", slave_addr=0x1A)
#     if value is not None:
#         print(f"Ultrasonic: {value} cm")
#     else:
#         print("Failed to read ultrasonic")



import serial
import time

def modbus_crc(buf):
    crc = 0xFFFF
    for b in buf:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def read_ultrasonic_loop(port="/dev/ttyS2", slave_addr=0x4C, timeout=1.0, delay_between=0.5, max_attempts=50):
    ser = serial.Serial(port, baudrate=4800, bytesize=8, parity="N", stopbits=1, timeout=timeout)
    cmd = [slave_addr, 0x03, 0x00, 0x00, 0x00, 0x01]
    crc = modbus_crc(cmd)
    cmd.append(crc & 0xFF)         # CRC Low
    cmd.append((crc >> 8) & 0xFF)  # CRC High

    print("TX CMD:", [hex(c) for c in cmd])

    value = None
    attempt = 0
    while value is None and attempt < max_attempts:
        attempt += 1
        ser.reset_input_buffer()
        ser.write(bytearray(cmd))
        ser.flush()

        resp = ser.read(7)
        print(f"[{attempt}] RX RAW:", list(resp))
        if len(resp) != 7:
            print("Response incomplete")
            time.sleep(delay_between)
            continue

     
        addr, func, bytecount, hi, lo, crc_l, crc_h = resp
        resp_frame = [addr, func, bytecount, hi, lo]
        crc_calc = modbus_crc(resp_frame)
        if (crc_l != (crc_calc & 0xFF)) or (crc_h != ((crc_calc >> 8) & 0xFF)):
            print(f"CRC error! In resp: {crc_l:02X} {crc_h:02X}, calc: {crc_calc & 0xFF:02X} {(crc_calc >> 8) & 0xFF:02X}")
            time.sleep(delay_between)
            continue

        value = (hi << 8) | lo
        print(f"Ultrasonic distance_cm = {value}")
        break 
    else:
        print("Failed to read ultrasonic (retries exceeded)")
        value = None

    ser.close()
    return value

if __name__ == "__main__":
    value = read_ultrasonic_loop("/dev/ttyS2", slave_addr=0x4C)
    if value is not None:
        print(f"Ultrasonic: {value} cm")
    else:
        print("Failed to read ultrasonic sensor")


