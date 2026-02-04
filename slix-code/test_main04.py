#!/usr/bin/env python3
"""
Main Controller for Integrated Sensor System
Luckfox Pico ProMax with Multiple Sensors
RS485 Sequential Communication + ThingsBoard Integration
"""

import time
import threading
import json
from datetime import datetime
import signal
import sys
import serial
import pytz
import subprocess
import socket
import requests

# Import MCP Control System
from test_mcp01 import SensorControlSystem

# Import All Sensor Classes
from class_wind_modbus import SensorWindSpeedDirection
from class_solar_modbus import SensorPyranometer  
from class_soil_modbus import SensorSoilMoistureTemp
from class_temp_modbus import SensorAirTempHumidityRS30
from class_rain_modbus import RainTipModbus
from class_ultra_modbus import UltrasonicModbus
from class_soil_EC_RK500 import SensorSoilECRK500_23  
from class_soilPH_RK500 import SensorSoilPHRK500_22 
from class_RKL01 import SensorWaterLevelRKL01

# Import ThingsBoard Sender
from telemetry_sending_paho import ThingsBoardSender

class IntegratedSensorSystem:
    def __init__(self, control_box_id="SLXA1250006"):  #ให้เอาชื่อใน weverboard SLXA12----- มาใส่แทนตัวนี้ อย่าลืมกดค้นหาแล้วใส่ให้ครบ บรรทัดไหนมี SLXA12-----
        print("🚀 Initializing Integrated Sensor System...")
        
        # Control Box Configuration
        self.control_box_id = control_box_id
        
        # Thailand Timezone
        self.thailand_tz = pytz.timezone('Asia/Bangkok')
        
        # MCP Control System
        self.mcp_system = SensorControlSystem()

        # Internet monitoring
        self.internet_available = False
        self.internet_was_unavailable_at_start = False
        self.internet_monitor_thread = None
        self.internet_check_interval = 5  # ตรวจสอบทุก 5 วินาที
        self.internet_timeout = 10  # timeout สำหรับการตรวจสอบ
        self.primary_check_url = "https://www.google.com"
        
        
        # ThingsBoard Configuration
        self.thingsboard_config = {
            "host": "thingsboard.weaverbase.com",
            "port": 1883,
            "access_token": "obqbBrUX2SfxylzlHF0m", #นำ token จาก weaverboard ที่ gen แล้วมาใส่
            "topic": "v1/gateway/telemetry"
        }
        
        # Initialize ThingsBoard Sender
        self.thingsboard_sender = None
        self._initialize_thingsboard()
        
        # Sensor Configuration - ทุกตัวใช้ RS485
        self.sensor_config = {
            1: {
                "address": 0x1A, #26-37 Default addr is 26
                "type": "wind", 
                "class": SensorWindSpeedDirection,
                "model": "RK120",
                "baudrate": 9600,
                "timeout": 1.5,
                "instance": "01",
                "enabled": True
            },
            2: {
                "address": 0x02, #01-13 Default addr is 1
                "type": "soil", 
                "class": SensorSoilMoistureTemp,
                "model": "RK520",
                "baudrate": 9600,
                "timeout": 1.5,
                "instance": "01",  #ถ้า sensor ชนิดเดียวกันมีมากกว่า 1 ตัวให้เปลี่ยนเลข instance ดูsoil เป็นตัวอย่าง
                "enabled": True
            },
            3: {
                "address": 0x03, #01-13 Default addr is 1
                "type": "soil", 
                "class": SensorSoilMoistureTemp,
                "model": "RK520",
                "baudrate": 9600,
                "timeout": 1.5,
                "instance": "02",
                "enabled": True
            },
            4: {
                "address": 0x0E,  #14-25 Default addr is 14
                "type": "air_temp", 
                "class": SensorAirTempHumidityRS30,
                "model": "MW485",
                "baudrate": 9600,
                "timeout": 5,
                "instance": "01",
                "enabled": True
            },
            5: {
                "address": 0x4E,  #76-87 Default addr is 76
                "type": "ultrasonic", 
                "class": UltrasonicModbus,
                "model": "RCWL",
                "baudrate": 9600,
                "timeout": 5,
                "instance": "01",
                "enabled": True
            },
            6: {
                "address": 0x32, #50-61 Default addr is 50 
                "type": "rainfall", 
                "class": RainTipModbus,
                "model": "RK400",
                "baudrate": 9600,
                "timeout": 1.5,
                "instance": "01",
                "enabled": True
            },
            7: {
                "address": 0x26, #38-49 Default addr is 38 
                "type": "solar", 
                "class": SensorPyranometer,
                "model": "RK200",
                "baudrate": 9600,
                "timeout": 1.5,
                "instance": "01",
                "enabled": False
            },
            8: {
                "address": 0x58, #88-99 Default addr is 88
                "type": "soil_ec", 
                "class": SensorSoilECRK500_23,
                "model": "RK500-23",
                "baudrate": 9600,
                "timeout": 1.5,
                "instance": "01",
                "enabled": False
            },
            9: {
                "address": 0x64, #100-111 Default addr is 100
                "type": "soil_ph", 
                "class": SensorSoilPHRK500_22,
                "model": "RK500-22",
                "baudrate": 9600,
                "timeout": 1.5,
                "instance": "01",
                "enabled": False
            },
            10: {
                "address": 0x70, #112-123 Default addr is 112
                "type": "liquid_level", 
                "class": SensorWaterLevelRKL01,
                "model": "RKL-01",
                "baudrate": 9600,
                "timeout": 5,
                "instance": "01",
                "enabled": False
            },
        }
        
        # Sensor measurement names
        self.measurement_names = {
            "air_temp": {
                "temperature": "Air_Temp",
                "humidity": "Air_Humid"
            },
            "soil": {
                "soil_temperature": "Soil_Temp", 
                "soil_moisture": "Soil_Moist"
            },
            "solar": {
                "solar_radiation": "Solar_Rad"
            },
            "wind": {
                "wind_speed": "Wind_Speed",
                "wind_direction": "Wind_Dir" 
            },
            "rainfall": {
                "rainfall": "Rain_Gauge"
            },
            "ultrasonic": {
                "distance_cm": "Ultra_Level",
                "distance_formula": "Ultra_Level_alarm"
            },
            "soil_ec": {
                "ec_value": "Soil_EC",
                "salinity": "Soil_Sal"
            },
            "soil_ph":{
                "ph_value": "Soil_pH",
                "temperature": "pH_Temp"
            },
            "liquid_level":{
                "water_level": "Water_Level"
            },
        }
        
        # Serial port settings
        self.serial_port = "/dev/ttyS2"
        self.current_baudrate = None
        self.serial_connection = None
        
        # Sensor Instances
        self.sensors = {}
        self.sensor_data = {}
        
        # Status Tracking
        self.previous_status = {}  # เก็บ status ครั้งก่อน
        self.last_communication_status = {}  # เก็บผล communication ล่าสุด
        self.first_run = True  # เช็คครั้งแรก
        
        # Control Flags
        self.running = True
        self.read_interval = 60  # seconds
        
        # Threading
        self.sensor_thread = None
        self.serial_lock = threading.Lock()
        
        # Initialize Serial and Sensors
        self._initialize_serial()
        self._initialize_sensors()

    def _on_thingsboard_status_change(self, connected):
        if connected:
            print("🎉 ThingsBoard reconnected successfully!")
        else:
            print("💔 ThingsBoard disconnected")
        
    def _initialize_thingsboard(self):
        """Initialize ThingsBoard connection"""
        try:
            print("📡 Initializing ThingsBoard connection...")
            self.thingsboard_sender = ThingsBoardSender(
                host=self.thingsboard_config["host"],
                port=self.thingsboard_config["port"],
                access_token=self.thingsboard_config["access_token"]
            )

            self.thingsboard_sender.connection_status_callback = self._on_thingsboard_status_change
            # Connect to ThingsBoard

            if self.thingsboard_sender.connect():
                print("✅ ThingsBoard connected successfully")
        
                def rpc_reset_remote(method, params):
                    if not params.get("param", False):
                        return {"success": False, "message": "param must be true"}
                    
                    def restart_service():
                        try:
                            # Stop service
                            subprocess.run(
                                ["sh", "-x", "/etc/init.d/S99sshtunnel","restart"], 
                                timeout=20, 
                                check=False
                            )
                            time.sleep(3)
                            
                            # Start service
                            subprocess.run(
                                ["sh", "-x", "/etc/init.d/S99sshtunnel", "start"], 
                                timeout=20,
                                check=True
                            )
                            
                            print("✅ SSH tunnel service restarted successfully")
                            
                        except Exception as e:
                            print(f"❌ Service restart failed: {e}")
                    
                    # Run in background thread
                    import threading
                    threading.Thread(target=restart_service, daemon=True).start()
                    
                    return {
                        "success": True, 
                        "message": "SSH tunnel restart initiated. Please wait 20-30 seconds before attempting remote connection.", 
                        "timestamp": int(time.time() * 1000)
                    }



                def rpc_reboot(method, params):
                    if not params.get("param", False):
                        return {"success": False, "message": "param must be true"}
                    try:
                        subprocess.run(["reboot"], check=True)
                        return {
                            "success": True,
                            "message": "Reboot command sent",
                            "timestamp": int(time.time() * 1000)
                        }
                    except subprocess.CalledProcessError as e:
                        return {"success": False, "message": f"reboot failed: {e}"}

                self.thingsboard_sender.register_rpc_method(
                    "reset_remote", rpc_reset_remote,
                    {"required": ["param"], "types": {"param": "bool"}}
                )
                self.thingsboard_sender.register_rpc_method(
                    "reboot", rpc_reboot,
                    {"required": ["param"], "types": {"param": "bool"}}
                )

  
                self.thingsboard_sender.start_rpc_handler()

            else:
                print("❌ Failed to connect to ThingsBoard")
                
        except Exception as e:
            print(f"❌ ThingsBoard initialization error: {e}")
            self.thingsboard_sender = None
            
    def _initialize_serial(self):
        """Initialize serial connection"""
        print("🔌 Initializing RS485 serial connection...")
        try:
            self.serial_connection = serial.Serial(
                port=self.serial_port,
                baudrate=9600,
                timeout=1.5,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            self.current_baudrate = 9600
            print(f"✅ Serial connection established on {self.serial_port}")
        except Exception as e:
            print(f"❌ Failed to initialize serial connection: {e}")
            self.serial_connection = None
            
    def _change_baudrate(self, new_baudrate):
        """Change serial baudrate if needed"""
        if self.current_baudrate != new_baudrate and self.serial_connection:
            try:
                self.serial_connection.close()
                time.sleep(0.1)
                
                self.serial_connection = serial.Serial(
                    port=self.serial_port,
                    baudrate=new_baudrate,
                    timeout=1.5,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS
                )
                self.current_baudrate = new_baudrate
                print(f"🔄 Baudrate changed to {new_baudrate}")
                time.sleep(0.2)
                return True
            except Exception as e:
                print(f"❌ Failed to change baudrate to {new_baudrate}: {e}")
                return False
        return True
        
    def _initialize_sensors(self):
        print("🔧 Initializing sensors...")
        for port, config in self.sensor_config.items():
            if not config.get("enabled", True):
                print(f"⏭️ Skip init port {port} ({config.get('type')}) - disabled")
                self.sensors[port] = None
                continue
            try:
                sensor = config["class"](port=self.serial_port, slave_address=config["address"], baudrate=config["baudrate"])
                self.sensors[port] = {
                    "instance": sensor,
                    "type": config["type"],
                    "address": config["address"],
                    "baudrate": config["baudrate"],
                    "timeout": config["timeout"],
                    "model": config["model"],
                    "instance_num": config["instance"]
                }
                self.previous_status[port] = {"current_status": None, "operation_status": None}
                self.last_communication_status[port] = False
                print(f"✅ Port {port} ({config['type']}) - Address: 0x{config['address']:02X}, Model: {config['model']}, Instance: {config['instance']}")
            except Exception as e:
                print(f"❌ Failed to initialize sensor on port {port}: {e}")
                self.sensors[port] = None
                
    def get_thailand_timestamp(self):
        """Get current timestamp in Thailand timezone (milliseconds)"""
        now = datetime.now(self.thailand_tz)
        return int(now.timestamp() * 1000)
        
    def determine_sensor_status(self, port, communication_success):
        """กำหนด status ของ sensor จากข้อมูล MCP + Communication"""
        try:
            # เช็ค MCP sensor connection
            self.mcp_system.check_sensor_connection()
            self.mcp_system.check_overcurrent()
            
            # สมมติว่า MCP มี method เหล่านี้ (อาจต้องเพิ่ม)
            # connection_detected = self.mcp_system.is_sensor_connected(port)
            # power_normal = not self.mcp_system.is_overcurrent(port)
            
            # ใช้ข้อมูลจาก communication result แทน
            # connection_detected = True  # สมมติว่าเสียบอยู่ถ้าไม่มี overcurrent
            # power_normal = True  # สมมติว่า power ปกติ
            connection_status = self.get_mcp_sensor_connection(port)
            power_status = self.get_mcp_power_status(port)

            print(f"   Physical Connection: {connection_status}")
            print(f"   Power Status: {power_status}")  
            print(f"   Communication: {'Success' if communication_success else 'Failed'}")
            
            # กำหนด status ตาม logic
            if connection_status == "CONNECTED" and power_status == "normal" and communication_success:
                status = ("healthy", "online")
            elif connection_status == "CONNECTED":
                status = ("weekly", "online")  
            else:
                status = ("weekly", "offline")
        
            print(f"   Final Status: {status[0]}/{status[1]}")
            return status
                    
        except Exception as e:
            print(f"❌ Error determining status for port {port}: {e}")
            return "weekly", "offline"
        
    def get_mcp_sensor_connection(self, port):
        """ดึงสถานะการเชื่อมต่อจาก MCP จริงๆ"""
        try:
            # เรียกใช้ MCP system เพื่อ update สถานะล่าสุด
            self.mcp_system.check_sensor_connection()
            
            # 🔧 อ่านจาก sensor_status ที่ MCP เก็บไว้
            if port in self.mcp_system.sensor_status:
                sensor_value = self.mcp_system.sensor_status[port]
                
                # แปลงค่าตาม logic ของแต่ละช่วง port
                if 1 <= port <= 8:
                    # Sensors 1-8: 0 = Connected, 1 = Disconnected
                    return "CONNECTED" if sensor_value == 0 else "DISCONNECTED"
                elif 9 <= port <= 12:
                    # Sensors 9-12: 1 = Connected, 0 = Disconnected  
                    return "CONNECTED" if sensor_value == 1 else "DISCONNECTED"
                else:
                    return "UNKNOWN"
            else:
                # ถ้าไม่มีใน sensor_status ให้อ่านโดยตรง
                return self.read_sensor_check_pin_direct(port)
            
        except Exception as e:
            print(f"❌ Error reading MCP sensor connection for port {port}: {e}")
            return "UNKNOWN"
        
    def get_mcp_power_status(self, port):
        """ดึงสถานะ power จาก MCP จริงๆ"""
        try:
            # เรียกใช้ MCP system เพื่อ update สถานะล่าสุด
            self.mcp_system.check_overcurrent()
            
            # 🔧 อ่านจาก overcurrent_status ที่ MCP เก็บไว้
            if port in self.mcp_system.overcurrent_status:
                overcurrent = self.mcp_system.overcurrent_status[port]
                # True = มี overcurrent (fault), False = ปกติ (normal)
                return "fault" if overcurrent else "normal"
            else:
                # ถ้าไม่มีใน overcurrent_status ให้อ่านโดยตรง
                return self.read_overcurrent_pin_direct(port)
                
        except Exception as e:
            print(f"❌ Error reading MCP power status for port {port}: {e}")
            return "unknown"
        
    def get_cpu_temperature(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp_raw = f.read().strip()
                return float(temp_raw) / 1000.0
        except Exception as e:
            print(f"❌ Error reading CPU temp: {e}")
            return None
        
    def read_sensor_check_pin_direct(self, port):
        """อ่าน sensor_check pin โดยตรงจาก MCP (backup method)"""
        try:
            if 1 <= port <= 8:
                # Port 1-8: MCP3 Port B, pins 0-7
                pin = port - 1  # Port 1 = Pin 0
                value = self.mcp_system.mcp3.read_pin('B', pin)
                # 0 = connected, 1 = disconnected
                return "CONNECTED" if value == 0 else "DISCONNECTED"
                
            elif 9 <= port <= 12:
                # Port 9-12: MCP3 Port A, pins 3,2,1,0
                pin = 12 - port  # Port 9 = Pin 3, Port 10 = Pin 2, etc.
                value = self.mcp_system.mcp3.read_pin('A', pin)
                # 1 = connected, 0 = disconnected
                return "CONNECTED" if value == 1 else "DISCONNECTED"
            else:
                print(f"⚠️  Port {port} not supported for sensor check")
                return "UNKNOWN"
                
        except Exception as e:
            print(f"❌ Error reading sensor check pin for port {port}: {e}")
            return "UNKNOWN"
        
    def read_overcurrent_pin_direct(self, port):
        """อ่าน overcurrent pin โดยตรงจาก MCP (backup method)"""
        try:
            if 1 <= port <= 8:
                # MCP1 overcurrent pins
                if port <= 4:
                    # Port 1-4: MCP1 Port B, pins 4-7
                    pin = 4 + (port - 1)  # Port 1 = Pin 4
                    value = self.mcp_system.mcp1.read_pin('B', pin)
                else:
                    # Port 5-8: MCP1 Port A, pins 7,6,5,4  
                    pin = 7 - (port - 5)  # Port 5 = Pin 7, Port 6 = Pin 6, etc.
                    value = self.mcp_system.mcp1.read_pin('A', pin)
                    
            elif 9 <= port <= 12:
                # MCP2 overcurrent pins  
                # Port 9-12: MCP2 Port B, pins 4-7
                pin = 4 + (port - 9)  # Port 9 = Pin 4
                value = self.mcp_system.mcp2.read_pin('B', pin)
                
            else:
                print(f"⚠️  Port {port} not supported for overcurrent check")
                return "unknown"
            
            # 0 = fault, 1 = normal
            return "normal" if value == 1 else "fault"
                
        except Exception as e:
            print(f"❌ Error reading overcurrent pin for port {port}: {e}")
            return "unknown"
            
    def create_sensor_message_name(self, port, measurement_type):
        """สร้างชื่อ message สำหรับ ThingsBoard"""
        sensor_info = self.sensors[port]
        sensor_type = sensor_info["type"]
        model = sensor_info["model"]
        instance = sensor_info["instance_num"]
        
        # แปลง measurement type เป็นชื่อที่ต้องการ
        measurement_name = self.measurement_names[sensor_type].get(measurement_type, measurement_type)
        
        return f"{self.control_box_id}_{measurement_name}_{model}-{instance}"
        
    def send_sensor_data_to_thingsboard(self, port, sensor_data, current_status, operation_status):
        """ส่งข้อมูล sensor ไป ThingsBoard (เฉพาะ data_value)"""
        # Auto-reconnect ก่อนส่ง
        # try:
        #     if self.thingsboard_sender is None:
        #         # ยังไม่เคยสร้าง หรือสร้างแล้วล้ม -> สร้างใหม่และเชื่อมใหม่
        #         self._initialize_thingsboard()
        #     elif hasattr(self.thingsboard_sender, "connected") and not self.thingsboard_sender.connected:
        #         # เคยสร้างแล้วแต่หลุด -> ลองเชื่อมใหม่
        #         self.thingsboard_sender.connect()

        #     if messages:
        #         ok = self.thingsboard_sender.send_telemetry(messages)
        #         if ok:
        #             print(f"📤 Sent to ThingsBoard: Port {port}")
                    
        #             # 🆕 เช็คสถานะ Internet เมื่อ telemetry ส่งสำเร็จ
        #             if not self.internet_available:
        #                 print(f"   ⚡ Telemetry sent successfully but Internet flag is False!")
        #                 print(f"   📡 ThingsBoard connected: {self.thingsboard_sender.connected}")
        #                 print(f"   🔍 This might indicate Internet connection is actually available")
                        
        #                 # Trigger force check ใน monitor thread
        #                 if not hasattr(self, '_telemetry_trigger_time'):
        #                     self._telemetry_trigger_time = 0
                        
        #                 # ป้องกันการ trigger บ่อยเกินไป
        #                 if time.time() - self._telemetry_trigger_time > 30:
        #                     self._telemetry_trigger_time = time.time()
        #                     print(f"   🚨 Scheduling immediate Internet re-check...")
                    
        #             for key, value in messages.items():
        #                 print(f"   📊 {key}: {value[0]['values']['data_value']}")
        #         else:
        #             print("⚠️ Failed to send telemetry")
        # except Exception as e:
        #     print(f"⚠️ ThingsBoard reconnect attempt failed: {e}")

        if not self.thingsboard_sender:
            print("⚠️ ThingsBoard sender not initialized")
            return
        
        try:
            sensor_info = self.sensors[port]
            sensor_type = sensor_info["type"]
            ts_now = self.get_thailand_timestamp()

            # สร้าง messages สำหรับ multi-value sensors
            messages = {}

            if sensor_type == "air_temp":
                if "temperature" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "temperature")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["temperature"]}
                    }]
                if "humidity" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "humidity")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["humidity"]}
                    }]

            elif sensor_type == "soil":
                if "soil_temperature" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "soil_temperature")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["soil_temperature"]}
                    }]
                if "soil_moisture" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "soil_moisture")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["soil_moisture"]}
                    }]

            elif sensor_type == "soil_ec":
                # RK500-23 Soil EC & Salinity
                if "ec_value" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "ec_value")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["ec_value"]}
                    }]
                if "salinity" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "salinity")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["salinity"]}
                    }]

            elif sensor_type == "soil_ph":
                # RK500-22 Soil pH
                if "ph_value" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "ph_value")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["ph_value"]}
                    }]
                if "temperature" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "temperature")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["temperature"]}
                    }]

            elif sensor_type == "solar":
                if "solar_radiation" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "solar_radiation")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["solar_radiation"]}
                    }]

            elif sensor_type == "wind":
                if "wind_speed" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "wind_speed")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["wind_speed"]}
                    }]
                if "wind_direction" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "wind_direction")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["wind_direction"]}
                    }]

            elif sensor_type == "rainfall":
                if "rainfall" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "rainfall")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["rainfall"]}
                    }]

            elif sensor_type == "ultrasonic":
                # ส่งค่าเดิม (Level)
                if "distance_cm" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "distance_cm")
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["distance_cm"]}
                    }]
                
                # ส่งค่าใหม่ (Formula)
                if "distance_formula" in sensor_data:
                    msg_name = self.create_sensor_message_name(port, "distance_formula")
                    # ผลลัพธ์ชื่อ Device จะเป็น: SLXA..._data_value_formular_RCWL-01
                    messages[msg_name] = [{
                        "ts": ts_now,
                        "values": {"data_value": sensor_data["distance_formula"]}
                    }]

            # ส่งข้อมูลไป ThingsBoard
            if messages:
                ok = self.thingsboard_sender.send_telemetry(messages)
                if ok:
                    print(f"📤 Sent sensor data to ThingsBoard: Port {port}")
                    for key, value in messages.items():
                        print(f"  {key}: {value[0]['values']['data_value']}")
                else:
                    print("⚠️ Failed to send telemetry (sender returned False)")
        except Exception as e:
            print(f"❌ Error sending data to ThingsBoard for port {port}: {e}")
            
    def send_status_to_thingsboard(self, port, current_status, operation_status):
        """ส่ง status ไป ThingsBoard เมื่อมีการเปลี่ยนแปลง"""
        # Auto-reconnect ก่อนส่ง
        # try:
        #     if self.thingsboard_sender is None:
        #         self._initialize_thingsboard()
        #     elif hasattr(self.thingsboard_sender, "connected") and not self.thingsboard_sender.connected:
        #         self.thingsboard_sender.connect()
        # except Exception as e:
        #     print(f"⚠️ ThingsBoard reconnect attempt failed: {e}")

        # if not self.thingsboard_sender or (hasattr(self.thingsboard_sender, "connected") and not self.thingsboard_sender.connected):
        #     return

        if not self.thingsboard_sender:
            return

        try:
            sensor_info = self.sensors[port]
            sensor_type = sensor_info["type"]
            ts_now = self.get_thailand_timestamp()

            messages = {}
            for measurement_key in self.measurement_names[sensor_type].keys():
                msg_name = self.create_sensor_message_name(port, measurement_key)
                messages[msg_name] = [{
                    "ts": ts_now,
                    "values": {
                        "current_status": current_status,
                        "operation_status": operation_status
                    }
                }]

            if messages:
                ok = self.thingsboard_sender.send_telemetry(messages)
                if ok:
                    print(f"📤 Sent status update to ThingsBoard: Port {port} - {current_status}/{operation_status}")
                else:
                    print("⚠️ Failed to send status (sender returned False)")
        except Exception as e:
            print(f"❌ Error sending status to ThingsBoard for port {port}: {e}")
            

    def send_controller_status_to_thingsboard(self):
        """
        ส่งสถานะ Hardware (IO) ทั้งหมดไปที่ ThingsBoard
        โดยสร้างเป็น Device แยกต่างหาก เช่น SLXA1250006_IO_Status
        """
        if not self.thingsboard_sender:
            return

        try:
            # 1. ดึงสถานะจาก MCP Class (ที่ทำเพิ่มใหม่)
            all_statuses = self.mcp_system.get_all_port_statuses()
            ts_now = self.get_thailand_timestamp()
            cpu_temp = self.get_cpu_temperature()
            
            # 2. สร้าง Telemetry Payload
            telemetry_values = {}
            
            for port, status in all_statuses.items():
                # แปลง Bool เป็น 1/0 หรือ True/False ตามต้องการ
                # Connection: 1=Connected, 0=Disconnected
                telemetry_values[f"port_{port}_connected"] = 1 if status['connected'] else 0
                
                # Overcurrent: 1=Fault, 0=Normal
                telemetry_values[f"port_{port}_overcurrent"] = 1 if status['overcurrent'] else 0
                
                # Power: 1=ON, 0=OFF
                telemetry_values[f"port_{port}_power"] = 1 if status['power_on'] else 0
            
            if cpu_temp is not None:
                telemetry_values["cpu_temperature"] = cpu_temp

            monitor_device_name = f"{self.control_box_id}_IO_Monitor"
            
            messages = {
                monitor_device_name: [{
                    "ts": ts_now,
                    "values": telemetry_values
                }]
            }

            # 4. ส่งข้อมูล
            ok = self.thingsboard_sender.send_telemetry(messages)
            if ok:
                print(f"📤 Sent IO Status to ThingsBoard ({monitor_device_name})")
                print(f"📤 Sent Status to {monitor_device_name} (CPU: {cpu_temp}°C)")
            else:
                print("⚠️ Failed to send IO Status")

        except Exception as e:
            print(f"❌ Error sending controller status: {e}")


    def enable_all_sensors(self):
        """Enable all sensor ports via MCP"""
        print("⚡ Enabling sensor ports...")
        
        for port in self.sensor_config.keys():
            try:
                self.mcp_system.turn_on_sensor(port)
                print(f"✅ Port {port} enabled")
                time.sleep(0.1)
            except Exception as e:
                print(f"❌ Failed to enable port {port}: {e}")
                
    def disable_all_sensors(self):
        """Disable all sensor ports via MCP"""
        print("🔌 Disabling sensor ports...")
        
        for port in self.sensor_config.keys():
            try:
                self.mcp_system.turn_off_sensor(port)
                print(f"✅ Port {port} disabled")
            except Exception as e:
                print(f"❌ Failed to disable port {port}: {e}")
                
    def read_sensor_with_timeout(self, port):
        """Read sensor data with timeout and baudrate management"""
        if port not in self.sensors or self.sensors[port] is None:
            return None
            
        sensor_info = self.sensors[port]
        sensor = sensor_info["instance"]
        sensor_type = sensor_info["type"]
        required_baudrate = sensor_info["baudrate"]
        timeout = sensor_info["timeout"]
        
        with self.serial_lock:
            try:
                if not self._change_baudrate(required_baudrate):
                    return None
                
                print(f"📡 Reading {sensor_type} sensor (Port {port})...")
                
                start_time = time.time()
                data = None
                
                if sensor_type == "wind":
                    data = sensor.read_wind()
                    if data:
                        result = {
                            "wind_speed": data.get("wind_speed"),
                            "wind_direction": data.get("wind_direction")
                        }
                    else:
                        result = None
                        
                elif sensor_type == "solar":
                    data = sensor.read_radiation()
                    if data and "radiation" in data:
                        result = {
                            "solar_radiation": data.get("radiation")
                        }
                    else:
                        result = None
                        
                elif sensor_type == "soil":
                    data = sensor.read_data()
                    if data:
                        result = {
                            "soil_moisture": data.get("soil_moisture"),
                            "soil_temperature": data.get("soil_temperature")
                        }
                    else:
                        result = None
                        
                elif sensor_type == "air_temp":
                    data = sensor.read_temp()
                    if data:
                        result = {
                            "temperature": data.get("temperature"),
                            "humidity": data.get("humidity")
                        }
                    else:
                        result = None
                elif sensor_type == "rainfall":
                    data = sensor.read_tip() 
                    if data and data.get("success"):
                        result = {
                            "rainfall": data.get("rainfall")
                        }
                    else:
                        result = None
                elif sensor_type == "ultrasonic":
                    data = sensor.read_distance() 
                    if data and data.get("success"):
                        result = {
                            "distance_cm": data.get("distance_cm"),
                            "distance_formula": data.get("distance_formula")
                        }
                    else:
                        result = None

                elif sensor_type == "soil_ec":
                    data = self.read_soil_ec_data(sensor)
                    if data:
                        result = {
                            "ec_value": data.get("ec_value"),
                            "salinity": data.get("salinity"),
                            "temperature": data.get("temperature")
                        }
                    else:
                        result = None
                        
                elif sensor_type == "soil_ph":
                    data = self.read_soil_ph_data(sensor)
                    if data:
                        result = {
                            "ph_value": data.get("ph_value"),
                            "temperature": data.get("temperature"),
                            "ph_classification": data.get("ph_classification")
                        }
                    else:
                        result = None
                
                elif sensor_type == "liquid_level":
                    data = self.read_water_level_data(sensor)
                    if data:
                        result = {
                            "water_level": data.get("water_level"),
                            "water_level_cm": data.get("water_level_cm"),
                            "raw_value": data.get("raw_value")
                        }
                    else:
                        result = None
                
                elapsed_time = time.time() - start_time
                if elapsed_time > timeout:
                    print(f"⏰ Timeout: {sensor_type} sensor took {elapsed_time:.2f}s")
                    return None
                    
                if result:
                    print(f"✅ {sensor_type} sensor responded in {elapsed_time:.2f}s")
                    return result
                else:
                    print(f"⚠️  {sensor_type} sensor: No valid data")
                    return None
                    
            except Exception as e:
                elapsed_time = time.time() - start_time
                if elapsed_time > timeout:
                    print(f"❌ {sensor_type} sensor: No response within {timeout}s")
                else:
                    print(f"❌ {sensor_type} sensor error: {e}")
                return None
                
            finally:
                time.sleep(0.2)

    def test_sensor_power_control(self):
        """ทดสอบการเปิด/ปิดไฟเซ็นเซอร์"""
        print("\n=== TESTING SENSOR POWER CONTROL ===")
        
        for port in [1, 2, 3, 4, 5, 6]:
            print(f"\nTesting Port {port}:")
            print("  Turning ON...")
            self.turn_on_sensor(port)
            time.sleep(2)
            
            print("  Turning OFF...")
            self.turn_off_sensor(port)
            time.sleep(2)
    
        print("\nTest completed!")
                
    def read_all_sensors_sequential(self):
        """Read all sensors sequentially with ThingsBoard integration"""
        print(f"📊 Reading all sensors sequentially... [{datetime.now().strftime('%H:%M:%S')}]")
        
        try:
            self.mcp_system.check_overcurrent()
            self.mcp_system.check_sensor_connection()
        except Exception as e:
            print(f"⚠️  MCP system check error: {e}")
        
        all_data = {
            "timestamp": datetime.now(self.thailand_tz).isoformat(),
            "sensors": {}
        }
        
        sensor_order = [p for p, cfg in self.sensor_config.items() if cfg.get("enabled", True)]
        
        for port in sensor_order:
            if port not in self.sensor_config:
                continue
                
            sensor_type = self.sensor_config[port]["type"]
            print(f"\n🔍 Reading sensor {port} ({sensor_type})...")
            
            try:
                # อ่านข้อมูลจาก sensor
                data = self.read_sensor_with_timeout(port)
                communication_success = data is not None
                print(f"📡 Communication Debug for Port {port}:")
                print(f"   - Raw data: {data}")
                print(f"   - communication_success: {communication_success}")
                
                # อัพเดท communication status
                self.last_communication_status[port] = communication_success
                
                # กำหนด current และ operation status
                current_status, operation_status = self.determine_sensor_status(port, communication_success)
                
                # เช็คว่า status เปลี่ยนแปลงหรือไม่
                prev_status = self.previous_status[port]
                status_changed = (
                    self.first_run or
                    prev_status["current_status"] != current_status or
                    prev_status["operation_status"] != operation_status
                )
                
                if data:
                    all_data["sensors"][f"port_{port}"] = {
                        "type": sensor_type,
                        "data": data,
                        "current_status": current_status,
                        "operation_status": operation_status,
                        "timestamp": datetime.now(self.thailand_tz).isoformat()
                    }
                    
                    print(f"✅ Port {port} ({sensor_type}): Success")
                    print(f"   Data: {data}")
                    print(f"   Status: {current_status}/{operation_status}")
                    
                    # ส่งข้อมูลไป ThingsBoard
                    if status_changed:
                        self.send_status_to_thingsboard(port, current_status, operation_status)
                    
                    self.send_sensor_data_to_thingsboard(port, data, current_status, operation_status)
                    
                else:
                    all_data["sensors"][f"port_{port}"] = {
                        "type": sensor_type,
                        "status": "no_response",
                        "current_status": current_status,
                        "operation_status": operation_status,
                        "timestamp": datetime.now(self.thailand_tz).isoformat()
                    }
                    
                    print(f"❌ Port {port} ({sensor_type}): No response")
                    print(f"   Status: {current_status}/{operation_status}")
                    
                    # ส่งเฉพาะ status ถ้าเปลี่ยนแปลง
                    if status_changed:
                        self.send_status_to_thingsboard(port, current_status, operation_status)
                
                # อัพเดท previous status
                self.previous_status[port] = {
                    "current_status": current_status,
                    "operation_status": operation_status
                }
                    
            except Exception as e:
                print(f"❌ Port {port} ({sensor_type}): Error - {e}")
                
                # ส่ง error status ถ้าเปลี่ยนแปลง
                current_status, operation_status = "weekly", "offline"
                if (self.first_run or 
                    self.previous_status[port]["current_status"] != current_status):
                    self.send_status_to_thingsboard(port, current_status, operation_status)
                
                self.previous_status[port] = {
                    "current_status": current_status,
                    "operation_status": operation_status
                }
            
            self.send_controller_status_to_thingsboard()
            
            if port < max(sensor_order):
                print(f"⏳ Waiting before next sensor...")
                time.sleep(0.5)
        
        # เปลี่ยน first_run เป็น False หลังรอบแรก
        self.first_run = False
        
        self.sensor_data = all_data
        responsive_sensors = len([s for s in all_data['sensors'].values() 
                                if 'status' not in s or s['status'] != 'no_response'])
        print(f"\n📋 Summary: {responsive_sensors}/{len(sensor_order)} sensors responded")
        return all_data
        
    # def save_data_to_file(self, data, filename="sensor_data.json"):
    #     """Save sensor data to JSON file"""
    #     try:
    #         with open(filename, "a") as f:
    #             json.dump(data, f, indent=2)
    #             f.write("\n")
    #     except Exception as e:
    #         print(f"❌ Failed to save data: {e}")
            
    def sensor_reading_loop(self):
        """Main sensor reading loop พร้อมแสดงสถานะ Internet"""
        print(f"🔄 Starting sensor reading loop (every {self.read_interval}s)")
        
        while self.running:
            try:
                print(f"\n{'='*60}")
                print(f"🕐 Sensor cycle at {datetime.now(self.thailand_tz).strftime('%H:%M:%S')}")
                
                # แสดงสถานะ Internet, ThingsBoard
                internet_icon = "🌐✅" if self.internet_available else "🌐❌"
                tb_icon = "📡✅" if (self.thingsboard_sender and self.thingsboard_sender.connected) else "📡❌"
                
                print(f"{internet_icon} Internet | {tb_icon} ThingsBoard")
                
                if not self.internet_available and self.thingsboard_sender and self.thingsboard_sender.connected:
                    print("   🤔 Strange: ThingsBoard connected but Internet flag False")
                
                print(f"{'='*60}")

                data = self.read_all_sensors_sequential()

                print(f"\n⏳ Waiting {self.read_interval}s for next cycle...")
                for i in range(self.read_interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except KeyboardInterrupt:
                print("\n🛑 Stopping sensor readings...")
                break
            except Exception as e:
                print(f"❌ Sensor loop error: {e}")
                time.sleep(5)


    def check_internet_connection(self):
        """ตรวจสอบการเชื่อมต่อ Internet - เช็คจริงไม่พึ่ง ThingsBoard"""
        
        print(f"🌐 Checking Internet at {datetime.now().strftime('%H:%M:%S')}...")
        
        # ❌ ลบการเช็ค ThingsBoard connection ออก
        # เพราะ ThingsBoard อาจจะยัง connected อยู่แม้เน็ตหาย (buffer)
        
        # วิธีที่ 1: เช็ค DNS (เร็วที่สุด)
        try:
            print("   🔍 Testing DNS (8.8.8.8)...")
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            print("   ✅ DNS test passed!")
            return True
        except OSError as e:
            print(f"   ❌ DNS failed: {e}")
        
        # วิธีที่ 2: เช็ค HTTP แบบไม่ cache
        try:
            print("   🔍 Testing HTTP (fresh request)...")
            # ใช้ headers เพื่อไม่ให้ cache
            headers = {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
            response = requests.get("https://www.google.com", 
                                headers=headers, 
                                timeout=3,
                                allow_redirects=False)
            if response.status_code == 200:
                print(f"   ✅ HTTP test passed (Status: {response.status_code})")
                return True
            else:
                print(f"   ❌ HTTP failed (Status: {response.status_code})")
        except Exception as e:
            print(f"   ❌ HTTP failed: {e}")
        
        # วิธีที่ 3: Ping (backup)
        try:
            print("   🔍 Testing Ping...")
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                capture_output=True,
                timeout=4,
                text=True
            )
            if result.returncode == 0:
                print("   ✅ Ping test passed!")
                return True
            else:
                print(f"   ❌ Ping failed (code: {result.returncode})")
                if result.stderr:
                    print(f"       Error: {result.stderr.strip()}")
        except Exception as e:
            print(f"   ❌ Ping error: {e}")
        
        print("   ❌ All Internet tests failed - No connection")
        return False
    
    def internet_monitor_loop(self):
        """Internet monitoring loop - เช็คการเปลี่ยนแปลงจริง"""
        print("🌐 Internet monitor started")
        
        # เช็คครั้งแรก
        print("\n📍 Initial Internet check...")
        initial_check = self.check_internet_connection()
        self.internet_available = initial_check
        
        if not initial_check:
            self.internet_was_unavailable_at_start = True
            print("⚠️  No Internet at startup → Will reboot when Internet returns")
        else:
            print("✅ Internet available at startup")
        
        loop_count = 0
        last_thingsboard_status = None  # 🆕 track ThingsBoard status
        
        while self.running:
            try:
                loop_count += 1
                
                # เช็ค ThingsBoard status เพื่อ detect การเปลี่ยนแปลง
                current_tb_status = (
                    self.thingsboard_sender and 
                    hasattr(self.thingsboard_sender, 'connected') and 
                    self.thingsboard_sender.connected
                )
                
                # ถ้า ThingsBoard status เปลี่ยน ให้ force check Internet
                force_check = (last_thingsboard_status is not None and 
                            current_tb_status != last_thingsboard_status)
                
                if force_check:
                    print(f"\n🔄 ThingsBoard status changed: {last_thingsboard_status} → {current_tb_status}")
                    print("🔍 Force checking Internet connection...")
                
                # กำหนดเวลาเช็ค
                if not self.internet_available or force_check:
                    check_interval = 0 if force_check else 3  # เช็คทันทีถ้า force, ไม่งั้น 10 วิ
                    if not force_check:
                        print(f"\n⏳ Waiting 10s for next Internet check (#{loop_count})...")
                else:
                    check_interval = 10
                    print(f"\n⏳ Waiting 10s for next Internet check (#{loop_count})...")
                
                if check_interval > 0:
                    time.sleep(check_interval)
                
                if not self.running:
                    break
                
                # เช็ค Internet
                print(f"\n📍 Internet check #{loop_count}:")
                current_status = self.check_internet_connection()
                
                print(f"   📊 Previous: {'✅' if self.internet_available else '❌'} | Current: {'✅' if current_status else '❌'}")
                print(f"   📡 ThingsBoard: {'✅' if current_tb_status else '❌'}")
                
                # เช็คว่าสถานะเปลี่ยนหรือไม่
                if current_status != self.internet_available:
                    if current_status:
                        # Internet กลับมา!
                        print(f"\n🎉 INTERNET RESTORED at {datetime.now().strftime('%H:%M:%S')}!")
                        print(f"🚩 Was unavailable at start: {self.internet_was_unavailable_at_start}")
                        
                        self.internet_available = True
                        
                        # 🆕 รอสักครู่เพื่อให้ Internet stable
                        print("⏳ Waiting 3 seconds for connection to stabilize...")
                        time.sleep(3)
                        
                        # Double-check ก่อน reboot
                        double_check = self.check_internet_connection()
                        if double_check:
                            if self.internet_was_unavailable_at_start:
                                print("🚀 DOUBLE-CONFIRMED: Triggering reboot!")
                                self._immediate_auto_reboot("Internet restored after startup")
                                return
                            else:
                                print("🚀 DOUBLE-CONFIRMED: Triggering reboot!")
                                self._immediate_auto_reboot("Internet connection restored")
                                return
                        else:
                            print("⚠️  Double-check failed - connection not stable yet")
                            self.internet_available = False
                    else:
                        # Internet หาย
                        print(f"\n💔 INTERNET LOST at {datetime.now().strftime('%H:%M:%S')}")
                        print("🔄 Will check every 10 seconds until restored...")
                        self.internet_available = False
                else:
                    status_text = "connected" if current_status else "disconnected"
                    print(f"   📄 Status unchanged: {status_text}")
                
                # บันทึก ThingsBoard status สำหรับรอบต่อไป
                last_thingsboard_status = current_tb_status
                    
            except Exception as e:
                print(f"❌ Internet monitor error: {e}")
                time.sleep(5)

    def _immediate_auto_reboot(self, reason):
        """🆕 Immediate auto reboot - ไม่รอ countdown นาน"""
        try:
            print(f"\n🚀 IMMEDIATE AUTO REBOOT INITIATED")
            print(f"📋 Reason: {reason}")
            print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 🆕 Countdown สั้นลง - เพียง 3 วินาที
            for countdown in [3, 2, 1]:
                if not self.running:
                    print("🛑 Auto-reboot cancelled - system is shutting down")
                    return
                print(f"⏳ Rebooting in {countdown}...")
                time.sleep(1)
            
            print("🔄 Executing immediate reboot...")
            subprocess.run(["reboot"], check=True)
            
            # ปิดระบบเร็วๆ (ไม่รอนาน)
            self.running = False
            
            # 🆕 ปิดเฉพาะสิ่งจำเป็น (ไม่ใช้ self.stop() ที่ช้า)
            try:
                if self.thingsboard_sender:
                    self.thingsboard_sender.close()
                if self.serial_connection:
                    self.serial_connection.close()
            except:
                pass
            
            # รอสั้นๆ
            time.sleep(1)
            
            
            # Execute reboot ทันที
            try:
                print("🚀 Immediate reboot command executing...")
                subprocess.run(["reboot"], check=True)
            except:
                try:
                    subprocess.run(["reboot"], check=True)
                except:
                    try:
                        subprocess.run(["reboot"], check=True)
                    except:
                        print("❌ All reboot methods failed")
                        
        except Exception as e:
            print(f"❌ Error during immediate auto-reboot: {e}")


    def start_internet_monitor(self):
        """เริ่ม Internet monitoring thread"""
        if self.internet_monitor_thread is None or not self.internet_monitor_thread.is_alive():
            self.internet_monitor_thread = threading.Thread(
                target=self.internet_monitor_loop,
                daemon=True
            )
            self.internet_monitor_thread.start()
            print("🌐 Internet monitor started")
        else:
            print("⚠️  Internet monitor already running")

    def stop_internet_monitor(self):
        """หยุด Internet monitoring"""
        if self.internet_monitor_thread and self.internet_monitor_thread.is_alive():
            print("🌐 Stopping Internet monitor...")
            # Monitor จะหยุดเองเมื่อ self.running = False
                
    def start(self):
        """Start the integrated sensor system"""
        print("🌟 Starting Integrated Sensor System...")
        
        try:
            if not self.serial_connection:
                print("❌ No serial connection available!")
                return
            
            print("🌐 Starting Internet connection monitoring...")
            self.start_internet_monitor()

            time.sleep(2)
                
            print("🔧 Starting MCP monitoring...")
            self.enable_all_sensors()
            
            print("⏳ Waiting for sensors to stabilize...")
            time.sleep(3)
            
            # Test communication
            print("🧪 Testing sensor communication...")
            test_data = self.read_all_sensors_sequential()
            responsive_sensors = len([s for s in test_data['sensors'].values() 
                                    if 'status' not in s or s['status'] != 'no_response'])
            print(f"📊 Test complete: {responsive_sensors}/{len(self.sensor_config)} sensors responding")
            
            # Start main loop
            self.sensor_thread = threading.Thread(
                target=self.sensor_reading_loop,
                daemon=True
            )
            self.sensor_thread.start()
            
            print("\n" + "="*60)
            print("✅ SYSTEM STARTED SUCCESSFULLY!")
            #print("📊 Sensor readings will be saved to 'sensor_data.json'")
            print("📡 Data will be sent to ThingsBoard")
            print("🔧 Press Ctrl+C to stop the system")
            print("="*60)
            
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Shutdown signal received...")
            self.stop()
        except Exception as e:
            print(f"❌ System error: {e}")
            self.stop()
            
    def stop(self):
        """Stop the integrated sensor system"""
        print("\n🛑 Stopping Integrated Sensor System...")
        self.running = False
        
        print("🌐 Stopping Internet monitor...")
        # Monitor จะหยุดเองเมื่อ self.running = False
        
        print("🔌 Turning off sensor power...")
        try:
            for port in self.sensor_config.keys():
                try:
                    self.mcp_system.turn_off_sensor(port)
                    print(f"✅ Port {port} power turned off")
                    time.sleep(0.1)
                except Exception as e:
                    print(f"❌ Failed to turn off power for port {port}: {e}")
        except Exception as e:
            print(f"❌ Error during sensor power shutdown: {e}")
        
        # Close ThingsBoard connection
        if self.thingsboard_sender:
            try:
                self.thingsboard_sender.close()
                print("✅ ThingsBoard connection closed")
            except:
                pass
        
        # Close serial connection
        if self.serial_connection:
            try:
                self.serial_connection.close()
                print("✅ Serial connection closed")
            except:
                pass
        
        # Close MCP monitoring
        try:
            if hasattr(self.mcp_system, 'stop_monitoring'):
                self.mcp_system.stop_monitoring()
                print("✅ MCP monitoring stopped")
        except:
            pass
        
        # Close sensor connections
        for port, sensor_info in self.sensors.items():
            if sensor_info and hasattr(sensor_info["instance"], 'close'):
                try:
                    sensor_info["instance"].close()
                    print(f"✅ Port {port} sensor closed")
                except:
                    pass
        
        print("✅ System stopped successfully!")
        print("🔋 All sensor power turned off safely")


    def signal_handler(sig, frame):
        """Handle Ctrl+C signal"""

        if 'system' in globals():
            try:
                system.stop()
            except:
                print("❌ Error during graceful shutdown")
        sys.exit(0)

    def stop(self):
        """Stop the integrated sensor system"""
        print("\n🛑 Stopping Integrated Sensor System...")
        
        self.running = False
        print("🔌 Turning off sensor power...")
        try:

            for port in self.sensor_config.keys():
                try:
                    # ใช้ turn_off_sensor จาก MCP system
                    self.mcp_system.turn_off_sensor(port)
                    print(f"✅ Port {port} power turned off")
                    time.sleep(0.1)  # delay เล็กน้อยระหว่าง port
                except Exception as e:
                    print(f"❌ Failed to turn off power for port {port}: {e}")
        except Exception as e:
            print(f"❌ Error during sensor power shutdown: {e}")
        
        # Close ThingsBoard connection
        if self.thingsboard_sender:
            try:
                self.thingsboard_sender.close()
                print("✅ ThingsBoard connection closed")
            except:
                pass
        
        # Close serial connection
        if self.serial_connection:
            try:
                self.serial_connection.close()
                print("✅ Serial connection closed")
            except:
                pass
                
        # ปิด MCP monitoring (ถ้ามี)
        try:
            if hasattr(self.mcp_system, 'stop_monitoring'):
                self.mcp_system.stop_monitoring()
            print("✅ MCP monitoring stopped")
        except:
            pass
        
        # Close sensor connections
        for port, sensor_info in self.sensors.items():
            if sensor_info and hasattr(sensor_info["instance"], 'close'):
                try:
                    sensor_info["instance"].close()
                    print(f"✅ Port {port} sensor closed")
                except:
                    pass
                    
        print("✅ System stopped successfully!")
        print("🔋 All sensor power turned off safely")

def main():
    signal.signal(signal.SIGINT, IntegratedSensorSystem.signal_handler)
    signal.signal(signal.SIGTERM, IntegratedSensorSystem.signal_handler)
    
    print("=" * 60)
    print("🌍 INTEGRATED SENSOR SYSTEM")
    print("   Luckfox Pico ProMax Multi-Sensor Controller")
    print("   RS485 Sequential + ThingsBoard Integration")
    print("=" * 60)
    IntegratedSensorSystem.test_sensor_power_control
    
    # สามารถเปลี่ยน Control Box ID ได้ที่นี่
    # system = IntegratedSensorSystem(control_box_id="SLXA1250004")  # สำหรับ box อื่น
    global system
    system = IntegratedSensorSystem(control_box_id="SLXA1250006")
    
    try:
        system.start()
    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received...")
        system.stop()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        system.stop()
    finally:
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()
