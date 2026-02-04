#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import time
import logging
import subprocess
import threading
import os

class IntegratedRPCHandler:
    def __init__(self, host, port, access_token):
        self.host = host
        self.port = port
        self.access_token = access_token
        self.client = None
        self.connected = False
        
        # RPC handling
        self.registered_methods = {}
        self.method_validators = {}
        
        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize MQTT client
        self._init_client()
        
        # Register RPC methods
        self._register_rpc_methods()
        
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
            
            # Subscribe to Device RPC topic
            try:
                client.subscribe("v1/devices/me/rpc/request/+", qos=1)
                self.logger.info("📡 Subscribed to Device RPC topic: v1/devices/me/rpc/request/+")
                print("\n🎯 RPC Handler ready - listening for commands...")
                print(f"🔧 Registered methods: {list(self.registered_methods.keys())}")
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
        """Callback เมื่อได้รับ RPC request"""
        try:
            topic = message.topic
            payload = message.payload.decode('utf-8')
            
            print(f"\n📨 RPC Request Received!")
            print(f"📍 Topic: {topic}")
            
            # Extract request ID from topic
            if topic.startswith("v1/devices/me/rpc/request/"):
                request_id = topic.split("/")[-1]
                self._handle_device_rpc_request(payload, request_id)
            else:
                self.logger.warning(f"Unknown topic: {topic}")
                
        except Exception as e:
            print(f"❌ Error processing RPC message: {e}")
            
    def _handle_device_rpc_request(self, payload, request_id):
        """จัดการ Device RPC request"""
        try:
            # Parse JSON
            rpc_data = json.loads(payload)
            method = rpc_data.get("method")
            params = rpc_data.get("params", {})
            
            print(f"🔄 Method: {method}")
            print(f"📊 Params: {params}")
            print(f"🆔 Request ID: {request_id}")
            
            # Validate method
            if method not in self.registered_methods:
                response = {
                    "error": f"Unsupported method: {method}",
                    "available_methods": list(self.registered_methods.keys())
                }
                self._send_rpc_response(request_id, response)
                return
            
            # Validate parameters
            validation_result = self._validate_method_params(method, params)
            if not validation_result["valid"]:
                response = {
                    "error": f"Invalid parameters: {validation_result['error']}",
                    "required_params": validation_result.get("required_params", [])
                }
                self._send_rpc_response(request_id, response)
                return
            
            # Execute method
            method_handler = self.registered_methods[method]
            try:
                response = method_handler(method, params)
                self._send_rpc_response(request_id, response)
            except Exception as e:
                error_response = {"error": f"Method execution failed: {str(e)}"}
                self._send_rpc_response(request_id, error_response)
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON Parse Error: {e}")
        except Exception as e:
            print(f"❌ Error handling RPC: {e}")
            
    def _validate_method_params(self, method, params):
        """ตรวจสอบ parameters ตาม validation rules"""
        if method not in self.method_validators:
            return {"valid": True}
            
        validator = self.method_validators[method]
        
        # เช็ค required parameters
        required_params = validator.get("required", [])
        for param in required_params:
            if param not in params:
                return {
                    "valid": False,
                    "error": f"Missing required parameter: {param}",
                    "required_params": required_params
                }
        
        # เช็ค parameter types
        param_types = validator.get("types", {})
        for param, expected_type in param_types.items():
            if param in params:
                value = params[param]
                if expected_type == "bool" and not isinstance(value, bool):
                    return {
                        "valid": False,
                        "error": f"Parameter '{param}' must be a boolean"
                    }
        
        return {"valid": True}
    
    def _send_rpc_response(self, request_id, response):
        """ส่ง RPC response กลับไป ThingsBoard"""
        try:
            if not self.connected:
                print("❌ Cannot send response: not connected")
                return False
                
            response_topic = f"v1/devices/me/rpc/response/{request_id}"
            message = json.dumps(response, ensure_ascii=False)
            
            print(f"📤 Sending response to: {response_topic}")
            print(f"📦 Response: {response}")
            
            result = self.client.publish(response_topic, message, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✅ Response sent successfully!")
                return True
            else:
                print(f"❌ Failed to send response: {result.rc}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending response: {e}")
            return False
    
    def _register_rpc_methods(self):
        """ลงทะเบียน RPC methods และกำหนดเงื่อนไข"""
        
        # 1. Method: reset_remote
        self.register_rpc_method(
            method_name="reset_remote",
            handler_function=self._handle_reset_remote,
            validation_rules={
                "required": ["param"],
                "types": {"param": "bool"}
            }
        )
        
        # 2. Method: reboot
        self.register_rpc_method(
            method_name="reboot",
            handler_function=self._handle_reboot,
            validation_rules={
                "required": ["param"],
                "types": {"param": "bool"}
            }
        )
        
        print("🔧 RPC methods registered successfully")
    
    def register_rpc_method(self, method_name, handler_function, validation_rules=None):
        """ลงทะเบียน RPC method"""
        self.registered_methods[method_name] = handler_function
        
        if validation_rules:
            self.method_validators[method_name] = validation_rules
            
        self.logger.debug(f"Registered RPC method: {method_name}")
    
    def get_thailand_timestamp(self):
        """สร้าง timestamp ปัจจุบัน"""
        return int(time.time() * 1000)
    
    # 🚀 RPC Handler Methods
    def _handle_reset_remote(self, method, params):
        """Handler สำหรับ reset remote SSH tunnel"""
        try:
            param = params.get("param")
            
            if param is not True:
                return {
                    "success": False,
                    "message": "reset_remote requires param=true to execute",
                    "param_received": param,
                    "timestamp": self.get_thailand_timestamp()
                }
            
            print("🔄 Reset remote SSH tunnel initiated by RPC command")
            
            def execute_reset_remote():
                try:
                    # คำสั่งที่ 1: restart
                    print("🔧 Executing: sh -x /etc/init.d/S99sshtunnel restart")
                    result1 = subprocess.run(
                        ["sh", "-x", "/etc/init.d/S99sshtunnel", "restart"],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    print(f"   Restart output: {result1.stdout}")
                    if result1.stderr:
                        print(f"   Restart stderr: {result1.stderr}")
                    
                    # รอ 2 วินาที
                    time.sleep(2)
                    
                    # คำสั่งที่ 2: start
                    print("🔧 Executing: sh -x /etc/init.d/S99sshtunnel start")
                    result2 = subprocess.run(
                        ["sh", "-x", "/etc/init.d/S99sshtunnel", "start"],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    print(f"   Start output: {result2.stdout}")
                    if result2.stderr:
                        print(f"   Start stderr: {result2.stderr}")
                    
                    print("✅ Reset remote SSH tunnel completed")
                    
                except subprocess.TimeoutExpired:
                    print("❌ SSH tunnel reset timeout")
                except Exception as e:
                    print(f"❌ Error executing SSH tunnel reset: {e}")
            
            # รันในแบบ background thread
            reset_thread = threading.Thread(target=execute_reset_remote, daemon=True)
            reset_thread.start()
            
            return {
                "success": True,
                "message": "SSH tunnel reset initiated",
                "commands": [
                    "sh -x /etc/init.d/S99sshtunnel restart",
                    "sh -x /etc/init.d/S99sshtunnel start"
                ],
                "param": param,
                "timestamp": self.get_thailand_timestamp()
            }
            
        except Exception as e:
            return {"error": f"Failed to reset remote: {str(e)}"}
    
    def _handle_reboot(self, method, params):
        """Handler สำหรับ reboot ระบบ"""
        try:
            param = params.get("param")
            
            if param is not True:
                return {
                    "success": False,
                    "message": "reboot requires param=true to execute",
                    "param_received": param,
                    "timestamp": self.get_thailand_timestamp()
                }
            
            print("🔄 System reboot initiated by RPC command")
            
            def execute_reboot():
                try:
                    # รอ 5 วินาทีเพื่อให้ response ส่งกลับไปก่อน
                    print("⏳ Waiting 5 seconds before reboot...")
                    time.sleep(5)
                    
                    # Execute reboot command
                    print("🔄 Executing reboot command...")
                    subprocess.run(["reboot"], check=True)
                    
                except Exception as e:
                    print(f"❌ Error executing reboot: {e}")
                    # Fallback reboot methods
                    try:
                        subprocess.run(["sudo", "reboot"], check=True)
                    except:
                        try:
                            subprocess.run(["systemctl", "reboot"], check=True)
                        except:
                            print("❌ All reboot methods failed")
            
            # รันในแบบ background thread
            reboot_thread = threading.Thread(target=execute_reboot, daemon=True)
            reboot_thread.start()
            
            return {
                "success": True,
                "message": "System reboot initiated - device will restart in 5 seconds",
                "command": "reboot",
                "param": param,
                "delay": 5,
                "timestamp": self.get_thailand_timestamp()
            }
            
        except Exception as e:
            return {"error": f"Failed to reboot: {str(e)}"}
    
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


# Main execution
if __name__ == "__main__":
    print("🚀 Integrated RPC Handler for Sensor Control System")
    print("="*60)
    
    # กำหนดค่าการเชื่อมต่อ
    THINGSBOARD_HOST = "thingsboard.weaverbase.com"
    THINGSBOARD_PORT = 1883
    ACCESS_TOKEN = "ufqdqoxO7cmrnlSBUEeZ"
    
    # สร้าง RPC handler
    rpc_handler = IntegratedRPCHandler(THINGSBOARD_HOST, THINGSBOARD_PORT, ACCESS_TOKEN)
    
    # เชื่อมต่อ
    if rpc_handler.connect():
        print("🎯 RPC Handler started successfully!")
        print("\n💡 Available RPC Methods:")
        print("1. reset_remote - Restart SSH tunnel service")
        print("   Parameters: {\"param\": true}")
        print("2. reboot - Restart the system")
        print("   Parameters: {\"param\": true}")
        print("\n📋 How to test:")
        print("1. Go to ThingsBoard Dashboard")
        print("2. Find your device")
        print("3. Go to RPC tab")
        print("4. Send RPC command")
        print("\n⏹️  Press Ctrl+C to stop")
        print("-"*60)
        
        try:
            # รอรับ RPC อยู่ตลอด
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping RPC handler...")
            
        finally:
            rpc_handler.disconnect()
            print("👋 RPC Handler stopped!")
            
    else:
        print("❌ Failed to connect to ThingsBoard")
