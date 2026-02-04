import time
import json
import subprocess
from telemetry_sending_paho import ThingsBoardSender  # คลาสที่แก้ไขแล้ว

# ----------------- CONFIG -----------------
THINGSBOARD_HOST = "thingsboard.weaverbase.com"
THINGSBOARD_PORT = 1883
ACCESS_TOKEN = "ufqdqoxO7cmrnlSBUEeZ"

# ----------------- RPC HANDLERS -----------------
def rpc_reset_remote(method, params):
    """
    Handler สำหรับ RPC method 'reset_remote'
    """
    if not params.get("param", False):
        return {"success": False, "message": "param must be true"}

    try:
        # รัน restart tunnel
        subprocess.run(["sh", "-x", "/etc/init.d/S99sshtunnel", "restart"], check=True)
        # รัน start tunnel
        subprocess.run(["sh", "-x", "/etc/init.d/S99sshtunnel", "start"], check=True)
        return {
            "success": True,
            "message": "S99sshtunnel restarted and started",
            "timestamp": int(time.time()*1000)
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "message": f"reset_remote failed: {e}"
        }

def rpc_reboot(method, params):
    """
    Handler สำหรับ RPC method 'reboot'
    """
    if not params.get("param", False):
        return {"success": False, "message": "param must be true"}

    try:
        subprocess.run(["reboot"], check=True)
        return {
            "success": True,
            "message": "Reboot command sent",
            "timestamp": int(time.time()*1000)
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "message": f"reboot failed: {e}"
        }

# ----------------- MAIN -----------------
if __name__ == "__main__":
    tb = ThingsBoardSender(THINGSBOARD_HOST, THINGSBOARD_PORT, ACCESS_TOKEN)

    # ลงทะเบียน RPC
    tb.register_rpc_method("reset_remote", rpc_reset_remote, {
        "required": ["param"], "types": {"param": "bool"}
    })
    tb.register_rpc_method("reboot", rpc_reboot, {
        "required": ["param"], "types": {"param": "bool"}
    })

    if tb.connect():
        tb.start_rpc_handler()  # เปิดใช้งานรับ RPC
        print("Connected to ThingsBoard and listening for RPC...")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            tb.close()
    else:
        print("Failed to connect to ThingsBoard")
