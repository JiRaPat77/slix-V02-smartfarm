#!/usr/bin/env python
import sys
import os
import time
import threading

# Import MCP libraries
sys.path.append(os.path.dirname(__file__))
from mcp_1 import MCP23017 as MCP1  # Sensor 1-8
from mcp_2 import MCP23017 as MCP2  # Sensor 9-16
from mcp_3 import MCP23017 as MCP3  # Sensor check & system

class SensorControlSystem:
    def __init__(self):
        # Initialize MCPs (แยก try-except เพื่อให้ระบบไม่ล่มถ้าตัวใดตัวหนึ่งเสีย)
        print("Initializing MCP controllers...")
        
        self.mcp1 = None
        self.mcp2 = None
        self.mcp3 = None
        self.mcp1_ready = False
        self.mcp2_ready = False
        self.mcp3_ready = False

        # --- MCP 1 (Sensor 1-8) ---
        try:
            self.mcp1 = MCP1(bus=3, address=0x26)
            self.mcp1_ready = True
            print("✅ MCP1 (Sensor 1-8) initialized.")
        except Exception as e:
            print(f"⚠️ MCP1 Init Failed: {e} -> Skipping MCP1")
            self.mcp1_ready = False

        # --- MCP 2 (Sensor 9-16) ---
        try:
            self.mcp2 = MCP2(bus=3, address=0x23)
            self.mcp2_ready = True
            print("✅ MCP2 (Sensor 9-16) initialized.")
        except Exception as e:
            print(f"⚠️ MCP2 Init Failed: {e} -> Skipping MCP2")
            self.mcp2_ready = False

        # --- MCP 3 (System & Check) ---
        try:
            self.mcp3 = MCP3(bus=3, address=0x25)
            self.mcp3_ready = True
            print("✅ MCP3 (System Control) initialized.")
        except Exception as e:
            print(f"⚠️ MCP3 Init Failed: {e} -> Skipping MCP3")
            self.mcp3_ready = False
        
        # Sensor status tracking
        self.sensor_status = {}      # เก็บสถานะการเสียบสาย (จาก MCP3)
        self.overcurrent_status = {} # เก็บสถานะ Overcurrent (จาก MCP1, 2)
        self.power_status = {}       # เก็บสถานะการจ่ายไฟ (Logic ภายใน)
        self.previous_sensor_status = {}
        
        # Setup pin configurations (เฉพาะตัวที่ Ready)
        self.setup_mcp_pins()
        
        # System running flag
        self.running = False
        
    def setup_mcp_pins(self):
        """Configure pins only for available MCPs"""
        print("Configuring MCP pins...")
        
        def safe_set_pin(mcp, port, pin, mode, description):
            if not mcp: return False
            try:
                mcp.set_pin_mode(port, pin, mode)
                time.sleep(0.01)
                return True
            except Exception as e:
                print(f"Error setting {description}: {e}")
                return False
        
        # MCP1 Config
        if self.mcp1_ready:
            try:
                print("Configuring MCP1...")
                for i in range(4):
                    safe_set_pin(self.mcp1, 'B', i, 0, f"sensor_en{i+1}")
                    safe_set_pin(self.mcp1, 'A', 3-i, 0, f"sensor_en{8-i}")
                for i in range(4):
                    safe_set_pin(self.mcp1, 'B', 4+i, 1, f"over_current{i+1}")
                    safe_set_pin(self.mcp1, 'A', 7-i, 1, f"over_current{8-i}")
            except Exception as e:
                print(f"❌ Error config MCP1: {e}")

        # MCP2 Config
        if self.mcp2_ready:
            try:
                print("Configuring MCP2...")
                for i in range(4):
                    safe_set_pin(self.mcp2, 'B', i, 0, f"sensor_en{i+9}")
                    safe_set_pin(self.mcp2, 'A', 3-i, 0, f"sensor_en{16-i}")
                for i in range(4):
                    safe_set_pin(self.mcp2, 'B', 4+i, 1, f"over_current{i+9}")
                    safe_set_pin(self.mcp2, 'A', 7-i, 1, f"over_current{16-i}")
            except Exception as e:
                print(f"❌ Error config MCP2: {e}")

        # MCP3 Config
        if self.mcp3_ready:
            try:
                print("Configuring MCP3...")
                for i in range(8):
                    safe_set_pin(self.mcp3, 'B', i, 1, f"sensor_check{i+1}")
                for i in range(4):
                    safe_set_pin(self.mcp3, 'A', 3-i, 1, f"sensor_check{12-i}")
                
                safe_set_pin(self.mcp3, 'A', 7, 0, "system_LED")
                for i in range(3):
                    safe_set_pin(self.mcp3, 'A', 6-i, 1, f"jumper_mode{i+1}")
            except Exception as e:
                print(f"❌ Error config MCP3: {e}")
            
    def turn_on_all_sensors(self):
        """Turn ON all sensor power supplies (Safe Mode)"""
        print("Turning ON all sensor power supplies...")
        
        if self.mcp1_ready:
            try:
                for i in range(4):
                    self.mcp1.write_pin('B', i, 0)
                    self.mcp1.write_pin('A', 3-i, 0)
                # Mark as ON for ports 1-8
                for p in range(1, 9): self.power_status[p] = True
            except Exception as e:
                print(f"Error MCP1 turn on: {e}")
            
        if self.mcp2_ready:
            try:
                for i in range(4):
                    self.mcp2.write_pin('B', i, 0)
                    self.mcp2.write_pin('A', 3-i, 0)
                # Mark as ON for ports 9-16
                for p in range(9, 17): self.power_status[p] = True
            except Exception as e:
                print(f"Error MCP2 turn on: {e}")
            
    def turn_on_sensor(self, sensor_num):
        """Turn ON specific sensor (with MCP check)"""
        if not (1 <= sensor_num <= 16): return

        print(f"Turning ON sensor {sensor_num}")
        
        try:
            if 1 <= sensor_num <= 8:
                if not self.mcp1_ready:
                    print(f"⚠️ Cannot turn on Port {sensor_num}: MCP1 not ready")
                    return
                
                if sensor_num <= 4: self.mcp1.write_pin('B', sensor_num-1, 0)
                else:               self.mcp1.write_pin('A', 8-sensor_num, 0)
                
            elif 9 <= sensor_num <= 16:
                if not self.mcp2_ready:
                    print(f"⚠️ Cannot turn on Port {sensor_num}: MCP2 not ready")
                    return

                if sensor_num <= 12: self.mcp2.write_pin('B', sensor_num-9, 0)
                else:                self.mcp2.write_pin('A', 16-sensor_num, 0)
            
            self.power_status[sensor_num] = True
            
        except Exception as e:
            print(f"❌ Error turning on sensor {sensor_num}: {e}")

    def turn_off_sensor(self, sensor_num):
        """Turn OFF specific sensor (with MCP check)"""
        if not (1 <= sensor_num <= 16): return

        print(f"Turning OFF sensor {sensor_num}")
        
        try:
            if 1 <= sensor_num <= 8:
                if self.mcp1_ready:
                    if sensor_num <= 4: self.mcp1.write_pin('B', sensor_num-1, 1)
                    else:               self.mcp1.write_pin('A', 8-sensor_num, 1)
                
            elif 9 <= sensor_num <= 16:
                if self.mcp2_ready:
                    if sensor_num <= 12: self.mcp2.write_pin('B', sensor_num-9, 1)
                    else:                self.mcp2.write_pin('A', 16-sensor_num, 1)
            
            self.power_status[sensor_num] = False
            
        except Exception as e:
            print(f"❌ Error turning off sensor {sensor_num}: {e}")
    
    def check_overcurrent(self):
        """Check overcurrent status (skip if MCP not ready)"""
        # Mapping ขา Overcurrent
        # MCP1 (Port 1-8), MCP2 (Port 9-12 support in code)
        
        # Ports 1-8
        if self.mcp1_ready:
            try:
                # Port 1-4 (B4-B7)
                for i in range(4):
                    port = i + 1
                    val = self.mcp1.read_pin('B', 4+i)
                    is_fault = (val == 0)
                    self.overcurrent_status[port] = is_fault
                    if is_fault:
                        print(f"⚠️ OVERCURRENT Port {port} -> Turning OFF")
                        self.turn_off_sensor(port)
                        
                # Port 5-8 (A4-A7 reversed)
                for i in range(4):
                    port = i + 5
                    val = self.mcp1.read_pin('A', 7-i)
                    is_fault = (val == 0)
                    self.overcurrent_status[port] = is_fault
                    if is_fault:
                        print(f"⚠️ OVERCURRENT Port {port} -> Turning OFF")
                        self.turn_off_sensor(port)
            except Exception as e:
                print(f"Error checking OC MCP1: {e}")

        # Ports 9-12
        if self.mcp2_ready:
            try:
                for i in range(4):
                    port = i + 9
                    val = self.mcp2.read_pin('B', 4+i)
                    is_fault = (val == 0)
                    self.overcurrent_status[port] = is_fault
                    if is_fault:
                        print(f"⚠️ OVERCURRENT Port {port} -> Turning OFF")
                        self.turn_off_sensor(port)
            except Exception as e:
                print(f"Error checking OC MCP2: {e}")

        return [p for p, fault in self.overcurrent_status.items() if fault]

    def check_sensor_connection(self):
        """Check connection status (skip if MCP3 not ready)"""
        connected = []
        disconnected = []
        
        if not self.mcp3_ready:
            return [], [] # Return empty if MCP3 broken

        try:
            # Check 1-8 (Port B0-B7)
            for i in range(8):
                port = i + 1
                status = self.mcp3.read_pin('B', i)
                # 0 = Connected, 1 = Disconnected (Logic ตามเดิม)
                self.sensor_status[port] = status
                
                # Check logic
                is_connected = (status == 0) 
                if is_connected: connected.append(port)
                else: disconnected.append(port)

            # Check 9-12 (Port A3-A0)
            for i in range(4):
                port = i + 9
                status = self.mcp3.read_pin('A', 3-i)
                # Logic 9-12 อาจต่างกัน (เช็คตามโค้ดเดิม: 1=Connected, 0=Disconnected)
                # จากโค้ดเก่า: return "CONNECTED" if value == 1 else "DISCONNECTED"
                self.sensor_status[port] = status
                
                is_connected = (status == 1)
                if is_connected: connected.append(port)
                else: disconnected.append(port)
                
        except Exception as e:
            print(f"Error checking sensor connection: {e}")
            
        return connected, disconnected

    def get_all_port_statuses(self):
        """
        รวบรวมสถานะทั้งหมดของทุก Port เพื่อส่งให้ Main
        return: dict { port_num: { 'connected': bool, 'overcurrent': bool, 'power_on': bool } }
        """
        status_report = {}
        # ตรวจสอบ 12 Ports (หรือตามที่มี)
        for port in range(1, 13): # 1-12
            # 1. Connection Status
            is_connected = False
            if port in self.sensor_status:
                val = self.sensor_status[port]
                if 1 <= port <= 8: is_connected = (val == 0)
                elif 9 <= port <= 12: is_connected = (val == 1)
            
            # 2. Overcurrent Status (True = Fault)
            is_overcurrent = self.overcurrent_status.get(port, False)
            
            # 3. Power Status (True = ON)
            is_power_on = self.power_status.get(port, False)
            
            status_report[port] = {
                "connected": is_connected,
                "overcurrent": is_overcurrent,
                "power_on": is_power_on
            }
            
        return status_report

    # ... (Functions อื่นๆ activate_sensor, read_jumper_mode คงเดิมแต่ใส่ try-except เพิ่มตามสมควร) ...
    def read_jumper_mode(self):
        if not self.mcp3_ready: return 0, 0, 0
        try:
            mode1 = self.mcp3.read_pin('A', 6)
            mode2 = self.mcp3.read_pin('A', 5)
            mode3 = self.mcp3.read_pin('A', 4)
            return mode1, mode2, mode3
        except:
            return 0, 0, 0

    def system_led_blink(self, times=3):
        if not self.mcp3_ready: return
        try:
            for _ in range(times):
                self.mcp3.write_pin('A', 7, 1)
                time.sleep(0.2)
                self.mcp3.write_pin('A', 7, 0)
                time.sleep(0.2)
        except:
            pass

    def cleanup(self):
        # Clean up code (optional)
        pass