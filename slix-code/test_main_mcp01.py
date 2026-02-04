from test_mcp01 import SensorControlSystem


system = SensorControlSystem()


system.turn_on_all_sensors()


# monitor_thread = system.start_system()


input("Press Enter to stop...")
system.stop_system()


#เปิดแค่พอตเดียว
#!/usr/bin/env python3
# import time
# from test_mcp01 import SensorControlSystem

# def main():
#     scs = SensorControlSystem()          
#     monitor_thread = None
#     try:
   
#         monitor_thread = scs.start_system()  
#         #เลือก port ที่ต้องการเปิด
#         scs.turn_on_sensor(5)            
#         print("Port 5 is ON. Press Ctrl+C to stop.")
        
#         # ทำงานหลักของโปรแกรม
#         while True:
#             time.sleep(0.5)

#     except KeyboardInterrupt:

#         print("\nKeyboardInterrupt received. Shutting down safely...")

#     finally:

#         try:

#             for port in range(1, 13):
#                 try:
#                     scs.turn_off_sensor(port)
#                 except Exception:
#                     pass
#         except Exception as e:
#             print(f"Error while turning off sensors: {e}")

       
#         try:
#             scs.stop_system()               
#         except Exception as e:
#             print(f"Error in stop_system: {e}")

# if __name__ == "__main__":
#     main()
