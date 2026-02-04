#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import time
import logging

class RPC_Test_Receiver:
    def __init__(self, host, port, access_token):
        self.host = host
        self.port = port
        self.access_token = access_token
        self.client = None
        self.connected = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize MQTT client
        self._init_client()
        
    def _init_client(self):
        """Initialize MQTT client"""
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.client.username_pw_set(self.access_token)
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            self.logger.info("MQTT client initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MQTT client: {e}")
            
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback เมื่อเชื่อมต่อสำเร็จ"""
        if rc == 0:
            self.connected = True
            self.logger.info("✅ Connected to ThingsBoard successfully!")
            
            # Subscribe to RPC topic
            try:
                client.subscribe("v1/devices/me/rpc/request/+", qos=1)
                self.logger.info("📡 Subscribed to RPC topic: v1/devices/me/rpc/request/+")
                print("\n🎯 Ready to receive RPC commands...")
                print("💡 Send RPC from ThingsBoard Dashboard to test")
                print("-" * 50)
            except Exception as e:
                self.logger.error(f"Failed to subscribe to RPC topic: {e}")
        else:
            self.connected = False
            self.logger.error(f"❌ Failed to connect to ThingsBoard: {rc}")
            
    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback เมื่อขาดการเชื่อมต่อ"""
        self.connected = False
        self.logger.warning(f"🔌 Disconnected from ThingsBoard: {rc}")
        
    def _on_message(self, client, userdata, message):
        """Callback เมื่อได้รับข้อความ"""
        try:
            topic = message.topic
            payload = message.payload.decode('utf-8')
            
            print("\n" + "="*60)
            print(f"📨 MESSAGE RECEIVED!")
            print("="*60)
            print(f"📍 Topic: {topic}")
            print(f"📦 Raw Payload:")
            print(payload)
            print("-" * 40)
            
            # ลอง Parse JSON
            try:
                rpc_data = json.loads(payload)
                print(f"✅ Parsed JSON successfully:")
                print(json.dumps(rpc_data, indent=2, ensure_ascii=False))
                
                # วิเคราะห์ข้อมูล RPC
                self._analyze_rpc_data(rpc_data)
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON Parse Error: {e}")
                print(f"Raw data: {payload}")
                
            print("="*60)
            
            # ส่ง response กลับ (ถ้าเป็น RPC)
            if topic == "v1/devices/me/rpc/request/+":
                self._send_test_response(rpc_data)
                
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            
    def _analyze_rpc_data(self, rpc_data):
        """วิเคราะห์ข้อมูล RPC ที่ได้รับ"""
        print(f"🔍 RPC DATA ANALYSIS:")
        print("-" * 30)
        
        # เช็ค structure
        if isinstance(rpc_data, dict):
            print(f"📋 Data Type: Dictionary")
            print(f"📊 Keys: {list(rpc_data.keys())}")
            
            # วิเคราะห์แต่ละ field
            for key, value in rpc_data.items():
                print(f"   {key}: {value} (type: {type(value).__name__})")
                
                # ถ้าเป็น dict ให้วิเคราะห์ลึกลงไป
                if isinstance(value, dict):
                    print(f"     └─ Sub-keys: {list(value.keys())}")
                    for sub_key, sub_value in value.items():
                        print(f"        {sub_key}: {sub_value} (type: {type(sub_value).__name__})")
                        
        # เช็คตาม ThingsBoard Gateway RPC format
        expected_fields = ["device", "data"]
        missing_fields = []
        
        for field in expected_fields:
            if field not in rpc_data:
                missing_fields.append(field)
                
        if missing_fields:
            print(f"⚠️  Missing expected fields: {missing_fields}")
        else:
            print(f"✅ Has all expected fields: {expected_fields}")
            
            # วิเคราะห์ data field
            data = rpc_data.get("data", {})
            if isinstance(data, dict):
                data_fields = ["id", "method", "params"]
                for field in data_fields:
                    if field in data:
                        print(f"✅ data.{field}: {data[field]}")
                    else:
                        print(f"❌ Missing data.{field}")
                        
    def _send_test_response(self, rpc_data):
        """ส่ง response ทดสอบกลับไป"""
        try:
            if not isinstance(rpc_data, dict):
                print("❌ Cannot send response: Invalid RPC data format")
                return
                
            device_name = rpc_data.get("device")
            data = rpc_data.get("data", {})
            request_id = data.get("id")
            method = data.get("method")
            params = data.get("params", {})
            
            if not all([device_name, request_id, method]):
                print("❌ Cannot send response: Missing required fields")
                return
                
            # สร้าง test response
            test_response = {
                "success": True,
                "message": f"Test response for method '{method}'",
                "method": method,
                "params_received": params,
                "timestamp": int(time.time() * 1000),
                "test_mode": True
            }
            
            # สร้าง response message ตาม Gateway format
            response_message = {
                device_name: [
                    {
                        "id": request_id,
                        "data": test_response
                    }
                ]
            }
            
            message = json.dumps(response_message, ensure_ascii=False)
            
            print(f"\n📤 SENDING TEST RESPONSE:")
            print("-" * 30)
            print(f"📍 Topic: v1/devices/me/rpc/request/+")
            print(f"📦 Response:")
            print(json.dumps(response_message, indent=2, ensure_ascii=False))
            
            # ส่งผ่าน MQTT
            result = self.client.publish("v1/devices/me/rpc/request/+", message, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✅ Response sent successfully!")
            else:
                print(f"❌ Failed to send response: {result.rc}")
                
        except Exception as e:
            print(f"❌ Error sending response: {e}")
            
    def connect(self):
        """เชื่อมต่อ ThingsBoard"""
        try:
            if not self.connected:
                self.logger.info(f"Connecting to {self.host}:{self.port}...")
                self.client.connect(self.host, self.port, 60)
                self.client.loop_start()
                
                # รอการเชื่อมต่อ
                timeout = 10
                start_time = time.time()
                while not self.connected and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                
                if self.connected:
                    return True
                else:
                    self.logger.error("Connection timeout")
                    return False
            else:
                return True
                
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False
            
    def disconnect(self):
        """ตัดการเชื่อมต่อ"""
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
                self.connected = False
                self.logger.info("Disconnected from ThingsBoard")
        except Exception as e:
            self.logger.error(f"Error disconnecting: {e}")


# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    print("🚀 ThingsBoard RPC Test Receiver")
    print("="*50)
    
    # กำหนดค่าการเชื่อมต่อ
    THINGSBOARD_HOST = "thingsboard.weaverbase.com"
    THINGSBOARD_PORT = 1883
    ACCESS_TOKEN = "ufqdqoxO7cmrnlSBUEeZ"  # ใช้ token เดียวกับในไฟล์หลัก
    
    # สร้าง RPC receiver
    rpc_receiver = RPC_Test_Receiver(THINGSBOARD_HOST, THINGSBOARD_PORT, ACCESS_TOKEN)
    
    # เชื่อมต่อ
    if rpc_receiver.connect():
        print("🎯 RPC Receiver started successfully!")
        print("\n💡 Instructions:")
        print("1. Go to ThingsBoard Dashboard")
        print("2. Find your device (SLXA125005)")
        print("3. Send RPC command from Device RPC tab")
        print("4. Watch the output here")
        print("\n⏹️  Press Ctrl+C to stop")
        print("-"*50)
        
        try:
            # รอรับ RPC อยู่ตลอด
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping RPC receiver...")
            
        finally:
            rpc_receiver.disconnect()
            print("👋 Goodbye!")
            
    else:
        print("❌ Failed to connect to ThingsBoard")
