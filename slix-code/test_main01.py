#!/usr/bin/env python
import sys
import os
import time
import threading
import json
from datetime import datetime

# Import MCP Control System
sys.path.append(os.path.dirname(__file__))
from test_mcp01 import SensorControlSystem

# Import Sensor Classes
from class_soil_modbus import SensorSoilMoistureTemp
from class_solar_modbus import SensorPyranometer
from class_wind_modbus import SensorWindSpeedDirection

class SensorManagementSystem:
    def __init__(self):
        # Initialize MCP Control System
        print("Initializing MCP Control System...")
        self.mcp_system = SensorControlSystem()
        
        # Sensor type definitions
        self.sensor_types = {
            'soil': {
                'class': SensorSoilMoistureTemp,
                'address_range': list(range(2, 12)),  # 1-12
                'default_address': 1,
                'used_addresses': []
            },
            'solar': {
                'class': SensorPyranometer,
                'address_range': list(range(14, 24)),  # 13-24 (0x0C-0x17)
                'default_address': 13,
                'used_addresses': []
            },
            'wind': {
                'class': SensorWindSpeedDirection,
                'address_range': list(range(26, 36)),  # 25-36 (0x19-0x24)
                'default_address': 25,
                'used_addresses': []
            }
        }
        
        # System status
        self.connected_sensors = {}  # {port: {'type': 'soil', 'address': 5, 'instance': obj}}
        self.sensor_count = 0
        self.scanning_in_progress = False
        self.data_reading_active = False
        
        # Files for address management
        self.address_file = "sensor_addresses.json"
        self.load_used_addresses()
        self.startup_validation()
        
        # Threading
        self.system_running = False
        self.scan_thread = None
        self.data_thread = None
        
    def load_used_addresses(self):
        """โหลด address ที่ใช้แล้วจากไฟล์"""
        try:
            if os.path.exists(self.address_file):
                with open(self.address_file, 'r') as f:
                    data = json.load(f)
                    for sensor_type in self.sensor_types:
                        if sensor_type in data:
                            self.sensor_types[sensor_type]['used_addresses'] = data[sensor_type]
                print(f"Loaded address data: {data}")
            else:
                print("No existing address file found, starting fresh")
        except Exception as e:
            print(f"Error loading address file: {e}")
    
    def save_used_addresses(self):
        """บันทึก address ที่ใช้แล้วลงไฟล์"""
        try:
            data = {}
            for sensor_type, info in self.sensor_types.items():
                data[sensor_type] = info['used_addresses']
            
            with open(self.address_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved address data: {data}")
        except Exception as e:
            print(f"Error saving address file: {e}")
    
    def get_next_available_address(self, sensor_type):
        """หา address ถัดไปที่ว่างสำหรับ sensor type นี้"""
        used = self.sensor_types[sensor_type]['used_addresses']
        address_range = self.sensor_types[sensor_type]['address_range']
        
        for addr in address_range:
            if addr not in used:
                return addr
        return None
    
    def hex_address(self, addr):
        """แปลง address เป็น hex string สำหรับ command"""
        return f"{addr:02X}"
    
    def scan_sensor_type(self, sensor_type, port_num):

        self.mcp_system.turn_off_sensor(port_num)
        time.sleep(0.5)
        self.mcp_system.turn_on_all_sensors()
        time.sleep(1)

        """สแกนหา sensor ชนิดนี้ที่ port นี้"""
        print(f"Scanning {sensor_type} sensor at port {port_num}...")
        
        sensor_info = self.sensor_types[sensor_type]
        sensor_class = sensor_info['class']
        default_address = sensor_info['default_address']  # ใช้ default address ในการ scan
        
        try:
            print(f"Trying default address {default_address} (0x{default_address:02X}) for {sensor_type} sensor...")
            
            # สร้าง sensor instance ด้วย default address เท่านั้น
            sensor = sensor_class(port="/dev/ttyS2", slave_address=default_address)
            
            # ลองอ่านค่า
            if sensor_type == 'soil':
                data = sensor.read_data(addr=default_address)
            elif sensor_type == 'solar':
                data = sensor.read_radiation(addr=default_address)
            elif sensor_type == 'wind':
                data = sensor.read_wind(addr=default_address)
            
            if data is not None:
                print(f"✓ Found {sensor_type} sensor at default address {default_address} (0x{default_address:02X}) on port {port_num}")
                sensor.close()
                return default_address
            
            sensor.close()
            
        except Exception as e:
            print(f"Error testing default address {default_address} (0x{default_address:02X}): {e}")
            if 'sensor' in locals():
                sensor.close()

        finally:
            self.mcp_system.turn_off_sensor(port_num)
        
        print(f"[DEBUG] {sensor_type.upper()} at port {port_num}, got data: {data}")
        print(f"❌ No {sensor_type} sensor found at port {port_num}")
        return None
  
    
    def setup_new_sensor(self, sensor_type, current_address, port_num):
        """ตั้งค่า address ใหม่ให้กับ sensor"""
        print(f"Setting up new {sensor_type} sensor...")
        
        # ตรวจสอบว่า current_address เป็น default address หรือไม่
        default_address = self.sensor_types[sensor_type]['default_address']
        if current_address != default_address:
            print(f"⚠️  Warning: Expected default address {default_address} (0x{default_address:02X}), but found {current_address} (0x{current_address:02X})")
        
        # หา address ใหม่ที่ว่าง (จาก address_range ที่ไม่รวม default)
        new_address = self.get_next_available_address(sensor_type)
        if new_address is None:
            print(f"❌ No available address for {sensor_type} sensor!")
            return None
        
        # ตรวจสอบว่า new_address ไม่ใช่ default address
        if new_address == default_address:
            print(f"❌ Error: Trying to use default address {default_address} as working address!")
            return None
        
        try:
            # สร้าง sensor instance ด้วย current address (default)
            sensor_class = self.sensor_types[sensor_type]['class']
            sensor = sensor_class(port="/dev/ttyS2", slave_address=current_address)
            
            # Set address ใหม่
            print(f"Setting {sensor_type} address from {current_address} (0x{current_address:02X}) to {new_address} (0x{new_address:02X})")
            sensor.set_address(new_address)
            sensor.close()
            
            # Restart sensor (ตัดไฟ -> เปิดใหม่)
            print(f"Restarting sensor at port {port_num}...")
            self.mcp_system.turn_off_sensor(port_num)
            time.sleep(2)
            self.mcp_system.turn_on_all_sensors()
            time.sleep(3)
            
            # เช็คว่า address ใหม่ทำงานได้
            sensor_new = sensor_class(port="/dev/ttyS2", slave_address=new_address)
            if sensor_type == 'soil':
                test_data = sensor_new.read_data(addr=new_address)
            elif sensor_type == 'solar':
                test_data = sensor_new.read_radiation(addr=new_address)
            elif sensor_type == 'wind':
                test_data = sensor_new.read_wind(addr=new_address)
            
            if test_data is not None:
                # บันทึก address ใหม่
                self.sensor_types[sensor_type]['used_addresses'].append(new_address)
                self.save_used_addresses()
                
                # เก็บข้อมูล sensor
                self.connected_sensors[port_num] = {
                    'type': sensor_type,
                    'address': new_address,
                    'instance': sensor_new
                }
                
                print(f"✅ {sensor_type} sensor setup complete at port {port_num}, address {new_address} (0x{new_address:02X})")
                return new_address
            else:
                print(f"❌ Failed to verify new address for {sensor_type} sensor")
                sensor_new.close()
                return None
                
        except Exception as e:
            print(f"❌ Error setting up {sensor_type} sensor: {e}")
            return None
        
    
    def resolve_address_conflict_v2(self, port_num, conflicted_address):
        """
        แก้ไข address conflict โดยทดสอบเซ็นเซอร์จริงอีกครั้ง
        โดยใช้วิธีปิด-เปิด sensor แต่ละพอร์ต
        """
        print(f"🔧 Resolving address conflict for port {port_num}, address {conflicted_address}...")
        
        try:
            # วิธีแยกทดสอบ: ปิดพอร์ตอื่นๆ ทีละอัน
            ports_to_test = [p for p in range(1, 13) if p != port_num and 
                            p in self.mcp_system.sensor_status and 
                            self.mcp_system.sensor_status[p] == 0]
            
            # ปิดพอร์ตอื่นๆ ชั่วคราว
            for p in ports_to_test:
                self.mcp_system.turn_off_sensor(p)
            time.sleep(1)
            
            # ทดสอบทุกชนิดเซ็นเซอร์ที่ address นี้
            test_results = []
            
            for sensor_type, info in self.sensor_types.items():
                try:
                    sensor_class = info['class']
                    sensor = sensor_class(port="/dev/ttyS2", slave_address=conflicted_address)
                    
                    data = None
                    if sensor_type == 'soil':
                        data = sensor.read_data(addr=conflicted_address)
                    elif sensor_type == 'solar':
                        data = sensor.read_radiation(addr=conflicted_address)
                    elif sensor_type == 'wind':
                        data = sensor.read_wind(addr=conflicted_address)
                    
                    sensor.close()
                    
                    if data is not None:
                        confidence = self.analyze_data_confidence(sensor_type, data)
                        if confidence > 0.5:
                            test_results.append({
                                'type': sensor_type,
                                'address': conflicted_address,
                                'confidence': confidence,
                                'data': data
                            })
                            print(f"  ✅ {sensor_type.upper()} test: confidence {confidence:.2f}")
                        else:
                            print(f"  ⚠️  {sensor_type.upper()} test: low confidence {confidence:.2f}")
                    else:
                        print(f"  ❌ {sensor_type.upper()} test: no data")
                        
                except Exception as e:
                    print(f"  ❌ {sensor_type.upper()} test failed: {e}")
            
            # เลือกผลลัพธ์ที่ดีที่สุด
            if len(test_results) == 1:
                result = test_results[0]
                print(f"  🎯 Conflict resolved: {result['type'].upper()} with confidence {result['confidence']:.2f}")
                return {
                    'type': result['type'],
                    'address': result['address'],
                    'data': result['data'],
                    'is_used': conflicted_address in self.sensor_types[result['type']]['used_addresses']
                }
            elif len(test_results) > 1:
                # เลือกที่มี confidence สูงสุด
                best = max(test_results, key=lambda x: x['confidence'])
                print(f"  🎯 Multiple matches, chose: {best['type'].upper()} (highest confidence: {best['confidence']:.2f})")
                return {
                    'type': best['type'],
                    'address': best['address'],
                    'data': best['data'],
                    'is_used': conflicted_address in self.sensor_types[best['type']]['used_addresses']
                }
            else:
                print(f"  ❌ No valid sensor found at address {conflicted_address}")
                return None
                
        finally:
            # เปิดพอร์ตที่ปิดไว้กลับคืน
            self.mcp_system.turn_on_all_sensors()
            time.sleep(1)

    def process_single_sensor(self, port_num, sensor_result):
        """ประมวลผล sensor เดี่ยวที่พบ"""
        sensor_type = sensor_result['type']
        found_address = sensor_result['address']
        is_used = sensor_result['used']
        
        if is_used:
            # Address นี้ใช้แล้ว - เป็น sensor เก่า
            print(f"🔄 Existing {sensor_type} sensor reconnected at address {found_address}")
            sensor_class = self.sensor_types[sensor_type]['class']
            sensor_instance = sensor_class(port="/dev/ttyS2", slave_address=found_address)
            self.connected_sensors[port_num] = {
                'type': sensor_type,
                'address': found_address,
                'instance': sensor_instance
            }
        else:
            # Address นี้ยังไม่ใช้ - setup ใหม่
            result = self.setup_new_sensor(sensor_type, found_address, port_num)
            if result is None:
                print(f"❌ Failed to setup {sensor_type} sensor at port {port_num}")
    
    def read_all_sensors(self):
        """อ่านค่าจาก sensor ทุกตัว"""
        if not self.connected_sensors:
            return
        
        print(f"\n📡 Reading data from {len(self.connected_sensors)} sensors...")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for port_num, sensor_info in self.connected_sensors.items():
            try:
                sensor_type = sensor_info['type']
                address = sensor_info['address']
                instance = sensor_info['instance']
                
                # อ่านค่าตามชนิด sensor
                if sensor_type == 'soil':
                    data = instance.read_data()
                    if data:
                        print(f"🌱 Port {port_num} ({sensor_type}, addr:{address}): Temp: {data['temperature']:.1f}°C, Moisture: {data['moisture']:.1f}%")
                elif sensor_type == 'solar':
                    data = instance.read_radiation()
                    if data:
                        print(f"☀️  Port {port_num} ({sensor_type}, addr:{address}): Radiation: {data['radiation']} W/m²")
                elif sensor_type == 'wind':
                    data = instance.read_wind()
                    if data:
                        print(f"💨 Port {port_num} ({sensor_type}, addr:{address}): Speed: {data['wind_speed']} m/s, Direction: {data['wind_direction']}°")
                
            except Exception as e:
                print(f"❌ Failed to read port {port_num}: {e}")
    
    def data_reading_loop(self):
        """Loop สำหรับอ่านค่า sensor ทุก 5 นาที"""
        print("📊 Data reading loop started...")
        
        while self.system_running:
            try:
                if self.connected_sensors:
                    #self.read_all_sensors()
                    self.read_all_sensors_in_range()
                # รอ 5 นาที (300 วินาที)
                for i in range(300):
                    if not self.system_running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"❌ Data reading loop error: {e}")
                time.sleep(30)

    def start_system(self):
        self.running = True
        self.mcp_system.turn_on_all_sensors()
        print("Turning ON all sensor power supplies...")
        time.sleep(1)
        print("All sensors powered ON!\n")
    
    def stop_system(self):
        """หยุดระบบ"""
        print("\n🛑 Stopping Sensor Management System...")
        
        # หยุด threads
        self.system_running = False
        
        # ปิด sensor instances
        for port_num, sensor_info in self.connected_sensors.items():
            try:
                sensor_info['instance'].close()
            except:
                pass
        
        # หยุด MCP system
        self.mcp_system.stop_system()
        
        print("✅ System stopped successfully!")
    

    def read_all_sensors_in_range(self):
        """อ่านค่าจาก sensor ทุก address ในขอบเขตที่กำหนด"""
        print(f"\n🔍 Reading all sensors in defined address ranges...")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        all_sensor_data = {
            "timestamp": timestamp,
            "sensors": []
        }
        
        # อ่านจากทุกประเภท sensor
        for sensor_type, info in self.sensor_types.items():
            sensor_class = info['class']
            address_range = info['address_range']
            used_addresses = info['used_addresses']
            
            print(f"\n🔍 Scanning {sensor_type.upper()} sensors (addresses: {address_range})...")
            
            for address in address_range:
                try:
                    # สร้าง sensor instance
                    sensor = sensor_class(port="/dev/ttyS2", slave_address=address)
                    
                    # อ่านค่าตามชนิด sensor
                    data = None
                    if sensor_type == 'soil':
                        data = sensor.read_data(addr=address)
                    elif sensor_type == 'solar':
                        data = sensor.read_radiation(addr=address)
                    elif sensor_type == 'wind':
                        data = sensor.read_wind(addr=address)
                    
                    if data is not None:
                        # หา port ที่ sensor นี้เชื่อมต่ออยู่
                        connected_port = None
                        for port_num, sensor_info in self.connected_sensors.items():
                            if sensor_info['address'] == address and sensor_info['type'] == sensor_type:
                                connected_port = port_num
                                break
                        
                        # เตรียมข้อมูลสำหรับ JSON
                        sensor_record = {
                            "sensor_type": sensor_type,
                            "address": address,
                            "address_hex": f"0x{address:02X}",
                            "port": connected_port,
                            "is_saved_address": address in used_addresses,
                            "data": data,
                            "read_time": timestamp
                        }
                        
                        all_sensor_data["sensors"].append(sensor_record)
                        
                        # แสดงผลแต่ละตัว
                        port_str = f"Port {connected_port}" if connected_port else "Unknown Port"
                        saved_str = "✅ Saved" if address in used_addresses else "🆕 New"
                        
                        if sensor_type == 'soil':
                            print(f"🌱 {sensor_type.upper()} | Addr: {address}(0x{address:02X}) | {port_str} | {saved_str}")
                            print(f"   Data: Temp: {data.get('temperature', 'N/A')}°C, Moisture: {data.get('moisture', 'N/A')}%")
                        elif sensor_type == 'solar':
                            print(f"☀️  {sensor_type.upper()} | Addr: {address}(0x{address:02X}) | {port_str} | {saved_str}")
                            print(f"   Data: Radiation: {data.get('radiation', 'N/A')} W/m²")
                        elif sensor_type == 'wind':
                            print(f"💨 {sensor_type.upper()} | Addr: {address}(0x{address:02X}) | {port_str} | {saved_str}")
                            print(f"   Data: Speed: {data.get('wind_speed', 'N/A')} m/s, Direction: {data.get('wind_direction', 'N/A')}°")
                    
                    sensor.close()
                    
                except Exception as e:
                    # ไม่แสดง error เพราะปกติจะมี address ที่ไม่มี sensor ตอบกลับ
                    pass
        
        # แสดงผล JSON
        print(f"\n📊 Complete JSON Result:")
        print("=" * 80)
        json_output = json.dumps(all_sensor_data, indent=2, ensure_ascii=False)
        print(json_output)
        
    def test_specific_sensor_by_address(self, sensor_type, address):
        """ทดสอบเซ็นเซอร์เฉพาะตัวตาม address เพื่อดูว่าทำงานหรือเสีย"""
        print(f"\n🔍 Testing {sensor_type.upper()} sensor at address {address} (0x{address:02X})...")
        
        try:
            sensor_class = self.sensor_types[sensor_type]['class']
            sensor = sensor_class(port="/dev/ttyS2", slave_address=address)
            
            # ลองอ่านค่า
            data = None
            if sensor_type == 'soil':
                data = sensor.read_data(addr=address)
            elif sensor_type == 'solar':
                data = sensor.read_radiation(addr=address)
            elif sensor_type == 'wind':
                data = sensor.read_wind(addr=address)
            
            sensor.close()
            
            if data is not None:
                print(f"✅ Sensor responds normally")
                print(f"   Data: {data}")
                return True
            else:
                print(f"❌ Sensor not responding or faulty")
                return False
                
        except Exception as e:
            print(f"❌ Error testing sensor: {e}")
            return False

    def diagnose_faulty_sensors(self):
        """วินิจฉัยเซ็นเซอร์ที่อาจเสีย"""
        print(f"\n🏥 Diagnosing Faulty Sensors...")
        print("=" * 50)
        
        faulty_sensors = []
        
        for sensor_type, info in self.sensor_types.items():
            used_addresses = info['used_addresses']
            
            for address in used_addresses:
                # เช็คว่าเซ็นเซอร์นี้เชื่อมต่ออยู่หรือไม่
                is_connected = any(
                    sensor_info['address'] == address and sensor_info['type'] == sensor_type
                    for sensor_info in self.connected_sensors.values()
                )
                
                if not is_connected:
                    print(f"\n🔍 Testing disconnected {sensor_type.upper()} sensor (Address: {address})...")
                    
                    # ทดสอบทุกพอร์ตเพื่อหาว่าเซ็นเซอร์อยู่ที่ไหน
                    found_port = None
                    for port_num in range(1, 13):
                        # เปิดเฉพาะพอร์ตนี้
                        self.mcp_system.turn_off_sensor(port_num)
                        time.sleep(0.5)
                        self.mcp_system.turn_on_all_sensors()
                        time.sleep(1)
                        
                        # ทดสอบ
                        if self.test_specific_sensor_by_address(sensor_type, address):
                            found_port = port_num
                            print(f"   Found at Port {port_num}")
                            break
                        
                        self.mcp_system.turn_off_sensor(port_num)
                    
                    if found_port is None:
                        faulty_sensors.append({
                            'type': sensor_type,
                            'address': address,
                            'status': 'Not responding - possibly faulty'
                        })
        
        if faulty_sensors:
            print(f"\n❌ Faulty Sensors Detected:")
            for sensor in faulty_sensors:
                print(f"  • {sensor['type'].upper()} (Address: {sensor['address']}/0x{sensor['address']:02X}) - {sensor['status']}")
        else:
            print(f"\n✅ All registered sensors are working normally!")
        
        return faulty_sensors
    def detect_sensor_by_data_pattern(self, port_num):
        """
        ปรับปรุงการตรวจจับเซ็นเซอร์โดยตรวจสอบ address ที่ไม่ซ้ำกัน
        และให้ความสำคัญกับเซ็นเซอร์ที่บันทึกไว้แล้ว
        """
        print(f"🧪 Analyzing sensor data pattern at port {port_num}...")
        
        # สร้างรายการ address ที่จะทดสอบ โดยแยกตาม priority
        addresses_to_test = []
        
        # Priority 1: Address ที่บันทึกไว้แล้ว (used_addresses)
        for sensor_type, info in self.sensor_types.items():
            for addr in info['used_addresses']:
                addresses_to_test.append((addr, sensor_type, True, 'saved'))
        
        # Priority 2: Default addresses ที่ยังไม่ได้ใช้
        for sensor_type, info in self.sensor_types.items():
            default_addr = info['default_address']
            # เช็คว่า default address นี้ยังไม่อยู่ในรายการทดสอบ
            if not any(addr == default_addr for addr, _, _, _ in addresses_to_test):
                addresses_to_test.append((default_addr, sensor_type, False, 'default'))
        
        print(f"  Testing {len(addresses_to_test)} addresses...")
        
        detection_results = []

        for address, expected_type, is_used, test_type in addresses_to_test:
            print(f"  Testing {test_type} address {address} (0x{address:02X}) for {expected_type.upper()}...")

            try:
                sensor_class = self.sensor_types[expected_type]['class']
                sensor = sensor_class(port="/dev/ttyS2", slave_address=address)

                # อ่านข้อมูลตามชนิดเซ็นเซอร์ที่คาดหวัง
                data = None
                if expected_type == 'soil':
                    data = sensor.read_data(addr=address)
                elif expected_type == 'solar':
                    data = sensor.read_radiation(addr=address)
                elif expected_type == 'wind':
                    data = sensor.read_wind(addr=address)

                sensor.close()

                if data is not None:
                    confidence = self.analyze_data_confidence(expected_type, data)
                    
                    # ให้คะแนนพิเศษสำหรับ saved address
                    if is_used and test_type == 'saved':
                        confidence += 0.2  # bonus สำหรับ address ที่บันทึกไว้
                    
                    if confidence > 0.5:
                        detection_results.append({
                            'address': address,
                            'detected_type': expected_type,
                            'confidence': confidence,
                            'data': data,
                            'is_used_address': is_used,
                            'test_type': test_type
                        })
                        print(f"    ✅ {expected_type.upper()} responds (confidence: {confidence:.2f})")
                    else:
                        print(f"    ⚠️  {expected_type.upper()} responds but low confidence ({confidence:.2f})")
                else:
                    print(f"    ❌ {expected_type.upper()} no response")

            except Exception as e:
                print(f"    ❌ Error testing {expected_type.upper()} at address {address}: {e}")
                continue

        # เลือกผลลัพธ์ที่ดีที่สุด
        if detection_results:
            # เรียงตาม confidence และให้ priority กับ saved address
            detection_results.sort(key=lambda x: (x['test_type'] == 'saved', x['confidence']), reverse=True)
            
            best_result = detection_results[0]
            print(f"  🎯 Best match: {best_result['detected_type'].upper()} at address {best_result['address']} "
                f"(confidence: {best_result['confidence']:.2f}, type: {best_result['test_type']})")
            
            return {
                'type': best_result['detected_type'],
                'address': best_result['address'],
                'data': best_result['data'],
                'is_used': best_result['is_used_address']
            }

        print("  ❌ No matching sensor found.")
        return None


    def analyze_data_confidence(self, sensor_type, data):
        """
        วิเคราะห์ความเชื่อมั่นว่าข้อมูลนี้มาจากเซ็นเซอร์ชนิดที่คาดหวัง
        """
        if not data:
            return 0.0
        
        confidence = 0.0
        
        if sensor_type == 'soil':
            # ตรวจสอบว่ามีฟิลด์ที่เหมาะสมหรือไม่
            if 'temperature' in data and 'moisture' in data:
                confidence += 0.5
                
                # ตรวจสอบช่วงค่าที่สมเหตุสมผล
                temp = data.get('temperature', 0)
                moisture = data.get('moisture', 0)
                
                if -40 <= temp <= 80:  # อุณหภูมิสมเหตุสมผล
                    confidence += 0.3
                if 0 <= moisture <= 100:  # ความชื้นสมเหตุสมผล
                    confidence += 0.3
                    
        elif sensor_type == 'solar':
            if 'radiation' in data:
                confidence += 0.5
                
                radiation = data.get('radiation', 0)
                if 0 <= radiation <= 2000:  # Solar radiation สมเหตุสมผล
                    confidence += 0.5
                    
        elif sensor_type == 'wind':
            if 'wind_speed' in data and 'wind_direction' in data:
                confidence += 0.5
                
                speed = data.get('wind_speed', 0)
                direction = data.get('wind_direction', 0)
                
                if 0 <= speed <= 100:  # ความเร็วลมสมเหตุสมผล
                    confidence += 0.25
                if 0 <= direction <= 359:  # ทิศทางลมสมเหตุสมผล
                    confidence += 0.25
        
        return min(confidence, 1.0)  # จำกัดไม่เกิน 1.0

    def reconnect_existing_sensor(self, port_num, sensor_info):
        """เชื่อมต่อเซ็นเซอร์เก่าที่ตรวจพบใหม่"""
        sensor_type = sensor_info['type']
        address = sensor_info['address']
        
        try:
            sensor_class = self.sensor_types[sensor_type]['class']
            sensor_instance = sensor_class(port="/dev/ttyS2", slave_address=address)
            
            self.connected_sensors[port_num] = {
                'type': sensor_type,
                'address': address,
                'instance': sensor_instance
            }
            
            print(f"✅ Reconnected {sensor_type.upper()} sensor at port {port_num}, address {address}")
            
        except Exception as e:
            print(f"❌ Failed to reconnect sensor: {e}")


    # เพิ่มฟังก์ชันช่วยในการดีบัก
    def debug_all_addresses(self):
        """ดีบักโดยทดสอบทุก address ที่เป็นไปได้"""
        print("\n🔍 DEBUG: Testing all possible addresses...")
        
        all_test_addresses = []
        for sensor_type, info in self.sensor_types.items():
            all_test_addresses.extend(info['used_addresses'])
            all_test_addresses.append(info['default_address'])
        
        # ลบตัวซ้ำ
        all_test_addresses = list(set(all_test_addresses))
        all_test_addresses.sort()
        
        for addr in all_test_addresses:
            print(f"\n📍 Testing address {addr} (0x{addr:02X}):")
            
            for sensor_type, info in self.sensor_types.items():
                sensor_class = info['class']
                
                try:
                    sensor = sensor_class(port="/dev/ttyS2", slave_address=addr)
                    
                    data = None
                    if sensor_type == 'soil':
                        data = sensor.read_data(addr=addr)
                    elif sensor_type == 'solar':
                        data = sensor.read_radiation(addr=addr)
                    elif sensor_type == 'wind':
                        data = sensor.read_wind(addr=addr)
                    
                    sensor.close()
                    
                    if data:
                        confidence = self.analyze_data_confidence(sensor_type, data)
                        print(f"  {sensor_type.upper()}: ✅ Responds (confidence: {confidence:.2f}) - {data}")
                    else:
                        print(f"  {sensor_type.upper()}: ❌ No response")
                        
                except Exception as e:
                    print(f"  {sensor_type.upper()}: ❌ Error - {e}")

    def validate_sensor_addresses(self):
        """
        ตรวจสอบความถูกต้องของ address ที่บันทึกไว้
        """
        print("\n🔍 Validating saved sensor addresses...")
        
        invalid_addresses = []
        
        for sensor_type, info in self.sensor_types.items():
            used_addresses = info['used_addresses'].copy()
            
            for address in used_addresses:
                print(f"  Validating {sensor_type.upper()} address {address}...")
                
                # ปิดเซ็นเซอร์ทั้งหมดก่อน
                for p in range(1, 13):
                    self.mcp_system.turn_off_sensor(p)
                time.sleep(0.5)
                self.mcp_system.turn_on_all_sensors()
                time.sleep(1)
                
                try:
                    sensor_class = info['class']
                    sensor = sensor_class(port="/dev/ttyS2", slave_address=address)
                    
                    data = None
                    if sensor_type == 'soil':
                        data = sensor.read_data(addr=address)
                    elif sensor_type == 'solar':
                        data = sensor.read_radiation(addr=address)
                    elif sensor_type == 'wind':
                        data = sensor.read_wind(addr=address)
                    
                    sensor.close()
                    
                    if data is None:
                        print(f"    ❌ Invalid: No response from {sensor_type.upper()} at address {address}")
                        invalid_addresses.append((sensor_type, address))
                    else:
                        confidence = self.analyze_data_confidence(sensor_type, data)
                        if confidence < 0.5:
                            print(f"    ⚠️  Suspicious: Low confidence ({confidence:.2f}) for {sensor_type.upper()} at address {address}")
                        else:
                            print(f"    ✅ Valid: {sensor_type.upper()} at address {address}")
                            
                except Exception as e:
                    print(f"    ❌ Error validating {sensor_type.upper()} at address {address}: {e}")
                    invalid_addresses.append((sensor_type, address))
        
        # ลบ address ที่ไม่ถูกต้อง
        if invalid_addresses:
            print(f"\n🧹 Cleaning up {len(invalid_addresses)} invalid addresses...")
            for sensor_type, address in invalid_addresses:
                if address in self.sensor_types[sensor_type]['used_addresses']:
                    self.sensor_types[sensor_type]['used_addresses'].remove(address)
                    print(f"  Removed {sensor_type.upper()} address {address}")
            
            self.save_used_addresses()
            print("✅ Address cleanup completed")
        else:
            print("✅ All saved addresses are valid")


    def startup_validation(self):
        """
        ตรวจสอบระบบเมื่อเริ่มต้น
        """
        print("\n🔧 Running startup validation...")
        
        # ตรวจสอบไฟล์ address
        self.validate_sensor_addresses()
        
        # แสดงสถานะเริ่มต้น
        print(f"\n📊 Startup Status:")
        for sensor_type, info in self.sensor_types.items():
            used_count = len(info['used_addresses'])
            available_count = len(info['address_range']) - used_count
            print(f"  {sensor_type.upper()}: {used_count} registered, {available_count} available")
            if info['used_addresses']:
                print(f"    Registered addresses: {info['used_addresses']}")


    def initial_comprehensive_scan(self):
        """
        สแกนเริ่มต้นแบบละเอียด - เปิดไฟทีละพอร์ตเพื่อแยกแยะเซ็นเซอร์
        ใช้เฉพาะตอนเริ่มโปรแกรม
        """
        print("\n🔍 Starting Initial Comprehensive Scan (Port by Port)")
        print("=" * 70)
        
        # ปิดเซ็นเซอร์ทั้งหมดก่อน
        print("🔴 Turning off all sensors...")
        for port in range(1, 13):
            self.mcp_system.turn_off_sensor(port)
        time.sleep(2)
        
        initial_detected_sensors = {}
        
        # สแกนทีละพอร์ต
        for port_num in range(1, 13):
            print(f"\n📌 Scanning Port {port_num}...")
            
            # เปิดเฉพาะพอร์ตนี้
            print(f"🟢 Turning ON Port {port_num}")
            self.mcp_system.turn_on_all_sensors()  # เปิดทั้งหมดก่อน
            time.sleep(0.5)
            
            # ปิดพอร์ตอื่นๆ ยกเว้นพอร์ตที่ต้องการ
            for other_port in range(1, 13):
                if other_port != port_num:
                    self.mcp_system.turn_off_sensor(other_port)
            time.sleep(2)
            
            # ตรวจสอบว่ามีเซ็นเซอร์หรือไม่
            detected_sensor = self.detect_sensor_by_data_pattern_initial(port_num)
            
            if detected_sensor:
                sensor_type = detected_sensor['type']
                address = detected_sensor['address']
                is_default = (address == self.sensor_types[sensor_type]['default_address'])
                
                print(f"✅ Found {sensor_type.upper()} sensor at Port {port_num}")
                print(f"   Address: {address} (0x{address:02X}) {'[DEFAULT]' if is_default else '[CUSTOM]'}")
                
                if is_default:
                    # เป็น default address - ต้องเปลี่ยนเป็น address ใหม่
                    print(f"🔧 Setting up new address for {sensor_type.upper()} sensor...")
                    new_address = self.setup_new_sensor_initial(sensor_type, address, port_num)
                    if new_address:
                        initial_detected_sensors[port_num] = {
                            'type': sensor_type,
                            'address': new_address,
                            'status': 'new_setup'
                        }
                        print(f"✅ Setup complete - New address: {new_address} (0x{new_address:02X})")
                    else:
                        print(f"❌ Failed to setup new address")
                else:
                    # มี address custom แล้ว - เป็นเซ็นเซอร์เก่า
                    initial_detected_sensors[port_num] = {
                        'type': sensor_type,
                        'address': address,
                        'status': 'existing'
                    }
                    print(f"🔄 Existing sensor reconnected")
            else:
                print(f"⚫ No sensor detected at Port {port_num}")
            
            # ปิดพอร์ตนี้
            print(f"🔴 Turning OFF Port {port_num}")
            self.mcp_system.turn_off_sensor(port_num)
            time.sleep(0.5)
        
        # เปิดเซ็นเซอร์ทั้งหมดกลับคืน
        print(f"\n🟢 Turning ON all detected sensors...")
        self.mcp_system.turn_on_all_sensors()
        time.sleep(3)
        
        # สร้าง sensor instances สำหรับเซ็นเซอร์ที่พบ
        print(f"\n📦 Creating sensor instances...")
        for port_num, sensor_info in initial_detected_sensors.items():
            try:
                sensor_type = sensor_info['type']
                address = sensor_info['address']
                
                sensor_class = self.sensor_types[sensor_type]['class']
                sensor_instance = sensor_class(port="/dev/ttyS2", slave_address=address)
                
                self.connected_sensors[port_num] = {
                    'type': sensor_type,
                    'address': address,
                    'instance': sensor_instance
                }
                
                print(f"✅ Port {port_num}: {sensor_type.upper()} (Address: {address}) - Instance created")
                
            except Exception as e:
                print(f"❌ Failed to create instance for Port {port_num}: {e}")
        
        # สรุปผลลัพธ์
        print(f"\n📊 Initial Scan Summary:")
        print("=" * 50)
        print(f"🟢 Total sensors detected: {len(initial_detected_sensors)}")
        print(f"📦 Sensor instances created: {len(self.connected_sensors)}")
        
        for port_num, sensor_info in initial_detected_sensors.items():
            status_icon = "🆕" if sensor_info['status'] == 'new_setup' else "🔄"
            print(f"  {status_icon} Port {port_num}: {sensor_info['type'].upper()} (Address: {sensor_info['address']})")
        
        self.sensor_count = len(self.connected_sensors)
        return len(initial_detected_sensors)


    def detect_sensor_by_data_pattern_initial(self, port_num):
        """
        ตรวจจับเซ็นเซอร์สำหรับ initial scan - ทดสอบทั้ง default และ used addresses
        """
        print(f"  🧪 Analyzing sensor at port {port_num}...")
        
        # รายการ address ที่จะทดสอบ (ทั้ง default และ used)
        addresses_to_test = []
        
        # เพิ่ม default addresses
        for sensor_type, info in self.sensor_types.items():
            addresses_to_test.append((info['default_address'], sensor_type, False, 'default'))
        
        # เพิ่ม used addresses
        for sensor_type, info in self.sensor_types.items():
            for addr in info['used_addresses']:
                if addr != info['default_address']:  # ไม่ซ้ำกับ default
                    addresses_to_test.append((addr, sensor_type, True, 'used'))
        
        detection_results = []
        
        for address, expected_type, is_used, addr_type in addresses_to_test:
            try:
                sensor_class = self.sensor_types[expected_type]['class']
                sensor = sensor_class(port="/dev/ttyS2", slave_address=address)
                
                data = None
                if expected_type == 'soil':
                    data = sensor.read_data(addr=address)
                elif expected_type == 'solar':
                    data = sensor.read_radiation(addr=address)
                elif expected_type == 'wind':
                    data = sensor.read_wind(addr=address)
                
                sensor.close()
                
                if data is not None:
                    confidence = self.analyze_data_confidence(expected_type, data)
                    
                    # ให้คะแนนพิเศษตาม address type
                    if addr_type == 'used':
                        confidence += 0.3
                    elif addr_type == 'default':
                        confidence += 0.1
                    
                    if confidence > 0.5:
                        detection_results.append({
                            'address': address,
                            'type': expected_type,
                            'confidence': confidence,
                            'data': data,
                            'is_used': is_used,
                            'addr_type': addr_type
                        })
                        print(f"    ✅ {expected_type.upper()} responds at {address} ({addr_type}) - confidence: {confidence:.2f}")
                    
            except Exception as e:
                # ไม่แสดง error เพราะปกติจะมี address ที่ไม่ตอบ
                pass
        
        # เลือกผลลัพธ์ที่ดีที่สุด
        if detection_results:
            # เรียงตาม confidence และ addr_type priority
            detection_results.sort(key=lambda x: (x['addr_type'] == 'used', x['confidence']), reverse=True)
            best = detection_results[0]
            
            return {
                'type': best['type'],
                'address': best['address'],
                'data': best['data'],
                'is_used': best['is_used']
            }
        
        return None


    def setup_new_sensor_initial(self, sensor_type, current_address, port_num):
        """
        ตั้งค่า address ใหม่ให้กับเซ็นเซอร์ในระหว่าง initial scan
        """
        print(f"  🔧 Setting up new address for {sensor_type.upper()} sensor...")
        
        # หา address ใหม่ที่ว่าง
        new_address = self.get_next_available_address(sensor_type)
        if new_address is None:
            print(f"    ❌ No available address for {sensor_type} sensor!")
            return None
        
        try:
            # Set address ใหม่
            sensor_class = self.sensor_types[sensor_type]['class']
            sensor = sensor_class(port="/dev/ttyS2", slave_address=current_address)
            
            print(f"    📝 Changing address from {current_address} to {new_address}")
            sensor.set_address(new_address)
            sensor.close()
            
            # Restart sensor
            print(f"    🔄 Restarting sensor...")
            self.mcp_system.turn_off_sensor(port_num)
            time.sleep(2)
            self.mcp_system.turn_on_all_sensors()
            # ปิดพอร์ตอื่นๆ ยกเว้นพอร์ตนี้
            for other_port in range(1, 13):
                if other_port != port_num:
                    self.mcp_system.turn_off_sensor(other_port)
            time.sleep(3)
            
            # ทดสอบ address ใหม่
            sensor_new = sensor_class(port="/dev/ttyS2", slave_address=new_address)
            
            test_data = None
            if sensor_type == 'soil':
                test_data = sensor_new.read_data(addr=new_address)
            elif sensor_type == 'solar':
                test_data = sensor_new.read_radiation(addr=new_address)
            elif sensor_type == 'wind':
                test_data = sensor_new.read_wind(addr=new_address)
            
            sensor_new.close()
            
            if test_data is not None:
                # บันทึก address ใหม่
                self.sensor_types[sensor_type]['used_addresses'].append(new_address)
                self.save_used_addresses()
                
                print(f"    ✅ Address setup successful: {new_address} (0x{new_address:02X})")
                return new_address
            else:
                print(f"    ❌ Failed to verify new address")
                return None
                
        except Exception as e:
            print(f"    ❌ Error setting up address: {e}")
            return None
        

