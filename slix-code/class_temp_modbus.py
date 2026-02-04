import serial
import time
import struct

class SensorAirTempHumidityRS30:
    """
    Class สำหรับ Sensor ATO Waterproof Temp & Humidity (SN-3000-WS-N01)
    Reference: ATO-Waterproof-Temperature-Humidity-Sensor-Probe-Manual
    """
    def __init__(self, port="/dev/ttyS2", slave_address=1, baudrate=9600, timeout=1.0):
        self.port = port
        self.slave_address = slave_address
        self.baudrate = baudrate
        self.timeout = timeout
        
        # Mapping ค่า Baudrate ตามคู่มือ 
        self.BAUD_MAP = {
            2400: 0, 4800: 1, 9600: 2, 
            19200: 3, 38400: 4, 57600: 5, 115200: 6
        }
        # สร้าง Map กลับสำหรับอ่านค่า
        self.BAUD_MAP_REVERSE = {v: k for k, v in self.BAUD_MAP.items()}

    @staticmethod
    def modbus_crc(data):
        """คำนวณ CRC16 ตามมาตรฐาน Modbus"""
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if (crc & 1) != 0:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    def _send_command(self, address, function_code, start_reg, data_val):
        """ส่งคำสั่ง Modbus พื้นฐาน"""
        try:
            ser = serial.Serial(
                port=self.port, 
                baudrate=self.baudrate, 
                bytesize=8, 
                parity='N', 
                stopbits=1, 
                timeout=self.timeout
            )
            
            # สร้าง Command Frame [Addr, Func, RegH, RegL, DataH, DataL, CRCL, CRCH]
            cmd = [address, function_code, (start_reg >> 8) & 0xFF, start_reg & 0xFF, (data_val >> 8) & 0xFF, data_val & 0xFF]
            crc = self.modbus_crc(cmd)
            cmd.append(crc & 0xFF)
            cmd.append((crc >> 8) & 0xFF)
            
            # ส่งข้อมูล
            # print(f"TX: {[hex(x) for x in cmd]}") # Debug
            ser.reset_input_buffer()
            ser.write(bytearray(cmd))
            
            # รอรับข้อมูล (Response ความยาวขึ้นอยู่กับ Function)
            # F03 (Read) = Addr(1) + Func(1) + Len(1) + Data(N) + CRC(2)
            # F06 (Write) = Addr(1) + Func(1) + Reg(2) + Val(2) + CRC(2) = 8 Bytes
            
            time.sleep(0.1) # รอ Processing time ของ Sensor [cite: 23]
            response = ser.read(128) # อ่านเข้ามาก่อน
            ser.close()
            
            if len(response) < 5:
                return None, "No response or incomplete"
                
            # ตรวจสอบ CRC ตอบกลับ
            resp_list = list(response)
            # print(f"RX: {[hex(x) for x in resp_list]}") # Debug
            
            msg_crc = (resp_list[-1] << 8) | resp_list[-2]
            calc_crc = self.modbus_crc(resp_list[:-2])
            
            if msg_crc != calc_crc:
                return None, f"CRC Error (Exp: {hex(calc_crc)}, Got: {hex(msg_crc)})"
                
            return resp_list, None
            
        except Exception as e:
            return None, f"Serial Error: {e}"

    def read_temp(self):
        """
        อ่านค่าอุณหภูมิและความชื้น (เพื่อให้เข้ากับ code เดิมใน test_main04)
        Register: 0x0000 (Hum), 0x0001 (Temp) 
        """
        # อ่าน 2 Registers เริ่มที่ 0x0000
        resp, err = self._send_command(self.slave_address, 0x03, 0x0000, 0x0002)
        
        if err or not resp:
            print(f"Read Error: {err}")
            return None
            
        try:
            # Response: [Addr, 03, Bytes, HumH, HumL, TempH, TempL, CRCL, CRCH]
            if len(resp) < 9: return None
            
            # Humidity (0x0000)
            hum_raw = (resp[3] << 8) | resp[4]
            humidity = hum_raw / 10.0
            
            # Temperature (0x0001) - Signed Value! [cite: 198]
            temp_raw = (resp[5] << 8) | resp[6]
            if temp_raw >= 0x8000:
                temp_raw -= 0x10000 # แปลง Two's complement
            temperature = temp_raw / 10.0
            
            return {
                "temperature": round(temperature, 1),
                "humidity": round(humidity, 1)
            }
        except Exception as e:
            print(f"Parse Error: {e}")
            return None

    # --- 1. เช็ค Address ของ Sensor (Check Address) ---
    def check_address(self):
        """
        ใช้ Broadcast Address (0xFF) เพื่อถามหา ID ของ Sensor ที่ต่ออยู่
        หมายเหตุ: ควรต่อ Sensor ตัวเดียวในระบบขณะใช้คำสั่งนี้
        
        """
        # ใช้ Address 0xFF ในการส่งคำสั่งอ่านที่ Register 0x07D0
        resp, err = self._send_command(0xFF, 0x03, 0x07D0, 0x0001)
        
        if err:
            print(f"Check Address Failed: {err}")
            return None
            
        # Response: [Addr(Actual), 03, 02, AddrH, AddrL, CRC...]
        # ตำแหน่งที่ 3 คือ AddrH (0x00), ตำแหน่งที่ 4 คือ AddrL (ID)
        found_address = (resp[3] << 8) | resp[4]
        return found_address

    # --- 2. เปลี่ยน Address ของ Sensor (Change Address) ---
    def set_address(self, new_address):
        """
        เปลี่ยน Address ของ Sensor ไปเป็นค่าใหม่
        Register: 0x07D0 [cite: 222]
        """
        if not (1 <= new_address <= 247):
            print("Error: Address must be 1-247")
            return False
            
        print(f"Changing Address from {self.slave_address} to {new_address}...")
        resp, err = self._send_command(self.slave_address, 0x06, 0x07D0, new_address)
        
        if err:
            print(f"Set Address Failed: {err}")
            return False
            
        # ตรวจสอบว่าเปลี่ยนสำเร็จ (Response ของ Write คือการ Echo คำสั่งกลับมา)
        if resp[4] == (new_address >> 8) & 0xFF and resp[5] == new_address & 0xFF:
            self.slave_address = new_address # อัพเดทค่าใน Class
            print(f"✅ Address changed to {new_address}")
            return True
        return False

    # --- 3. Reset กลับค่าเริ่มต้น (Reset to Factory) ---
    def reset_to_default(self):
        """
        ตั้งค่า Address กลับเป็น 1 และ Baudrate เป็น 4800
        [cite: 102] Default Address=1, Baud=4800
        """
        print("🔄 Resetting to Factory Defaults...")
        
        # 1. Reset Address -> 1
        success_addr = self.set_address(1)
        
        # 2. Reset Baudrate -> 4800 (Value = 1)
        # หมายเหตุ: ต้องใช้ Address ใหม่ (1) ในการส่งคำสั่งถัดไป
        original_addr = self.slave_address
        self.slave_address = 1 
        
        # Register 0x07D1, Value 1 = 4800bps 
        resp, err = self._send_command(self.slave_address, 0x06, 0x07D1, 1)
        
        if err:
            print(f"Reset Baudrate Failed: {err}")
            self.slave_address = original_addr # Revert if failed
            return False
            
        if resp[5] == 1:
            self.baudrate = 4800
            print("✅ Baudrate reset to 4800")
            print("🎉 Factory Reset Complete (Addr: 1, Baud: 4800)")
            return True
            
        return False

    def calibrate(self, temp_offset=0.0, hum_offset=0.0):
        """
        ตั้งค่า Calibration (Offset)
        Reg 0x0050: Temp Offset
        Reg 0x0051: Hum Offset
        
        """
        # Convert to int16 format (x10)
        t_val = int(temp_offset * 10)
        h_val = int(hum_offset * 10)
        
        # Handle Negative Values (Two's complement)
        if t_val < 0: t_val += 0x10000
        if h_val < 0: h_val += 0x10000
        
        # Send Temp Calibration
        self._send_command(self.slave_address, 0x06, 0x0050, t_val)
        # Send Hum Calibration
        self._send_command(self.slave_address, 0x06, 0x0051, h_val)
        print(f"Calibrated: Temp {temp_offset}, Hum {hum_offset}")