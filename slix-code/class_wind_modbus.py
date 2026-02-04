from Modbus_485 import Modbus_Film69

class SensorWindSpeedDirection:
    def __init__(self, port="/dev/ttyS2", slave_address=1, baudrate=9600):
        self.slave_address = slave_address
        self.modbus = Modbus_Film69(port=port, slaveaddress=slave_address, baudrate=baudrate)

    def read_wind(self, addr=None):
        """
        อ่านค่าความเร็วลมและทิศทางลม
        Command: 01 03 00 00 00 02
        Response: 01 03 04 [speed_H][speed_L] [dir_H][dir_L] CRC
        Wind Speed: (value / 10) m/s
        Wind Direction: degrees (0-359°)
        """
        try:
            address = addr if addr is not None else self.slave_address
            cmd = f"{address:02X} 03 00 00 00 02"
            response, _ = self.modbus.send(cmd, resopne_len=9, ID=address)
            parts = response.split()
            if len(parts) < 9:
                raise ValueError("Invalid response")

            speed_raw = int(parts[3] + parts[4], 16)
            direction_raw = int(parts[5] + parts[6], 16)

            return {
                "wind_speed": round(speed_raw / 10.0, 1),   # m/s
                "wind_direction": direction_raw,             # degree
                "Respond": parts
            }
        except Exception as e:
            print(f"Read failed: {e}")
            return None

    def set_address(self, new_address):
        """
        เปลี่ยน slave address (ใช้ Function 06, address register: 0x0020)
        คำสั่ง: [old_addr] 06 00 20 00 [new_addr]
        """
        if not (0x00 <= new_address <= 0xFF):
            raise ValueError("Address must be between 0x00 and 0xFF")

        cmd = f"{self.slave_address:02X} 06 00 20 00 {new_address:02X}"
        try:
            response, _ = self.modbus.send(cmd, resopne_len=8, ID=self.slave_address)
            print(f"Set address response: {response}")
        except Exception as e:
            print(f"Set address failed: {e}")

    def close(self):
        self.modbus.close()