# Main execution
if __name__ == "__main__":
    system = None
    
    try:
        # สร้างระบบ
        system = SensorManagementSystem()
        
        print("\n🎮 Select operation mode:")
        print("1. Start complete system (recommended)")
        print("2. Test MCP sensor detection only")
        print("3. Show system status")
        print("4. Read all sensors in address ranges (ONE TIME)")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            # เริ่มระบบปกติ
            # system.start_system()
            # system.debug_all_addresses()
            
            print("\n🔌 Starting Auto-Scanning Sensor System")
            print("==================================================")

            while True:
                count = system.initial_comprehensive_scan()

                # เตรียม JSON สรุป
                result = {
                    "timestamp": datetime.now().isoformat(),
                    "total_connected": count,
                    "sensors": []
                }

                for port, info in system.connected_sensors.items():
                    result["sensors"].append({
                        "port": port,
                        "type": info["type"],
                        "address": info["address"],
                        "address_hex": f"0x{info['address']:02X}"
                    })

                # แสดงผล JSON สรุป
                print("\n📦 JSON Summary:")
                print(json.dumps(result, indent=2))

                print("\n⏳ Waiting 60 seconds for next scan...\n")
                time.sleep(60)
                
        elif choice == "2":
            # ทดสอบ MCP เท่านั้น
            system.mcp_system.test_sensor_detection_values()
            
        elif choice == "3":
            # แสดงสถานะ
            system.print_system_status()

        elif choice == "4":
            # อ่านครั้งเดียวแล้วจบ
            system.mcp_system.start_system()
            time.sleep(3)
            system.read_all_sensors_in_range()
            
        elif choice == "5":
            print("👋 Goodbye!")
        else:
            print("❌ Invalid choice!")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"❌ System error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if system:
            system.stop_system()
        print("\n🏁 Program terminated.")