#!/usr/bin/env python3
"""
Standalone RPC Handler - ไม่ต้องแก้ไฟล์ main เลย
รันแยก process และใช้ system commands
"""

import json
import subprocess
import time
import logging
import signal
import sys

from telemetry_sending_paho import ThingsBoardSender

class StandaloneRPCHandler:
    def __init__(self, thingsboard_config):
        self.config = thingsboard_config
        self.tb_sender = None
        self.running = True
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("StandaloneRPC")
        
    def initialize_thingsboard(self):
        """เชื่อมต่อ ThingsBoard เฉพาะ RPC"""
        try:
            self.tb_sender = ThingsBoardSender(
                host=self.config["host"],
                port=self.config["port"],
                access_token=self.config["access_token"]  # ใช้ token เดียวกัน!
            )
            
            if self.tb_sender.connect():
                self.logger.info("✅ RPC: ThingsBoard connected")
                self.register_rpc_methods()
                self.tb_sender.start_rpc_handler()
                return True
            else:
                self.logger.error("❌ RPC: Connection failed")
                return False
                
        except Exception as e:
            self.logger.error(f"RPC initialization error: {e}")
            return False
    
    def register_rpc_methods(self):
        """RPC methods ที่ใช้ system commands"""
        
        def rpc_reboot(method, params):
            if not params.get("param", False):
                return {"success": False, "message": "param must be true"}
            
            try:
                # Reboot ตรงๆ
                subprocess.Popen(["reboot"])
                return {"success": True, "message": "Reboot initiated"}
            except Exception as e:
                return {"success": False, "message": f"Reboot failed: {e}"}
        
        def rpc_restart_main_service(method, params):
            try:
                # Restart main service ผ่าน init.d script
                subprocess.run(["/etc/init.d/S99main_service", "restart"], 
                             check=True, timeout=30)
                return {"success": True, "message": "Main service restarted"}
            except Exception as e:
                return {"success": False, "message": f"Restart failed: {e}"}
        
        def rpc_get_system_status(method, params):
            try:
                status = {}
                
                # Check service status
                try:
                    result = subprocess.run(["/etc/init.d/S90sensor_system", "status"], 
                                          capture_output=True, text=True, timeout=5)
                    status["main_service"] = "running" if result.returncode == 0 else "stopped"
                except:
                    status["main_service"] = "unknown"
                
                # Check uptime
                try:
                    with open("/proc/uptime", "r") as f:
                        uptime = float(f.read().split()[0]) / 3600
                        status["uptime_hours"] = round(uptime, 1)
                except:
                    status["uptime_hours"] = "unknown"
                
                return {"success": True, "status": status}
            except Exception as e:
                return {"success": False, "message": f"Status failed: {e}"}
        
        def rpc_reset_remote(method, params):
            if not params.get("param", False):
                return {"success": False, "message": "param must be true"}
            
            try:
                subprocess.run(["sh", "-x", "/etc/init.d/S99sshtunnel", "restart"], 
                             check=True, timeout=30)
                return {"success": True, "message": "SSH tunnel restarted"}
            except Exception as e:
                return {"success": False, "message": f"SSH restart failed: {e}"}
        
        # Register methods
        self.tb_sender.register_rpc_method("reboot", rpc_reboot, 
                                         {"required": ["param"], "types": {"param": "bool"}})
        self.tb_sender.register_rpc_method("restart_main_service", rpc_restart_main_service)
        self.tb_sender.register_rpc_method("get_system_status", rpc_get_system_status)
        self.tb_sender.register_rpc_method("reset_remote", rpc_reset_remote,
                                         {"required": ["param"], "types": {"param": "bool"}})
        
        self.logger.info("✅ RPC methods registered")
    
    def run(self):
        self.logger.info("🚀 Starting Standalone RPC Handler...")
        
        if not self.initialize_thingsboard():
            return
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("🛑 Stopping...")
        finally:
            if self.tb_sender:
                self.tb_sender.close()

if __name__ == "__main__":
    config = {
        "host": "thingsboard.weaverbase.com",
        "port": 1883,
        "access_token": "SK1b5Lq5QVpO1oY0yQeK"  # Same token as main!
    }
    
    rpc_handler = StandaloneRPCHandler(config)
    rpc_handler.run()
